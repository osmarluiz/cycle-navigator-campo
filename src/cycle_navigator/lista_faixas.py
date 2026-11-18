# -*- coding: utf-8 -*-
"""A LISTA DAS FAIXAS: uma linha por faixa do ano, ao lado da curva.

⚠️⚠️ PORQUE LISTA E NAO FILA DE BOTOES. As faixas eram "chips" numa fileira horizontal, que mostrava
so' "2. Milho safrinha". Com duas faixas servia; com cinco (hortalica gira quatro, cinco vezes no
ano) a fileira empurrava o produtor e o Gravar para fora da tela, e para saber o periodo ou a
duvida de cada uma era preciso clicar em cada chip. Uma lista cresce para baixo, rola, e cada
linha diz tudo: numero, periodo, cultura, confianca. E' a tabela de atributos do ano.

Clicar na linha poe a faixa em foco (a mesma que acende na curva); o ✕ apaga aquela linha.
"""
import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolButton,
                             QVBoxLayout, QWidget)

from . import estilo


class _Linha(QFrame):
    clicou = pyqtSignal()
    apagar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("faixa_linha")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 4, 3); lay.setSpacing(6)
        self.bola = QLabel("●"); self.bola.setFixedWidth(12)
        self.num = QLabel(""); self.num.setFixedWidth(16)
        self.periodo = QLabel(""); self.periodo.setObjectName("faixa_periodo")
        self.periodo.setFixedWidth(112)
        self.cultura = QLabel("")
        self.conf = QLabel(""); self.conf.setObjectName("faixa_periodo")
        self.x = QToolButton(); self.x.setObjectName("faixa_x")
        self.x.setIcon(qta.icon("mdi6.close", color=estilo.TEXT_2, color_active=estilo.PERIGO))
        self.x.setIconSize(QSize(14, 14))
        self.x.setToolTip("apagar esta faixa")
        self.x.clicked.connect(self.apagar)
        for w in (self.bola, self.num, self.periodo):
            lay.addWidget(w)
        lay.addWidget(self.cultura, 1)
        lay.addWidget(self.conf)
        lay.addWidget(self.x)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicou.emit()
        super().mousePressEvent(ev)

    def acende(self, on):
        self.setProperty("aceso", bool(on))
        self.style().unpolish(self); self.style().polish(self)


class ListaFaixas(QWidget):
    focar = pyqtSignal(int)
    apagar = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(372)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(10, 0, 2, 0); raiz.setSpacing(4)
        topo = QHBoxLayout()
        self.titulo = QLabel("FAIXAS"); self.titulo.setObjectName("rotulo")
        topo.addWidget(self.titulo)
        topo.addStretch(1)
        self.bt_add = QPushButton("faixa"); self.bt_add.setObjectName("ghost")
        self.bt_add.setIcon(qta.icon("mdi6.plus", color=estilo.TEXT))
        self.bt_add.setIconSize(QSize(16, 16))
        self.bt_add.setToolTip("faixa nova (ou arraste na curva, num trecho vazio)")
        topo.addWidget(self.bt_add)
        raiz.addLayout(topo)
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.area.setStyleSheet("background: transparent;")
        dentro = QWidget(); dentro.setAutoFillBackground(False)
        self.col = QVBoxLayout(dentro)
        self.col.setContentsMargins(0, 0, 0, 0); self.col.setSpacing(2)
        self.col.addStretch(1)
        self.area.setWidget(dentro)
        raiz.addWidget(self.area, 1)
        self.linhas = []

    def refaz(self, n):
        """Deixa exatamente `n` linhas (reaproveita as que ja' existem: nada pisca)."""
        while len(self.linhas) > n:
            w = self.linhas.pop()
            self.col.removeWidget(w)
            w.setParent(None); w.deleteLater()
        while len(self.linhas) < n:
            i = len(self.linhas)
            w = _Linha()
            w.clicou.connect(lambda i=i: self.focar.emit(i))
            w.apagar.connect(lambda i=i: self.apagar.emit(i))
            self.col.insertWidget(i, w)
            self.linhas.append(w)
        self.titulo.setText(f"FAIXAS · {n}" if n else "FAIXAS")

    def texto(self, i, periodo, cultura, confianca, aceso, cor=None):
        if not (0 <= i < len(self.linhas)):
            return
        w = self.linhas[i]
        w.num.setText(str(i + 1))
        w.bola.setStyleSheet(f"color:{cor or estilo.TEXT_3};")
        w.periodo.setText(periodo)
        w.cultura.setText(cultura or "—  diga a cultura")
        w.cultura.setStyleSheet("" if cultura else f"color:{estilo.TEXT_3};")
        w.conf.setText(confianca)
        w.acende(aceso)
        if aceso:
            self._mostra(w)

    def foca(self, i):
        for j, w in enumerate(self.linhas):
            w.acende(j == i)
        if 0 <= i < len(self.linhas):
            self._mostra(self.linhas[i])

    def _mostra(self, w):
        """⚠️ so' depois de o layout assentar: a linha recem-criada ainda nao tem posicao, e rolar
        ja' deixava a faixa em foco cortada no fim da lista."""
        QTimer.singleShot(0, lambda: w.parent() is not None and self.area.ensureWidgetVisible(w))
