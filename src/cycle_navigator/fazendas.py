# -*- coding: utf-8 -*-
"""DE QUEM E' A AREA -- poligonos desenhados no mapa, com a tabela de atributos de quem respondeu.

O levantamento tem duas perguntas: o que foi plantado (ver `ciclos.py`) e de quem e' a terra. Esta e'
a segunda. O funcionario contorna a fazenda, preenche o cadastro, e a partir daí todo talhao marcado
dentro daquele poligono ja' sai com esses dados.

⚠️⚠️ A HERANCA E' O PONTO. Sem ela, quem esta' em campo redigita o nome do produtor e o telefone a
cada talhao, com o produtor esperando -- e o que acontece na pratica e' que para de preencher. Uma
fazenda tem dezenas de talhoes; o cadastro se digita UMA vez.

⚠️ DESENHO VERTICE A VERTICE, como em qualquer SIG. Clique poe vertice, o mouse arrasta uma linha
elastica, duplo-clique ou Enter fecha, Backspace tira o ultimo, Esc cancela. A versao anterior
entregava um quadrado pronto para o usuario deformar -- gesto que nao existe em ferramenta de SIG
nenhuma, e que obriga a desfazer um trabalho antes de comecar o seu.

⚠️ O poligono e' guardado em PIXEL (linha/coluna) e em UTM. Pixel porque e' nisso que o mapa e os
pontos trabalham, UTM porque e' o que sobrevive ao recorte: se um dia a janela do AOI mudar, as
coordenadas de pixel apontam para outro lugar e as de terreno continuam certas.
"""
import json
import logging
import os
import tempfile
from datetime import date

import numpy as np
import pyqtgraph as pg
from matplotlib.path import Path as _Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                             QPlainTextEdit, QVBoxLayout)

log = logging.getLogger(__name__)

STATUS = ["nao visitado", "visitado", "nao encontrado", "recusou"]
COR_STATUS = {"nao visitado": "#9aa0a6", "visitado": "#33c16f",
              "nao encontrado": "#d9a441", "recusou": "#c0392b"}
COLUNAS = [("nome", "Fazenda"), ("proprietario", "Proprietário"), ("contato", "Contato"),
           ("status", "Visita"), ("data_visita", "Data"), ("car", "CAR"), ("area_ha", "Área (ha)")]


# ==================================================================== dados
class CadastroFazendas:
    """Os poligonos e seus atributos, num JSON ao lado dos pontos.

    ⚠️ Escrita atomica (grava num temporario e renomeia). Um desligamento no meio da gravacao, num
    notebook em campo, nao pode deixar o cadastro do dia pela metade.
    """

    def __init__(self, caminho, transform=None, crs=None):
        self.caminho = str(caminho)
        self.transform = transform
        self.crs = str(crs) if crs else None
        self.fazendas = []
        self._paths = {}
        self.carrega()

    def carrega(self):
        if not os.path.exists(self.caminho):
            return
        try:
            with open(self.caminho, encoding="utf-8") as f:
                self.fazendas = json.load(f).get("fazendas", [])
        except (OSError, ValueError) as e:
            log.warning("cadastro de fazendas ilegivel (%s): %s", self.caminho, e)
            self.fazendas = []
        self._reindexa()

    def grava(self):
        d = {"format_version": 1, "crs": self.crs, "fazendas": self.fazendas}
        pasta = os.path.dirname(self.caminho) or "."
        os.makedirs(pasta, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=pasta, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.caminho)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _reindexa(self):
        # matplotlib.path em vez de shapely: ja' vem com o ts-annotator, e um teste de
        # ponto-em-poligono nao justifica mais uma dependencia num computador de campo.
        self._paths = {f["id"]: _Path(np.asarray(f["poligono"], float))
                       for f in self.fazendas if len(f.get("poligono") or []) >= 3}

    def em(self, row, col):
        """A fazenda que contem este pixel, ou None. (col, row) = (x, y) do poligono."""
        for f in self.fazendas:
            p = self._paths.get(f["id"])
            if p is not None and p.contains_point((col, row)):
                return f
        return None

    def por_id(self, fid):
        return next((f for f in self.fazendas if f["id"] == fid), None)

    def salva(self, fid, poligono=None, dados=None):
        """Cria ou atualiza. `poligono` = [(col, row), ...] em pixel; None mantem o que havia."""
        f = self.por_id(fid) if fid else None
        if f is None:
            fid = max((x["id"] for x in self.fazendas), default=0) + 1
            f = {"id": fid}
            self.fazendas.append(f)
        if poligono is not None:
            poli = [[float(c), float(r)] for c, r in poligono]
            f["poligono"] = poli
            if self.transform is not None:
                f["poligono_utm"] = [list(self.transform * (c, r)) for c, r in poli]
                f["area_ha"] = round(
                    _area_px(poli) * abs(self.transform.a * self.transform.e) / 1e4, 2)
        if dados:
            f.update(dados)
        f["atualizado_em"] = date.today().isoformat()
        self._reindexa()
        self.grava()
        return f

    def remove(self, fid):
        self.fazendas = [f for f in self.fazendas if f["id"] != fid]
        self._reindexa()
        self.grava()

    def __len__(self):
        return len(self.fazendas)


