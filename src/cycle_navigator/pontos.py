# -*- coding: utf-8 -*-
"""MARCAR O QUE A AREA FOI -- o que o agricultor conta, gravado faixa a faixa do ano.

Serve ao trabalho de campo: alguem clica no talhao, ve' a curva daquele ano-safra com os ciclos ja'
sombreados (ver `ciclos.py`), e o produtor vai dizendo o que foi plantado em cada parte. O navegador
ja' sabia ler a FORMA da curva sem rotulo nenhum; isto acrescenta o rotulo que so' o campo tem.

⚠️⚠️ O ROTULO E' POR (LOCAL, SAFRA), NAO POR LOCAL. O mesmo talhao e' soja em 2023/24 e milho em
2024/25. Guardar um rotulo so' por pixel perderia a safra em silencio e misturaria anos diferentes no
mesmo ponto. Por isso ha' UM ARQUIVO POR SAFRA, e trocar a safra troca o conjunto de pontos.

⚠️ E DENTRO DA SAFRA O ROTULO E' UMA LISTA DE FAIXAS, nao uma classe. Um talhao de soja em outubro e
milho safrinha em marco nao e' "soja" nem "milho": sao duas lavouras no mesmo pixel, e e' justamente
essa sucessao que a contagem de ciclos tenta ler. Reduzir isso a uma classe so' jogaria fora a
resposta mais cara de obter.

⚠️ O armazenamento e' o `AnnotationStore` do ts-annotator, nao uma implementacao daqui. Ele ja'
resolve o que e' chato e facil de errar: um local = um rotulo (re-rotular ATUALIZA em vez de
duplicar), indice espacial para o clique achar o ponto existente, e escrita atomica -- um
desligamento no meio da gravacao nao deixa o arquivo pela metade.
"""
import csv
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ts_annotator.core.annotation_store import AnnotationStore

log = logging.getLogger(__name__)


def resumo(segmentos):
    """'Soja > Milho safrinha' -- o que aparece na lista e no contador."""
    return " > ".join(s["cultura"] for s in segmentos) if segmentos else "vazio"


class CamadaPontos:
    """Os pontos marcados, desenhados sobre o mapa.

    ⚠️ Redesenha so' o que esta' na vista (`store.query` por retangulo). Desenhar os N pontos a cada
    pan, com N crescendo a sessao inteira, trava a navegacao justamente quando o trabalho rende.
    """

    def __init__(self, view, cores):
        self.view = view
        self.cores = cores
        self.scatter = pg.ScatterPlotItem(size=13, pen=pg.mkPen("#000000", width=1.5),
                                          hoverable=False)
        self.scatter.setZValue(20)
        view.vb.addItem(self.scatter)
        self.store = None

    def usar(self, store):
        self.store = store
        self.redesenha()

    def redesenha(self):
        if self.store is None:
            return
        r = self.view.vb.viewRect()
        pts = self.store.query(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())
        if not pts:
            self.scatter.clear()
            return
        spots = []
        for p in pts:
            # a cor do ponto e' a da PRIMEIRA cultura do ano: e' a que o olho associa ao talhao
            cic = p.get("ciclos") or []
            nome = cic[0]["cultura"] if cic else p.get("class", "")
            spots.append({"pos": (p["col"] + 0.5, p["row"] + 0.5),
                          "brush": pg.mkBrush(pg.mkColor(self.cores.get(nome, "#ffffff")))})
        self.scatter.setData(spots)


