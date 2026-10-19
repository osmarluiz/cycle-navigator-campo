# -*- coding: utf-8 -*-
"""A JANELA DO CAMPO: uma data por vez, uma forma de ver, e um modo de trabalho de cada vez.

⚠️⚠️ DATA E FORMA DE VER SAO DOIS CAMPOS, NAO UM. A versao anterior juntava tudo num combo so'
("Imagem · NDVI-temporal", "Mês · 2024-01 jan", ...), e quem queria "janeiro em falsa-cor" tinha de
procurar numa lista de dezenove itens de duas naturezas misturadas. Separar devolve a pergunta que a
pessoa realmente faz: QUANDO, e COMO.

⚠️⚠️ O MODO E' EXPLICITO E EXCLUSIVO. Antes, depois de desenhar um poligono, o clique voltava a abrir
o talhao -- nao havia como corrigir um vertice ou o cadastro sem apagar e refazer. Identificar,
desenhar e editar sao tres intencoes diferentes para o MESMO gesto (clicar no mapa), entao tem de
haver um estado visivel dizendo qual esta' valendo. Esc sempre volta para Identificar.

⚠️ SEM PAINEL LATERAL. A tabela de atributos virou janela propria, aberta por botao -- como em
qualquer SIG. Ela era necessaria em talvez um minuto de cada vinte, e enquanto isso comia um quinto
da largura do mapa.
"""
import logging

import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QMainWindow, QPushButton, QSplitter, QToolButton, QVBoxLayout,
                             QWidget)

from . import estilo

log = logging.getLogger(__name__)

IDENTIFICAR, DESENHAR, EDITAR = "identificar", "desenhar", "editar"
DICA = {
    IDENTIFICAR: "clique num talhão para ver o ciclo do ano",
    DESENHAR: "dentro de um imóvel do CAR ou talhão do SAM: parte do contorno dele · fora: clique "
              "põe vértice · duplo-clique fecha · Esc cancela",
    EDITAR: "clique numa fazenda para mover os vértices · num imóvel do CAR (ocre) ou talhão do "
            "SAM (azul) para adotá-lo · duplo-clique abre o cadastro · Esc sai",
}


def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    return f


def _rot(txt):
    l = QLabel(txt)
    l.setObjectName("rotulo")
    return l