def _area_px(poli):
    a = np.asarray(poli, float)
    x, y = a[:, 0], a[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


# ==================================================================== desenho
class DesenhoPoligono:
    """Desenho vertice a vertice sobre o mapa, no gesto de SIG. Ver o aviso do topo."""

    def __init__(self, view, ao_terminar):
        self.view = view
        self.ao_terminar = ao_terminar
        self.vb = view.vb
        self.cena = view.glw.scene()
        self.pts = []
        self.ativo = False
        self.editando = None
        self._linha = pg.PlotDataItem(pen=pg.mkPen("#00e5ff", width=2.5))
        self._elastico = pg.PlotDataItem(pen=pg.mkPen("#00e5ff", width=1.5,
                                                      style=Qt.PenStyle.DashLine))
        self._vert = pg.ScatterPlotItem(size=9, brush=pg.mkBrush("#00e5ff"),
                                        pen=pg.mkPen("#06212b", width=1.5))
        for it in (self._linha, self._elastico, self._vert):
            it.setZValue(40)
        self._roi = None

    # ---------- criar ----------
    def comeca(self, fid=None, poligono=None):
        self.cancela()
        self.editando = fid
        if poligono:                      # editar contorno existente: ja' nasce como ROI
            self._abre_roi([tuple(p) for p in poligono])
            return
        self.ativo = True
        self.pts = []
        for it in (self._linha, self._elastico, self._vert):
            self.vb.addItem(it)
        self.cena.sigMouseMoved.connect(self._moveu)
        self.view.setCursor(Qt.CursorShape.CrossCursor)

    def clique(self, ev):
        """Devolve True se consumiu o clique (ou seja, o mapa nao deve tratar como ponto)."""
        if not self.ativo:
            return False
        p = self.vb.mapSceneToView(ev.scenePos())
        if ev.double():
            self.fecha()
            return True
        if ev.button() == Qt.MouseButton.RightButton:
            self.desfaz_vertice()
            return True
        self.pts.append((p.x(), p.y()))
        self._redesenha()
        return True

    def _moveu(self, pos):
        if not self.ativo or not self.pts:
            return
        p = self.vb.mapSceneToView(pos)
        a = self.pts[-1]
        self._elastico.setData([a[0], p.x()], [a[1], p.y()])

    def _redesenha(self):
        if not self.pts:
            self._linha.clear(); self._vert.clear(); return
        a = np.asarray(self.pts, float)
        fechado = np.vstack([a, a[:1]]) if len(a) > 2 else a
        self._linha.setData(fechado[:, 0], fechado[:, 1])
        self._vert.setData(a[:, 0], a[:, 1])

    def desfaz_vertice(self):
        if self.pts:
            self.pts.pop()
            self._redesenha()
            self._elastico.clear()

    def fecha(self):
        """Fecha o contorno e passa para o modo de ajustar vertices."""
        if len(self.pts) < 3:
            return False
        pts = list(self.pts)
        self._sai_do_desenho()
        self._abre_roi(pts)
        return True

    def _abre_roi(self, pts):
        self._roi = pg.PolyLineROI(pts, closed=True, pen=pg.mkPen("#00e5ff", width=3))
        self._roi.setZValue(40)
        self.vb.addItem(self._roi)

    def _sai_do_desenho(self):
        if not self.ativo:
            return
        self.ativo = False
        try:
            self.cena.sigMouseMoved.disconnect(self._moveu)
        except TypeError:
            pass
        for it in (self._linha, self._elastico, self._vert):
            it.clear()
            self.vb.removeItem(it)
        self.view.unsetCursor()

    def pontos(self):
        if self._roi is not None:
            h = self._roi.getSceneHandlePositions()
            return [(p.x(), p.y()) for p in (self._roi.mapSceneToParent(q) for _, q in h)]
        return list(self.pts)

    def cancela(self):
        self._sai_do_desenho()
        if self._roi is not None:
            self.vb.removeItem(self._roi)
            self._roi = None
        self.pts = []
        self.editando = None

    @property
    def em_curso(self):
        return self.ativo or self._roi is not None


class CamadaFazendas:
    """Os contornos ja' cadastrados, desenhados no mapa."""

    def __init__(self, view):
        self.view = view
        self.cadastro = None
        self._itens = []
        self.oculto = None       # id em edicao: nao desenha por cima do que se esta' editando

    def usar(self, cadastro):
        self.cadastro = cadastro
        self.redesenha()

    def redesenha(self):
        for it in self._itens:
            self.view.vb.removeItem(it)
        self._itens = []
        if self.cadastro is None:
            return
        for f in self.cadastro.fazendas:
            poli = f.get("poligono") or []
            if len(poli) < 3 or f["id"] == self.oculto:
                continue
            a = np.asarray(poli + [poli[0]], float)
            cor = COR_STATUS.get(f.get("status"), "#9aa0a6")
            linha = pg.PlotDataItem(a[:, 0], a[:, 1], pen=pg.mkPen(cor, width=2.5))
            linha.setZValue(15)
            # rotulo legivel SOBRE a imagem: tamanho de interface e fundo escuro translucido. O
            # TextItem padrao vem em 8 px sem fundo, e some em cima de um pivo claro.
            nome = f.get("nome") or f"#{f['id']}"
            txt = pg.TextItem(html=f'<span style="font-size:13px;font-weight:600;color:{cor};'
                                   f'padding:2px 6px">{nome}</span>',
                              anchor=(0.5, 1.3), fill=pg.mkBrush(10, 12, 8, 170),
                              border=pg.mkPen(cor, width=1))
            txt.setPos(float(a[:, 0].mean()), float(a[:, 1].mean()))
            txt.setZValue(16)
            for it in (linha, txt):
                self.view.vb.addItem(it)
                self._itens.append(it)


# ==================================================================== interface
class DialogoFazenda(QDialog):
    """O formulario de preenchimento. ⚠️ Popup, nao edicao na celula: em campo se digita um
    telefone e uma observacao de duas linhas, e isso nao cabe numa celula de tabela."""

    def __init__(self, dados=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cadastro da fazenda")
        self.setMinimumWidth(460)
        d = dados or {}
        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(14)
        self.nome = QLineEdit(d.get("nome", "")); self.nome.setPlaceholderText("ex.: Fazenda do João")
        self.dono = QLineEdit(d.get("proprietario", ""))
        self.contato = QLineEdit(d.get("contato", "")); self.contato.setPlaceholderText("telefone / WhatsApp")
        self.status = QComboBox(); self.status.addItems(STATUS)
        self.status.setCurrentText(d.get("status") or STATUS[0])
        self.data = QLineEdit(d.get("data_visita") or date.today().isoformat())
        self.obs = QPlainTextEdit(d.get("obs", "")); self.obs.setMaximumHeight(90)
        form.addRow("Fazenda", self.nome)
        form.addRow("Proprietário", self.dono)
        form.addRow("Contato", self.contato)
        form.addRow("Visita", self.status)
        form.addRow("Data", self.data)
        form.addRow("Observações", self.obs)
        if d.get("area_ha"):
            form.addRow("Área", QLabel(f"<b>{d['area_ha']:,.1f}</b> ha".replace(",", ".")))
        if d.get("car"):
            # bloco so'-leitura: o que o CAR publico sabe deste imovel (sem dono nem contato)
            from .car import CAMPOS
            tit = QLabel("<b>Dados do CAR</b> <span style='color:#888'>(só leitura)</span>")
            form.addRow(tit)
            for k, rot in CAMPOS:
                v = d.get(k)
                if v in (None, ""):
                    continue
                if isinstance(v, float):
                    v = f"{v:,.1f}".replace(",", ".")
                lb = QLabel(str(v)); lb.setWordWrap(True)
                lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                form.addRow(rot, lb)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        bb.button(QDialogButtonBox.StandardButton.Save).setObjectName("cta")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(bb)
        self.nome.setFocus()

    def dados(self):
        return {"nome": self.nome.text().strip(),
                "proprietario": self.dono.text().strip(),
                "contato": self.contato.text().strip(),
                "status": self.status.currentText(),
                "data_visita": self.data.text().strip() or date.today().isoformat(),
                "obs": self.obs.toPlainText().strip()}
