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

⚠️ AS FERRAMENTAS DO MAPA FICAM SOBRE O MAPA. Os modos e as camadas de contorno (CAR, SAM) agem no
mapa; numa segunda fileira da barra eles ficavam longe de onde o olho esta' e somavam vinte controles
num bloco so'. Flutuando no canto do mapa, como em qualquer app de mapa, a barra de cima fica com o
QUANDO/COMO/ONDE e quem levanta -- uma fileira.
"""
import logging

import qtawesome as qta
from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut, QStandardItem
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QMainWindow, QPushButton, QSplitter, QToolButton, QVBoxLayout,
                             QWidget)

from . import estilo

log = logging.getLogger(__name__)

IDENTIFICAR, DESENHAR, EDITAR = "identificar", "desenhar", "editar"
DICA = {
    IDENTIFICAR: "Clique num talhão para ver o ano dele  ·  ← → troca o mês",
    DESENHAR: "Clique para pôr vértices · duplo-clique fecha · dentro de um contorno do CAR/SAM, "
              "parte dele · Esc cancela",
    EDITAR: "Clique numa fazenda para mover os vértices · num contorno do CAR/SAM para adotá-lo · "
            "duplo-clique abre o cadastro · Esc sai",
}


def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    return f


def _rot(txt):
    l = QLabel(txt)
    l.setObjectName("rotulo")
    return l


def _icone(nome, cor=None, **kw):
    return qta.icon(nome, color=cor or estilo.TEXT, **kw)


class BarraTopo(QWidget):
    """Quando, como, onde -- e quem levanta. As ferramentas do mapa moram em `self.ferramentas`,
    que a janela poe flutuando sobre o mapa (os sinais continuam saindo daqui)."""

    safraMudou = pyqtSignal(str)
    camadaMudou = pyqtSignal(str)
    dataMudou = pyqtSignal(int)          # AAAAMM
    modoMudou = pyqtSignal(str)
    abrirTabela = pyqtSignal()
    abrirAnalise = pyqtSignal()
    abrirSugestoes = pyqtSignal()
    exportar = pyqtSignal()
    carToggled = pyqtSignal(bool)
    samToggled = pyqtSignal(bool)
    buscou = pyqtSignal(str)
    ondeEstou = pyqtSignal()
    verLevantados = pyqtSignal()

    def __init__(self, safras, camadas, parent=None, camadas_ano=()):
        super().__init__(parent)
        self.setObjectName("topbar")
        l1 = QHBoxLayout(self)
        l1.setContentsMargins(14, 10, 14, 10)
        l1.setSpacing(8)

        # ---------------- marca ----------------
        logo = QLabel()
        logo.setPixmap(QPixmap(estilo.ICONE_APP).scaled(
            28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        l1.addWidget(logo)
        nome = QLabel("Cycle Navigator")
        nome.setObjectName("marca")
        l1.addWidget(nome)
        self.lb_nome = nome              # some em janela estreita (ver resizeEvent)
        l1.addSpacing(6)
        l1.addWidget(_sep())

        # ---------------- quando ----------------
        l1.addWidget(_rot("Safra"))
        self.cb_safra = QComboBox(); self.cb_safra.addItems(safras); self.cb_safra.setFixedWidth(104)
        self.cb_safra.setToolTip("ano-safra: outubro a setembro")
        self.cb_safra.currentTextChanged.connect(self.safraMudou)
        l1.addWidget(self.cb_safra)

        self.bt_ant = QToolButton(); self.bt_ant.setFixedSize(32, 32)
        self.bt_ant.setIcon(_icone("mdi6.chevron-left"))
        self.bt_ant.setIconSize(QSize(22, 22))
        self.bt_ant.setToolTip("mês anterior (←)")
        self.cb_data = QComboBox(); self.cb_data.setFixedWidth(116)
        self.cb_data.setToolTip("o mês que o mapa mostra")
        self.cb_data.currentIndexChanged.connect(self._data)
        self.bt_prox = QToolButton(); self.bt_prox.setFixedSize(32, 32)
        self.bt_prox.setIcon(_icone("mdi6.chevron-right"))
        self.bt_prox.setIconSize(QSize(22, 22))
        self.bt_prox.setToolTip("próximo mês (→)")
        l1.addSpacing(4)
        l1.addWidget(self.bt_ant); l1.addWidget(self.cb_data); l1.addWidget(self.bt_prox)

        # ---------------- como ----------------
        self.cb_camada = QComboBox()
        # ⚠️ A BARRA TEM DE CABER NA TELA. O combo pedia a largura do item mais comprido e a busca
        # 250 px fixos: a barra somava 1601 px de minimo, a tela do MacBook Air tem 1470, e a
        # janela inteira ficava mais larga que a tela (o lado direito cortado). Minimos pequenos,
        # e quem sobra espaco e' a busca.
        self.cb_camada.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cb_camada.setMinimumContentsLength(12)
        self.cb_camada.setMinimumWidth(150); self.cb_camada.setMaximumWidth(230)
        self.cb_camada.view().setMinimumWidth(240)
        self.cb_camada.setToolTip("como o mapa mostra a imagem")
        self._popula_camadas(camadas, camadas_ano)
        self.cb_camada.currentTextChanged.connect(self._camada)
        l1.addSpacing(4)
        l1.addWidget(self.cb_camada)

        l1.addStretch(1)

        # ---------------- onde ----------------
        caixa = QWidget()
        cl = QHBoxLayout(caixa); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)
        self.ed_busca = QLineEdit()
        self.ed_busca.setObjectName("busca")
        self.ed_busca.setPlaceholderText("Buscar lugar…")
        self.ed_busca.setMinimumWidth(130)
        self.ed_busca.setMaximumWidth(360)
        self.ed_busca.setClearButtonEnabled(True)
        self.ed_busca.setToolTip("município · código do CAR · nome de fazenda · coordenada "
                                 "(cole do celular: -15.79, -47.88)   ⌘F")
        self.ed_busca.returnPressed.connect(lambda: self.buscou.emit(self.ed_busca.text().strip()))
        lupa = QLabel(self.ed_busca)
        lupa.setPixmap(_icone("mdi6.magnify", estilo.TEXT_3).pixmap(18, 18))
        lupa.move(11, 7)
        lupa.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        cl.addWidget(self.ed_busca)
        l1.addWidget(caixa, 8)        # a sobra da barra vai para a busca, nao para o vazio
        self.bt_gps = QToolButton()
        self.bt_gps.setObjectName("ghost")
        self.bt_gps.setFixedSize(34, 34)
        self.bt_gps.setIcon(_icone("mdi6.crosshairs-gps"))
        self.bt_gps.setIconSize(QSize(20, 20))
        self.bt_gps.setToolTip("Onde estou: centra o mapa na sua posição")
        self.bt_gps.clicked.connect(self.ondeEstou)
        l1.addWidget(self.bt_gps)
        l1.addWidget(_sep())

        # ---------------- registros ----------------
        # ⚠️ a contagem e' um BOTAO: clicar enquadra todos os talhoes ja' levantados da safra.
        self.info = QPushButton("")
        self.info.setObjectName("contagem")
        self.info.setIcon(_icone("mdi6.map-marker-multiple-outline"))
        self.info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info.setToolTip("talhões já levantados nesta safra — clique para ver todos no mapa")
        self.info.clicked.connect(self.verLevantados)
        l1.addWidget(self.info)
        self.bt_tabela = QToolButton()
        self.bt_tabela.setObjectName("ghost")
        self.bt_tabela.setFixedSize(34, 34)
        self.bt_tabela.setIcon(_icone("mdi6.table"))
        self.bt_tabela.setIconSize(QSize(20, 20))
        self.bt_tabela.setToolTip("Tabelas: fazendas e talhões levantados")
        self.bt_tabela.clicked.connect(self.abrirTabela)
        l1.addWidget(self.bt_tabela)
        self.bt_analise = QToolButton()
        self.bt_analise.setObjectName("ghost")
        self.bt_analise.setFixedSize(34, 34)
        self.bt_analise.setIcon(_icone("mdi6.chart-box-outline"))
        self.bt_analise.setIconSize(QSize(20, 20))
        self.bt_analise.setToolTip("Análise: tudo o que foi levantado na safra, e o que conferir")
        self.bt_analise.clicked.connect(self.abrirAnalise)
        l1.addWidget(self.bt_analise)
        self.bt_sugestao = QToolButton()
        self.bt_sugestao.setObjectName("ghost")
        self.bt_sugestao.setFixedSize(34, 34)
        self.bt_sugestao.setIcon(_icone("mdi6.lightbulb-on-outline"))
        self.bt_sugestao.setIconSize(QSize(20, 20))
        self.bt_sugestao.setToolTip("Sugestões: escreva o que quer mudar; a tela vai junto")
        self.bt_sugestao.clicked.connect(self.abrirSugestoes)
        l1.addWidget(self.bt_sugestao)
        self.bt_exportar = QToolButton()
        self.bt_exportar.setObjectName("ghost")
        self.bt_exportar.setFixedSize(34, 34)
        self.bt_exportar.setIcon(_icone("mdi6.export"))
        self.bt_exportar.setIconSize(QSize(20, 20))
        self.bt_exportar.setToolTip("Exportar os talhões da safra (GeoPackage, Shapefile ou CSV)")
        self.bt_exportar.clicked.connect(self.exportar)
        l1.addWidget(self.bt_exportar)
        l1.addWidget(_sep())

        # ---------------- quem ----------------
        self.ed_levantador = QLineEdit()
        self.ed_levantador.setPlaceholderText("seu nome")
        self.ed_levantador.setMinimumWidth(96); self.ed_levantador.setMaximumWidth(150)
        self.ed_levantador.setToolTip("quem está levantando: vai junto com cada talhão gravado")
        self.ed_levantador.addAction(_icone("mdi6.account-outline", estilo.TEXT_2),
                                     QLineEdit.ActionPosition.LeadingPosition)
        l1.addWidget(self.ed_levantador)

        self._monta_ferramentas()
        self.bt_ant.clicked.connect(lambda: self.passo(-1))
        self.bt_prox.clicked.connect(lambda: self.passo(+1))

    def resizeEvent(self, ev):
        # janela estreita: o nome do programa da' lugar aos controles (o icone fica)
        self.lb_nome.setVisible(self.width() >= 1380)
        super().resizeEvent(ev)

    def _popula_camadas(self, mes, ano):
        """Mes e ano no mesmo combo, com cabecalhos que nao se selecionam."""
        m = self.cb_camada.model()
        for titulo, nomes in (("IMAGEM DO MÊS", mes), ("RESUMO DO ANO", ano)):
            if not nomes:
                continue
            cab = QStandardItem(titulo)
            cab.setEnabled(False)
            cab.setSelectable(False)
            m.appendRow(cab)
            for n in nomes:
                self.cb_camada.addItem(n)
        self.cb_camada.setCurrentIndex(1)

    def _monta_ferramentas(self):
        """O bloco que flutua no canto do mapa: modos | contornos."""
        self.ferramentas = QWidget()
        self.ferramentas.setObjectName("flutuante")
        self.ferramentas.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self.ferramentas)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self._bt_modo = {}
        for modo, txt, ico, dica in (
                (IDENTIFICAR, "Identificar", "mdi6.cursor-default-click-outline",
                 "clicar num talhão abre o ano dele (Esc)"),
                (DESENHAR, "Desenhar", "mdi6.vector-polygon", "traçar o contorno de uma fazenda"),
                (EDITAR, "Editar", "mdi6.vector-square-edit",
                 "mover vértices, adotar um contorno do CAR/SAM, abrir o cadastro")):
            b = QPushButton(txt)
            b.setCheckable(True)
            b.setIcon(qta.icon(ico, color=estilo.TEXT, color_on=estilo.ON_ACCENT))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(dica)
            self.grupo.addButton(b)
            self._bt_modo[modo] = b
            b.clicked.connect(lambda _, m=modo: self.modoMudou.emit(m))
            lay.addWidget(b)
        self._bt_modo[IDENTIFICAR].setChecked(True)
        lay.addWidget(_sep())

        def camada(txt, ico, dica, sinal):
            b = QPushButton(txt)
            b.setObjectName("camada")
            b.setCheckable(True)
            b.setIcon(qta.icon(ico, color=estilo.TEXT))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(dica)
            b.toggled.connect(sinal)
            b.hide()                      # so' aparece se a camada carregou
            lay.addWidget(b)
            return b
        self.bt_car = camada("CAR", "mdi6.land-fields",
                             "imóveis do CAR (tracejado ocre): clique num deles para ver o que o "
                             "cadastro diz", self.carToggled)
        self.bt_sam = camada("Talhões", "mdi6.vector-selection",
                             "talhões recortados automaticamente (linhas azuis)", self.samToggled)

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

    def mostra_data(self, m):
        """Poe o combo no mes m sem disparar nada (quem mudou o mes ja' sabe)."""
        i = self.cb_data.findData(m)
        if i >= 0 and i != self.cb_data.currentIndex():
            self.cb_data.setCurrentIndex(i)

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
        if hasattr(self, "dica"):
            self.dica.setText(DICA.get(modo, ""))
            self.dica.adjustSize()


def _rotulo(m):
    mes = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
           7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}[m % 100]
    return f"{mes}/{m // 100}"