class BarraTopo(QWidget):
    """Quando, como, e com qual ferramenta."""

    safraMudou = pyqtSignal(str)
    camadaMudou = pyqtSignal(str)
    dataMudou = pyqtSignal(int)          # AAAAMM
    modoMudou = pyqtSignal(str)
    abrirTabela = pyqtSignal()
    exportar = pyqtSignal()
    carToggled = pyqtSignal(bool)
    samToggled = pyqtSignal(bool)

    def __init__(self, safras, camadas, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        fora = QVBoxLayout(self)
        fora.setContentsMargins(16, 10, 16, 10)
        fora.setSpacing(8)

        # ---------------- fileira 1: quando e como ----------------
        l1 = QHBoxLayout()
        l1.setSpacing(8)
        l1.addWidget(_rot("Safra"))
        self.cb_safra = QComboBox(); self.cb_safra.addItems(safras); self.cb_safra.setFixedWidth(110)
        self.cb_safra.currentTextChanged.connect(self.safraMudou)
        l1.addWidget(self.cb_safra)
        l1.addWidget(_sep())

        l1.addWidget(_rot("Data"))
        self.bt_ant = QToolButton(); self.bt_ant.setFixedSize(32, 32)
        self.bt_ant.setIcon(qta.icon("mdi6.chevron-left", color=estilo.TEXT))
        self.bt_ant.setIconSize(QSize(22, 22))
        self.bt_ant.setToolTip("mês anterior (←)")
        self.cb_data = QComboBox(); self.cb_data.setFixedWidth(130)
        self.cb_data.currentIndexChanged.connect(self._data)
        self.bt_prox = QToolButton(); self.bt_prox.setFixedSize(32, 32)
        self.bt_prox.setIcon(qta.icon("mdi6.chevron-right", color=estilo.TEXT))
        self.bt_prox.setIconSize(QSize(22, 22))
        self.bt_prox.setToolTip("próximo mês (→)")
        l1.addWidget(self.bt_ant); l1.addWidget(self.cb_data); l1.addWidget(self.bt_prox)
        l1.addWidget(_sep())

        l1.addWidget(_rot("Ver como"))
        self.cb_camada = QComboBox(); self.cb_camada.setMinimumWidth(210)
        self.cb_camada.addItems(camadas)
        self.cb_camada.currentTextChanged.connect(self._camada)
        l1.addWidget(self.cb_camada)

        l1.addStretch(1)
        l1.addWidget(_rot("Levantador"))
        self.ed_levantador = QLineEdit()
        self.ed_levantador.setPlaceholderText("seu nome")
        self.ed_levantador.setFixedWidth(180)
        l1.addWidget(self.ed_levantador)
        fora.addLayout(l1)

        # ---------------- fileira 2: ferramentas ----------------
        l2 = QHBoxLayout()
        l2.setSpacing(8)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self._bt_modo = {}
        for modo, txt, ico, dica in (
                (IDENTIFICAR, "Identificar", "mdi6.cursor-default-click-outline",
                 "clicar num talhão abre a curva"),
                (DESENHAR, "Desenhar fazenda", "mdi6.vector-polygon", "traçar um contorno novo"),
                (EDITAR, "Editar fazenda", "mdi6.vector-square-edit",
                 "mover vértices ou abrir o cadastro")):
            b = QPushButton(txt)
            b.setObjectName("modo")
            b.setCheckable(True)
            b.setIcon(qta.icon(ico, color=estilo.TEXT, color_on=estilo.ON_ACCENT))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(dica)
            self.grupo.addButton(b)
            self._bt_modo[modo] = b
            b.clicked.connect(lambda _, m=modo: self.modoMudou.emit(m))
            l2.addWidget(b)
        self._bt_modo[IDENTIFICAR].setChecked(True)

        l2.addWidget(_sep())
        self.bt_tabela = QPushButton("Tabelas")
        self.bt_tabela.setIcon(qta.icon("mdi6.table", color=estilo.TEXT))
        self.bt_tabela.setIconSize(QSize(18, 18))
        self.bt_tabela.clicked.connect(self.abrirTabela)
        l2.addWidget(self.bt_tabela)
        self.bt_exportar = QPushButton("Exportar")
        self.bt_exportar.setIcon(qta.icon("mdi6.export", color=estilo.TEXT))
        self.bt_exportar.setIconSize(QSize(18, 18))
        self.bt_exportar.clicked.connect(self.exportar)
        l2.addWidget(self.bt_exportar)
        l2.addWidget(_sep())
        self.bt_car = QPushButton("CAR")
        self.bt_car.setObjectName("modo")
        self.bt_car.setCheckable(True)
        self.bt_car.setChecked(False)      # desligado por padrao: liga-se para cadastrar
        self.bt_car.setToolTip("mostrar os imóveis do CAR (linhas tracejadas ocre). No modo Editar, "
                               "clicar num deles o adota como fazenda; no modo Desenhar, parte do "
                               "contorno dele")
        self.bt_car.setIcon(qta.icon("mdi6.land-fields", color=estilo.TEXT, color_on=estilo.ON_ACCENT))
        self.bt_car.setIconSize(QSize(18, 18))
        self.bt_car.toggled.connect(self.carToggled)
        self.bt_car.hide()           # so' aparece se a camada carregou
        l2.addWidget(self.bt_car)
        self.bt_sam = QPushButton("SAM")
        self.bt_sam.setObjectName("modo")
        self.bt_sam.setCheckable(True)
        self.bt_sam.setChecked(False)
        self.bt_sam.setToolTip("mostrar os talhões segmentados automaticamente (linhas azuis). "
                               "Editar: clicar num deles o adota; Desenhar: parte do contorno dele")
        self.bt_sam.setIcon(qta.icon("mdi6.vector-selection", color=estilo.TEXT, color_on=estilo.ON_ACCENT))
        self.bt_sam.setIconSize(QSize(18, 18))
        self.bt_sam.toggled.connect(self.samToggled)
        self.bt_sam.hide()
        l2.addWidget(self.bt_sam)

        l2.addStretch(1)
        self.dica = QLabel(DICA[IDENTIFICAR])
        self.dica.setObjectName("dica")
        l2.addWidget(self.dica)
        l2.addSpacing(20)
        self.info = QLabel("")
        self.info.setObjectName("contador")
        l2.addWidget(self.info)
        fora.addLayout(l2)

        self.bt_ant.clicked.connect(lambda: self.passo(-1))
        self.bt_prox.clicked.connect(lambda: self.passo(+1))

    # ---------------- data ----------------
    def lista_datas(self, meses, atual=None):
        self.cb_data.blockSignals(True)
        self.cb_data.clear()
        for m in meses:
            self.cb_data.addItem(_rotulo(m), m)
        if atual is not None:
            i = self.cb_data.findData(atual)
            if i >= 0:
                self.cb_data.setCurrentIndex(i)
        self.cb_data.blockSignals(False)

    def _data(self, *_):
        d = self.cb_data.currentData()
        if d is not None:
            self.dataMudou.emit(int(d))

    def _camada(self, nome):
        self.camadaMudou.emit(nome)

    def data_ativa(self, on):
        """A data so' vale para as camadas mensais; nas do ano ela fica apagada."""
        for w in (self.bt_ant, self.cb_data, self.bt_prox):
            w.setEnabled(on)

    def passo(self, d):
        n = self.cb_data.count()
        if n and self.cb_data.isEnabled():
            self.cb_data.setCurrentIndex((self.cb_data.currentIndex() + d) % n)

    # ---------------- modo ----------------
    def mostra_modo(self, modo):
        b = self._bt_modo.get(modo)
        if b:
            b.setChecked(True)
        self.dica.setText(DICA.get(modo, ""))


def _rotulo(m):
    mes = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
           7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}[m % 100]
    return f"{mes}/{m // 100}"


