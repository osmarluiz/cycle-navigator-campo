# -*- coding: utf-8 -*-
"""O PAINEL DO LUGAR: duas abas para as duas informacoes de um clique -- o PIXEL e a FAZENDA.

⚠️⚠️ SAO DUAS COISAS E CADA UMA TEM A SUA ABA. O pixel responde "o que foi plantado aqui, mes a
mes" (a serie e as faixas); a fazenda responde "de quem e' esta terra" (o poligono e o cadastro).
Antes a fazenda era uma linha no cabecalho do pixel, e para ver ou mudar o cadastro era preciso
trocar de MODO (Editar) ou abrir a tabela -- e o formulario pulava numa janela por cima do mapa.
Agora o cadastro inteiro mora aqui, editavel no lugar, com as duas acoes que so' fazem sentido
para uma fazenda: redesenhar o contorno e excluir. O modo Editar deixou de existir.

A aba em que se esta' NAO muda sozinha ao clicar noutro lugar: quem esta' conferindo fazendas
continua vendo fazendas; quem esta' levantando pixels continua na serie.
"""
from datetime import date

import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPlainTextEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from . import estilo
from .fazendas import STATUS
from .texto import data_br


def _br(v, casas=1):
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data_iso(txt):
    """'18/11/2026' -> '2026-11-18'; o que ja' for ISO ou nao for data volta como veio."""
    p = str(txt or "").strip().split("/")
    if len(p) == 3 and all(x.isdigit() for x in p):
        return f"{int(p[2]):04d}-{int(p[1]):02d}-{int(p[0]):02d}"
    return str(txt or "").strip()


class PainelFazenda(QWidget):
    """O cadastro da fazenda sob o clique, editavel no lugar."""

    salvou = pyqtSignal(int, dict)
    contorno = pyqtSignal(int)
    excluir = pyqtSignal(int)
    desenhar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fid = None
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(16, 8, 16, 12); raiz.setSpacing(8)
        # ---- sem fazenda aqui
        self.vazio = QWidget()
        vz = QHBoxLayout(self.vazio); vz.setContentsMargins(0, 18, 0, 18)
        self.lb_vazio = QLabel("Nenhuma fazenda cadastrada neste lugar."); self.lb_vazio.setObjectName("vazio")
        self.bt_desenhar = QPushButton("Desenhar uma fazenda")
        self.bt_desenhar.setIcon(qta.icon("mdi6.vector-polygon", color=estilo.TEXT))
        self.bt_desenhar.clicked.connect(self.desenhar)
        vz.addStretch(1); vz.addWidget(self.lb_vazio); vz.addSpacing(12); vz.addWidget(self.bt_desenhar)
        vz.addStretch(1)
        raiz.addWidget(self.vazio)
        # ---- o cadastro
        self.ficha = QWidget()
        col = QVBoxLayout(self.ficha); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(8)
        topo = QHBoxLayout()
        self.titulo = QLabel(""); self.titulo.setObjectName("titulo")
        self.titulo.setTextFormat(Qt.TextFormat.RichText)
        topo.addWidget(self.titulo, 1)
        self.bt_contorno = QPushButton("Editar contorno")
        self.bt_contorno.setIcon(qta.icon("mdi6.vector-square-edit", color=estilo.TEXT))
        self.bt_contorno.setToolTip("mover, criar e apagar vértices do contorno desta fazenda")
        self.bt_excluir = QPushButton("Excluir fazenda"); self.bt_excluir.setObjectName("perigo")
        self.bt_salvar = QPushButton("Salvar cadastro"); self.bt_salvar.setObjectName("cta")
        self.bt_salvar.setIcon(qta.icon("mdi6.check-bold", color=estilo.ON_ACCENT))
        self.bt_salvar.setIconSize(QSize(18, 18))
        for b in (self.bt_contorno, self.bt_excluir, self.bt_salvar):
            topo.addWidget(b)
        col.addLayout(topo)
        campos = QHBoxLayout(); campos.setSpacing(24)
        f1 = QFormLayout(); f2 = QFormLayout()
        for f in (f1, f2):
            f.setVerticalSpacing(8); f.setHorizontalSpacing(12)
            f.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.nome = QLineEdit(); self.nome.setPlaceholderText("ex.: Fazenda do João")
        self.dono = QLineEdit(); self.dono.setPlaceholderText("quem é o dono ou responsável")
        self.contato = QLineEdit(); self.contato.setPlaceholderText("telefone / WhatsApp")
        self.status = QComboBox()
        for s in STATUS:
            self.status.addItem(s.replace("nao", "não").capitalize(), s)
        self.data = QLineEdit(); self.data.setPlaceholderText("dd/mm/aaaa")
        self.obs = QPlainTextEdit(); self.obs.setPlaceholderText("observações da visita")
        self.obs.setMaximumHeight(84)
        f1.addRow("Fazenda", self.nome); f1.addRow("Proprietário", self.dono)
        f1.addRow("Contato", self.contato)
        f2.addRow("Visita", self.status); f2.addRow("Data", self.data)
        campos.addLayout(f1, 3); campos.addLayout(f2, 2)
        dir_ = QVBoxLayout(); dir_.setSpacing(4)
        r = QLabel("OBSERVAÇÕES"); r.setObjectName("rotulo")
        dir_.addWidget(r); dir_.addWidget(self.obs); dir_.addStretch(1)
        campos.addLayout(dir_, 3)
        col.addLayout(campos)
        self.car = QLabel(""); self.car.setObjectName("dica"); self.car.setWordWrap(True)
        self.car.setTextFormat(Qt.TextFormat.RichText)
        self.car.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.car)
        col.addStretch(1)
        raiz.addWidget(self.ficha)
        self.bt_salvar.clicked.connect(self._salva)
        self.bt_contorno.clicked.connect(lambda: self.fid is not None and self.contorno.emit(self.fid))
        self.bt_excluir.clicked.connect(lambda: self.fid is not None and self.excluir.emit(self.fid))
        for w in (self.nome, self.dono, self.contato, self.data):
            w.textEdited.connect(self._mexeu)
            w.returnPressed.connect(self._salva)
        self.status.activated.connect(self._mexeu)
        self.obs.textChanged.connect(self._mexeu)
        self._limpo = None
        self.mostra(None)

    # ---------- o que esta' na tela ----------
    def dados(self):
        return {"nome": self.nome.text().strip(), "proprietario": self.dono.text().strip(),
                "contato": self.contato.text().strip(), "status": self.status.currentData(),
                "data_visita": _data_iso(self.data.text()) or date.today().isoformat(),
                "obs": self.obs.toPlainText().strip()}

    @property
    def mexido(self):
        return self.fid is not None and self._limpo is not None and self.dados() != self._limpo

    def _mexeu(self, *_):
        self.bt_salvar.setEnabled(self.mexido)

    def _salva(self):
        if self.fid is not None and self.mexido:
            self.salvou.emit(self.fid, self.dados())

    def mostra(self, f, foco=False):
        """`f`: o dicionario da fazenda (ou None: nao ha' fazenda neste lugar)."""
        self.fid = f["id"] if f else None
        self.vazio.setVisible(f is None)
        self.ficha.setVisible(f is not None)
        if f is None:
            self._limpo = None
            return
        area = f" &nbsp;<span style='color:{estilo.TEXT_2};font-weight:400'>· {_br(f['area_ha'])} ha</span>" \
            if f.get("area_ha") else ""
        self.titulo.setText((f.get("nome") or "Fazenda sem nome") + area)
        self.obs.blockSignals(True)
        self.nome.setText(f.get("nome") or ""); self.dono.setText(f.get("proprietario") or "")
        self.contato.setText(f.get("contato") or "")
        self.status.setCurrentIndex(max(0, self.status.findData(f.get("status") or STATUS[0])))
        self.data.setText(data_br(f.get("data_visita") or date.today().isoformat(), hora=False))
        self.obs.setPlainText(f.get("obs") or "")
        self.obs.blockSignals(False)
        if f.get("car"):
            from .car import CAMPOS
            partes = [f"{rot}: <b>{_br(f[k]) if isinstance(f[k], float) else f[k]}</b>"
                      for k, rot in CAMPOS if f.get(k) not in (None, "")]
            self.car.setText("Do CAR (só leitura) &nbsp; " + " &nbsp;·&nbsp; ".join(partes))
        self.car.setVisible(bool(f.get("car")))
        self._limpo = self.dados()
        self.bt_salvar.setEnabled(False)
        if foco:
            self.nome.setFocus(); self.nome.selectAll()