class _Ancora(QObject):
    """Reposiciona os flutuantes quando o mapa muda de tamanho."""

    def __init__(self, alvo, fn):
        super().__init__(alvo)
        self._fn = fn
        alvo.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Resize:
            self._fn()
        return False


class JanelaCampo(QMainWindow):
    """Barra em cima, mapa no meio (com as ferramentas flutuando), curva embaixo."""

    cancelou = pyqtSignal()
    confirmou = pyqtSignal()
    desfezVertice = pyqtSignal()
    gravarAtalho = pyqtSignal()

    ALTURA_FECHADO = 96          # o painel de baixo antes do primeiro clique: so' os passos

    def __init__(self, view, safras, camadas, painel_ciclo, camadas_ano=()):
        super().__init__()
        self.setWindowTitle("Cycle Navigator — levantamento de campo")
        self.view = view
        self.painel = painel_ciclo
        self.barra = BarraTopo(safras, camadas, camadas_ano=camadas_ano)

        # ---------------- sobre o mapa ----------------
        f = self.barra.ferramentas
        f.setParent(view)
        f.adjustSize()
        self.barra.dica = QLabel(DICA[IDENTIFICAR], view)
        self.barra.dica.setObjectName("pilula")
        self.barra.dica.adjustSize()
        self.aviso = QLabel("", view)
        self.aviso.setObjectName("aviso")
        self.aviso.hide()
        self._t_aviso = QTimer(self)
        self._t_aviso.setSingleShot(True)
        self._t_aviso.timeout.connect(self.aviso.hide)
        _Ancora(view, self._posiciona)

        self.div = QSplitter(Qt.Orientation.Vertical)
        self.div.addWidget(view)
        self.div.addWidget(painel_ciclo)
        self.div.setStretchFactor(0, 1)
        self.div.setStretchFactor(1, 0)
        self.div.setCollapsible(0, False)
        self.div.setCollapsible(1, False)
        self.div.setSizes([860, self.ALTURA_FECHADO])
        self._aberto = False

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self.barra)
        cl.addWidget(self.div, 1)
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
        QShortcut(QKeySequence.StandardKey.Find, self).activated.connect(
            lambda: (self.barra.ed_busca.setFocus(), self.barra.ed_busca.selectAll()))
        QShortcut(QKeySequence.StandardKey.Save, self).activated.connect(self.gravarAtalho)

    # ---------------- flutuantes ----------------
    def _posiciona(self):
        v, m = self.view, 14
        self.barra.ferramentas.adjustSize()
        self.barra.ferramentas.move(m, m)
        self.barra.ferramentas.raise_()
        d = self.barra.dica
        d.adjustSize()
        d.move(m, v.height() - d.height() - m)
        d.raise_()
        if self.aviso.isVisible():
            self.aviso.adjustSize()
            self.aviso.move((v.width() - self.aviso.width()) // 2, 18 + self.barra.ferramentas.height())
            self.aviso.raise_()

    def avisa(self, texto, tipo="ok", ms=2600):
        """Um recado curto sobre o mapa que some sozinho: 'Gravado', 'Sem localização'..."""
        self.aviso.setText(texto)
        self.aviso.setProperty("tipo", tipo)
        self.aviso.style().unpolish(self.aviso)
        self.aviso.style().polish(self.aviso)
        self.aviso.show()
        self._posiciona()
        self._t_aviso.start(ms)

    # ---------------- painel de baixo ----------------
    def abre_painel(self):
        """No primeiro talhao aberto o painel cresce; antes disso o mapa ocupa quase tudo."""
        if self._aberto:
            return
        self._aberto = True
        total = sum(self.div.sizes())
        alt = max(330, min(400, int(total * 0.42)))
        self.div.setSizes([total - alt, alt])

    def fecha_painel(self):
        self._aberto = False
        total = sum(self.div.sizes())
        self.div.setSizes([total - self.ALTURA_FECHADO, self.ALTURA_FECHADO])

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
        # ⚠️ as janelas soltas (tabelas, analise) fecham junto: aberta sozinha, uma delas mantinha
        # o programa vivo sem janela principal.
        for w in getattr(self, "filhas", ()):
            w.close()
        self.para_threads()
        super().closeEvent(ev)