class JanelaCampo(QMainWindow):
    """Barra em cima, mapa no meio, curva embaixo. Sem painel lateral."""

    cancelou = pyqtSignal()
    confirmou = pyqtSignal()
    desfezVertice = pyqtSignal()

    def __init__(self, view, safras, camadas, painel_ciclo):
        super().__init__()
        self.setWindowTitle("Cycle Navigator — levantamento de campo")
        self.view = view
        self.barra = BarraTopo(safras, camadas)

        div = QSplitter(Qt.Orientation.Vertical)
        div.addWidget(view)
        div.addWidget(painel_ciclo)
        div.setStretchFactor(0, 1)
        div.setStretchFactor(1, 0)
        div.setSizes([600, 360])

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self.barra)
        cl.addWidget(div, 1)
        self.setCentralWidget(central)

        # ⚠️ Os atalhos vivem na JANELA: durante o desenho o foco esta' na cena do pyqtgraph, que
        # nao recebe Esc nem Enter; um atalho de janela chega sempre.
        QShortcut(QKeySequence(Qt.Key.Key_Left), self).activated.connect(
            lambda: self.barra.passo(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self).activated.connect(
            lambda: self.barra.passo(+1))
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.cancelou)
        for k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            QShortcut(QKeySequence(k), self).activated.connect(self.confirmou)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self).activated.connect(self.desfezVertice)

    def para_threads(self):
        """Para as threads de tiles do mapa e ESPERA elas acabarem.

        ⚠️⚠️ O `stop()` do TiledMapView espera 2 s e desiste. Depois de passar meses com as setas,
        ha' centenas de leituras de tile enfileiradas, a thread ainda esta' lendo quando o Qt
        destroi os objetos, e o Qt aborta o processo inteiro ("QThread: Destroyed while thread is
        still running" -> qFatal -> 0xC0000409). Para quem usa, e' o programa "parando de funcionar"
        ao fechar. Aqui se espera o tempo que for preciso: fechar demorar alguns segundos e'
        aceitavel; fechar com crash nao e'.
        """
        if getattr(self, "_parou", False):
            return
        self._parou = True
        try:
            self.view.stop()
        except Exception:
            pass
        for th in (getattr(self.view, "_thread", None), getattr(self.view, "_ov_thread", None)):
            try:
                if th is not None and th.isRunning():
                    th.quit()
                    th.wait()              # sem limite: ate' a thread terminar de verdade
            except Exception:
                pass

    def closeEvent(self, ev):
        self.para_threads()
        super().closeEvent(ev)