class PainelLugar(QWidget):
    """As duas abas. `painel_pixel` e' o PainelCiclo, que continua dono da serie e das faixas."""

    def __init__(self, painel_pixel, parent=None):
        super().__init__(parent)
        self.pixel = painel_pixel
        self.fazenda = PainelFazenda()
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0); raiz.setSpacing(0)
        fita = QHBoxLayout(); fita.setContentsMargins(12, 6, 12, 0); fita.setSpacing(4)
        self.grupo = QButtonGroup(self); self.grupo.setExclusive(True)
        self.abas = {}
        for chave, txt, ico in (("pixel", "Pixel", "mdi6.chart-timeline-variant"),
                                ("fazenda", "Fazenda", "mdi6.vector-polygon")):
            b = QPushButton(txt); b.setObjectName("aba"); b.setCheckable(True)
            b.setIcon(qta.icon(ico, color=estilo.TEXT_2, color_on=estilo.TEXT))
            b.setIconSize(QSize(16, 16))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=chave: self.vai(c))
            self.grupo.addButton(b); self.abas[chave] = b
            fita.addWidget(b)
        fita.addStretch(1)
        raiz.addLayout(fita)
        self.pilha = QStackedWidget()
        self.pilha.addWidget(self.pixel); self.pilha.addWidget(self.fazenda)
        raiz.addWidget(self.pilha, 1)
        self.vai("pixel")

    def vai(self, chave):
        self.abas[chave].setChecked(True)
        self.pilha.setCurrentIndex(0 if chave == "pixel" else 1)

    @property
    def aba(self):
        return "pixel" if self.pilha.currentIndex() == 0 else "fazenda"

    def mostra_fazenda(self, f, foco=False):
        """Atualiza a aba Fazenda e o rotulo dela (o nome da fazenda do lugar, quando ha').
        ⚠️ o que foi digitado e nao salvo e' gravado ao sair do lugar: e' texto de cadastro, e
        perde-lo calado seria pior do que salva-lo sem pedir."""
        if self.fazenda.mexido and (f is None or f["id"] != self.fazenda.fid):
            self.fazenda._salva()
        self.fazenda.mostra(f, foco)
        nome = (f.get("nome") or "sem nome") if f else ""
        self.abas["fazenda"].setText(f"Fazenda · {nome}" if f else "Fazenda")