class PainelPontos(QWidget):
    """Safra, contagem do que ja' foi levantado, desfazer e exportacao."""

    safraMudou = pyqtSignal(str)

    def __init__(self, cores, safras, arquivo_levantador=None, parent=None):
        super().__init__(parent)
        self.cores = dict(cores)
        self.store = None
        self._ultimo = None
        self._arq_lev = Path(arquivo_levantador) if arquivo_levantador else None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)

        lay.addWidget(QLabel("<b>Quem esta' levantando</b>"))
        # ⚠️ Fica gravado em disco e volta na proxima sessao. Pedir o nome toda vez que o programa
        # abre garante que um dia alguem deixa em branco ou poe o nome errado, e aí nao da' mais
        # para saber de quem foi a resposta -- que e' justamente o motivo de ter o campo.
        self.ed_levantador = QLineEdit()
        self.ed_levantador.setPlaceholderText("nome do aluno/funcionario")
        lay.addWidget(self.ed_levantador)

        lay.addWidget(QLabel("<b>Ano-safra</b>"))
        self.cb_safra = QComboBox()
        self.cb_safra.addItems(safras)
        self.cb_safra.currentTextChanged.connect(self.safraMudou.emit)
        lay.addWidget(self.cb_safra)
        lay.addWidget(QLabel("<span style='color:#888'>Clique num talhao para abrir o ciclo "
                             "do ano embaixo.</span>"))

        linha = QHBoxLayout()
        self.bt_desfazer = QPushButton("Desfazer  (Ctrl+Z)")
        self.bt_exportar = QPushButton("Exportar CSV")
        linha.addWidget(self.bt_desfazer); linha.addWidget(self.bt_exportar)
        lay.addLayout(linha)

        self.info = QLabel("nenhum ponto levantado")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        lay.addStretch(1)

        self.bt_desfazer.clicked.connect(self.desfaz)
        self.bt_exportar.clicked.connect(self.exporta)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.desfaz)

        if self._arq_lev and self._arq_lev.exists():
            try:
                self.ed_levantador.setText(self._arq_lev.read_text(encoding="utf-8").strip())
            except OSError as e:
                log.warning("nao li o levantador anterior: %s", e)
        self.ed_levantador.editingFinished.connect(self._salva_levantador)

    @property
    def levantador(self):
        return self.ed_levantador.text().strip()

    def _salva_levantador(self):
        if not self._arq_lev:
            return
        try:
            self._arq_lev.parent.mkdir(parents=True, exist_ok=True)
            self._arq_lev.write_text(self.levantador, encoding="utf-8")
        except OSError as e:
            log.warning("nao gravei o levantador: %s", e)

    def define_safra(self, safra):
        """Poe o seletor na safra indicada SEM disparar o sinal.

        ⚠️ Sem isto o combo mostra a primeira safra da lista enquanto o programa carregou outra, e
        quem esta' levantando acredita estar anotando um ano enquanto grava em outro. O rotulo iria
        para o arquivo certo e para o ano errado na cabeca da pessoa -- erro silencioso e caro.
        """
        self.cb_safra.blockSignals(True)
        self.cb_safra.setCurrentText(safra)
        self.cb_safra.blockSignals(False)

    def usar(self, store):
        self.store = store
        self._ultimo = None
        self.atualiza_info()

    def atualiza_info(self):
        if self.store is None:
            return
        total = len(self.store)
        if not total:
            self.info.setText("nenhum ponto levantado nesta safra")
            return
        # conta por CULTURA, somando as faixas: e' o numero que diz quanto campo ja' rendeu
        c, conf = Counter(), Counter()
        faixas = 0
        for p in self.store.points:
            for s in (p.get("ciclos") or []):
                c[s["cultura"]] += 1
                conf[s.get("confianca") or "—"] += 1
                faixas += 1
        linhas = "<br>".join(
            f"<span style='color:{self.cores.get(k, '#fff')}'>&#9679;</span> {k}: <b>{v}</b>"
            for k, v in c.most_common())
        # quantas faixas sao firmes importa tanto quanto quantas existem
        qual = " · ".join(f"{k}: {v}" for k, v in conf.most_common())
        self.info.setText(f"<b>{total}</b> talhao(oes) · <b>{faixas}</b> faixa(s)<br>{linhas}"
                          f"<br><span style='color:#888'>{qual}</span>")

    # ---------- acoes ----------
    def registra(self, row, col, curva, segmentos, produtor="", fazenda=None):
        """Grava o que o agricultor disse. Devolve (ponto, era_atualizacao)."""
        if self.store is None:
            return None
        pt, atualizou = self.store.add_or_update(row, col, resumo(segmentos), curve=curva)
        # ⚠️ o vinculo com a fazenda e' gravado por ID E por nome. O id liga ao cadastro; o nome
        # sobrevive se o cadastro for perdido ou o poligono redesenhado, e e' o que vai no CSV.
        if fazenda:
            pt["fazenda_id"] = fazenda.get("id")
            pt["fazenda"] = fazenda.get("nome", "")
            pt["contato"] = fazenda.get("contato", "")
            if not produtor:
                produtor = fazenda.get("proprietario") or fazenda.get("nome") or ""
        # ⚠️ as faixas entram DEPOIS do add_or_update: o AnnotationStore monta o dicionario do ponto
        # com os campos que ele conhece, e um campo extra passado la' dentro seria descartado.
        pt["ciclos"] = list(segmentos)
        pt["n_faixas"] = len(segmentos)
        pt["levantador"] = self.levantador
        pt["produtor"] = produtor
        pt["gravado_em"] = datetime.now().isoformat(timespec="seconds")
        self.store.save()
        self._ultimo = (int(row), int(col))
        self.atualiza_info()
        return pt, atualizou

    def existente(self, row, col):
        """O que ja' foi gravado neste local: (faixas, produtor). Reabrir em vez de recomecar."""
        if self.store is None:
            return None, None
        p = self.store.find_at(row, col)
        if not p:
            return None, None
        return (p.get("ciclos") or None), p.get("produtor") or None

    def desfaz(self):
        if self.store is None or self._ultimo is None:
            return
        self.store.remove_at(*self._ultimo)
        self._ultimo = None
        self.atualiza_info()

    def exporta(self):
        if self.store is None or not len(self.store):
            QMessageBox.information(self, "Exportar", "Nao ha' pontos para exportar.")
            return
        destino, _ = QFileDialog.getSaveFileName(self, "Exportar pontos", "pontos.csv",
                                                 "CSV (*.csv)")
        if not destino:
            return
        n = self.exporta_para(destino)
        QMessageBox.information(self, "Exportar", f"{n} faixa(s) em\n{destino}")

    def exporta_para(self, destino):
        """CSV com UMA LINHA POR FAIXA. Devolve quantas linhas sairam."""
        # ⚠️ UMA LINHA POR FAIXA, nao por ponto. Quem for usar isto depois quer o par
        # (trecho da curva, cultura); uma linha por ponto obrigaria a desempacotar a lista de novo.
        campos = ["id", "safra", "cultura", "confianca", "mes_ini", "mes_fim", "faixa",
                  "n_faixas", "fazenda", "produtor", "contato", "levantador", "gravado_em",
                  "row", "col", "x", "y"]
        n = 0
        with open(destino, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            for p in self.store.points:
                cic = p.get("ciclos") or []
                for i, s in enumerate(cic, 1):
                    w.writerow({"id": p["id"], "safra": p.get("period"),
                                "cultura": s["cultura"], "confianca": s.get("confianca"),
                                "mes_ini": s.get("mes_ini"),
                                "mes_fim": s.get("mes_fim"), "faixa": i, "n_faixas": len(cic),
                                "fazenda": p.get("fazenda"), "contato": p.get("contato"),
                                "levantador": p.get("levantador"), "produtor": p.get("produtor"),
                                "gravado_em": p.get("gravado_em"),
                                "row": p["row"], "col": p["col"],
                                "x": p.get("x"), "y": p.get("y")})
                    n += 1
        return n


def abre_store(cfg, safra, transform, crs):
    """Um arquivo de pontos por safra -- ver o aviso do topo do modulo."""
    pasta = cfg.pasta_pontos
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"pontos_{safra.replace('/', '_')}.json"
    return AnnotationStore(str(caminho), transform=transform, crs=crs, period=safra)
