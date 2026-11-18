# -*- coding: utf-8 -*-
"""O CICLO DO ANO: o agricultor conta o que foi plantado em cada parte, uma faixa por vez.

⚠️⚠️ AS BORDAS GRUDAM NO MES. A serie e' mensal: "meio de fevereiro" nao existe no dado, e deixar a
borda parar ali promete uma precisao que o dado nao tem -- e ainda faz duas pessoas gravarem limites
diferentes para a mesma resposta. Toda borda cai no mes inteiro mais proximo.

⚠️ AS FAIXAS VEM SUGERIDAS PELO MOTOR, MAS A CULTURA VEM VAZIA. As BORDAS vem de `sos_k`/`eos_k` do
pheno_engine porque ninguem desenha duas bordas por talhao com o produtor esperando, e porque assim
a resposta do agricultor e' uma resposta SOBRE A LEITURA DO MOTOR. A CULTURA vem vazia porque campo
pre-preenchido e' aceito sem ler: deixar "Soja" produziria talhoes de soja que ninguem afirmou.
Os botoes de cultura de um clique NAO mudam isso: nada fica escolhido ate' alguem clicar.

⚠️ TODAS AS FAIXAS APARECEM, UMA EM FOCO. A versao anterior pintava so' a faixa em foco; as outras
ficavam a 10% de cinza, e quem olhava a curva via um ciclo onde o motor tinha achado dois. Agora cada
faixa tem a cor da sua cultura (cinza enquanto nao tem nome) e um rotulo em cima; a em foco e' a
unica com borda grossa e a unica que se arrasta.

⚠️ O MES DO MAPA APARECE NA CURVA, E A CURVA LEVA O MAPA. Uma linha tracejada marca o mes que o mapa
esta' mostrando; clicar num mes da curva leva o mapa ate' ele. "Como estava esse talhao em
janeiro?" e' a pergunta mais comum na conversa com o produtor, e antes exigia achar janeiro num
combo la' em cima.

⚠️ O PAINEL FOI ENXUGADO DE PROPOSITO. O ponto de operacao do motor (piso/subida) mora num menu: e'
ajuste de especialista, usado uma vez por sessao, e nao pode disputar atencao com a cultura, que se
escolhe a cada talhao.
"""
import logging

import numpy as np
import pheno_engine
import pyqtgraph as pg
import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QCompleter, QHBoxLayout, QLabel, QLineEdit,
                             QMenu, QPushButton, QSlider, QToolButton, QVBoxLayout, QWidget,
                             QWidgetAction)

from . import estilo
from .lista_faixas import ListaFaixas

log = logging.getLogger(__name__)

MES_CURTO = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
             7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}

# ⚠️ A CONFIANCA E' POR FAIXA, NAO POR PONTO. O produtor costuma ter certeza da lavoura principal e
# duvida da segunda. Uma confianca unica obrigaria a rebaixar a resposta inteira por causa da parte
# fraca, ou inflar a parte fraca por causa da forte -- as duas saidas sao mentira.
CONFIANCA = ["certo", "acho que", "nao sei"]
CONF_ROTULO = {"certo": "Certo", "acho que": "Acho que", "nao sei": "Não sei"}
ALFA = {"certo": 110, "acho que": 70, "nao sei": 40}
COR_FOCO = estilo.FOCO
COR_FUNDO = estilo.TEXT_3
COR_CURVA = estilo.ACCENT

# as culturas que ganham botao de um clique, nesta ordem, quando ninguem gravou nada ainda; depois
# a ordem passa a ser a das mais gravadas
RAPIDAS = ["Soja", "Milho safrinha", "Milho", "Feijão", "Sorgo", "Algodão", "Pastagem"]
N_RAPIDAS = 7


def ndvi_da_curva(curva):
    """(T, bandas) -> (T,) NDVI. Bandas do cubo: 1=B 2=G 3=R 4=NIR."""
    c = np.asarray(curva, float)
    red, nir = c[:, 2], c[:, 3]
    return (nir - red) / (nir + red + 1e-6)


def rotulo_mes(m):
    return f"{MES_CURTO[m % 100]}/{str(m // 100)[2:]}"


def ciclos_do_motor(nd12, piso=0.08, subida=0.0):
    """Ciclos de UM ano-safra: [(sos, pico, eos), ...] em indice 0..11, e o n de ciclos."""
    arr = np.asarray(nd12, np.float32).reshape(1, 1, -1)
    f = pheno_engine.derive_feat(arr, floor=float(piso), slope_min=float(subida))
    val = lambda k: float(np.ravel(f[k])[0])
    T = arr.shape[2] - 1
    out = []
    for k in (1, 2, 3):
        pico = val(f"m{k}")
        if not np.isfinite(pico):
            continue
        sos, eos = val(f"sos{k}"), val(f"eos{k}")
        out.append((int(round(sos if np.isfinite(sos) else 0)), int(round(pico)),
                    int(round(eos if np.isfinite(eos) else T))))
    return out, val("ncyc")


def deteccao(nd, meses, piso=0.08, subida=0.0):
    """Ciclos de TODOS os anos-safra completos, em indice da serie inteira.

    ⚠️ Fatia por ano-safra antes de chamar o motor. O `derive_feat` tem os meses da seca FIXOS nos
    indices 8..12, ou seja, pressupoe doze meses a partir de outubro; chamado com 54 meses ele nao
    daria erro -- daria numero, e errado.
    """
    pos = {m: i for i, m in enumerate(meses)}
    out = []
    for m in meses:
        if m % 100 != 10:
            continue
        ano = m // 100
        janela = ([ano * 100 + x for x in (10, 11, 12)] +
                  [(ano + 1) * 100 + x for x in range(1, 10)])
        if not all(x in pos for x in janela):
            continue
        idx = [pos[x] for x in janela]
        ciclos, ncyc = ciclos_do_motor(np.asarray(nd)[idx], piso, subida)
        for sos, pico, eos in ciclos:
            out.append((idx[sos], idx[eos], idx[pico], ncyc))
    return out


def _rot(txt):
    l = QLabel(txt)
    l.setObjectName("rotulo")
    return l


class Segmentado(QWidget):
    """Botoes encostados, um marcado: [Safra | 2 anos | Tudo]."""

    escolheu = pyqtSignal(object)

    def __init__(self, opcoes, parent=None):
        super().__init__(parent)
        self.setObjectName("seg")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.bts = {}
        for valor, txt, dica in opcoes:
            b = QPushButton(txt)
            b.setCheckable(True)
            b.setToolTip(dica)
            b.clicked.connect(lambda _, v=valor: self.escolheu.emit(v))
            self.grupo.addButton(b)
            self.bts[valor] = b
            lay.addWidget(b)

    def marca(self, valor):
        b = self.bts.get(valor)
        if b is not None:
            b.setChecked(True)

    def valor(self):
        for v, b in self.bts.items():
            if b.isChecked():
                return v
        return None


class PainelCiclo(QWidget):
    """A curva do talhao clicado e as faixas que o produtor for contando."""

    gravar = pyqtSignal(list)
    mesEscolhido = pyqtSignal(int)      # AAAAMM clicado na curva -> o mapa vai ate' ele
    fonteMudou = pyqtSignal(str)        # "talhao" | "pixel"
    recado = pyqtSignal(str, str)       # (texto, tipo) para o aviso sobre o mapa
    abriu = pyqtSignal()

    def __init__(self, culturas_conhecidas=None, parent=None, cores=None, mais_usadas=None):
        super().__init__(parent)
        self._conhecidas = culturas_conhecidas or (lambda: [])
        self._mais_usadas = mais_usadas or (lambda: [])
        self.cores = {k.lower(): v for k, v in (cores or {}).items()}
        self.meses = []
        self.rc = None
        self.curva = None
        self.nd = None
        self._faixas = []
        self._foco = -1
        self._picos = []
        self._sug = []
        self._tocado = False
        self._ajustando = False       # trava anti-recursao do grude no mes
        self._mes_mapa = None

        lay = QVBoxLayout(self)
        self.setObjectName("rodape")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay.setContentsMargins(16, 10, 16, 12)
        lay.setSpacing(8)

        # ---------------- vazio: os tres passos ----------------
        # ⚠️ ESTADO VAZIO. Sem talhao aberto, dois graficos em branco nao dizem nada e parecem
        # defeito -- e ocupavam metade da tela. Agora o painel encolhe e mostra o caminho inteiro.
        self.vazio = QWidget()
        vz = QHBoxLayout(self.vazio)
        vz.setContentsMargins(4, 6, 4, 6)
        vz.setSpacing(10)
        vz.addStretch(1)
        for i, txt in enumerate(("Clique num talhão no mapa",
                                 "Diga o que foi plantado em cada faixa do ano",
                                 "Gravar"), 1):
            n = QLabel(str(i)); n.setObjectName("num")
            t = QLabel(txt); t.setObjectName("passo")
            vz.addWidget(n); vz.addWidget(t)
            if i < 3:
                seta = QLabel()
                seta.setPixmap(qta.icon("mdi6.arrow-right", color=estilo.TEXT_3).pixmap(18, 18))
                vz.addSpacing(6); vz.addWidget(seta); vz.addSpacing(6)
        vz.addStretch(1)
        lay.addWidget(self.vazio, 1)

        # ---------------- cabecalho ----------------
        cab = self._cab = QHBoxLayout()
        cab.setSpacing(10)
        txts = QVBoxLayout(); txts.setSpacing(0)
        self.titulo = QLabel("")
        self.titulo.setObjectName("h2")
        self.subtitulo = QLabel("")
        self.subtitulo.setObjectName("subtitulo")
        # ⚠️ RichText explicito: o Qt adivinha o formato pelo comeco do texto, e um subtitulo que
        # comeca por palavra comum era tratado como texto puro -- os "&nbsp;" apareciam na tela.
        self.titulo.setTextFormat(Qt.TextFormat.RichText)
        self.subtitulo.setTextFormat(Qt.TextFormat.RichText)
        txts.addWidget(self.titulo); txts.addWidget(self.subtitulo)
        cab.addLayout(txts, 1)
        self.seg_fonte = Segmentado([
            ("pixel", "Pixel", "a curva é a do pixel clicado (4,8 m)"),
            ("talhao", "Média do talhão", "a curva é a MÉDIA do talhão pronto sob o clique: menos "
                                          "ruído que um pixel só")])
        self.seg_fonte.escolheu.connect(lambda v: self.fonteMudou.emit(str(v)))
        cab.addWidget(self.seg_fonte)
        self.seg_janela = Segmentado([(12, "Safra", "os 12 meses da safra (out → set)"),
                                      (24, "2 anos", "24 meses"),
                                      (0, "Tudo", "a série inteira")])
        self.seg_janela.escolheu.connect(self.define_janela)
        self.seg_janela.marca(12)
        cab.addWidget(self.seg_janela)
        # ⚠️ piso/subida saem para um menu: ajuste de especialista nao pode disputar espaco com o
        # campo que se usa a cada talhao.
        self.bt_ajustes = QToolButton()
        self.bt_ajustes.setObjectName("ghost")
        self.bt_ajustes.setFixedSize(32, 32)
        self.bt_ajustes.setToolTip("ajustar a detecção de ciclos (especialista)")
        self.bt_ajustes.setIcon(qta.icon("mdi6.tune-variant", color=estilo.TEXT_2))
        self.bt_ajustes.setIconSize(QSize(18, 18))
        self.bt_ajustes.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bt_ajustes.setMenu(self._menu_ajustes())
        cab.addWidget(self.bt_ajustes)
        lay.addLayout(cab)

        # ---------------- graficos ----------------
        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(150)
        self.plot.setBackground(estilo.PANEL)
        # o botao "A" de auto-range aparece sozinho quando o auto-range e' desligado; aqui o zoom e'
        # da janela de meses, nao do usuario, entao o botao so' confunde
        self.plot.getPlotItem().hideButtons()
        self.plot.setLabel("left", "vigor (NDVI)", color=estilo.TEXT_3)
        self.plot.showGrid(x=False, y=True, alpha=0.12)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setYRange(0, 1.05)
        self.plot.getPlotItem().setMenuEnabled(False)
        for ax in ("left", "bottom"):
            a = self.plot.getAxis(ax)
            a.setPen(pg.mkPen(estilo.BORDER_STRONG))
            a.setTextPen(pg.mkPen(estilo.TEXT_2))
        self.plot.setCursor(Qt.CursorShape.PointingHandCursor)
        meio = QHBoxLayout(); esq = QVBoxLayout(); meio.addLayout(esq, 1)
        lay.addLayout(meio, 1)
        esq.addWidget(self.plot, 1)

        self.geral = pg.PlotWidget()
        self.geral.setFixedHeight(40)
        self.geral.setBackground(estilo.PANEL)
        self.geral.getPlotItem().hideButtons()
        self.geral.setMouseEnabled(x=False, y=False)
        self.geral.hideAxis("left")
        self.geral.getAxis("bottom").setPen(pg.mkPen(estilo.BORDER))
        self.geral.getAxis("bottom").setTextPen(pg.mkPen(estilo.TEXT_3))
        self.geral.getPlotItem().setMenuEnabled(False)
        self.geral.setYRange(0, 1)
        self.geral.setToolTip("a série inteira: arraste a janela para ver outros anos")
        self.janela = pg.LinearRegionItem(brush=pg.mkBrush(143, 196, 82, 38),
                                          pen=pg.mkPen(COR_CURVA, width=2),
                                          hoverBrush=pg.mkBrush(143, 196, 82, 70))
        self.janela.setZValue(10)
        [li.setCursor(Qt.CursorShape.SizeHorCursor) for li in self.janela.lines]
        self.geral.addItem(self.janela)
        self.janela.sigRegionChanged.connect(self._janela_mudou)
        esq.addWidget(self.geral)
        self.lista = ListaFaixas()          # uma linha por faixa (ver lista_faixas.py)
        self.lista.focar.connect(self._foca); self.lista.apagar.connect(self._apaga)
        meio.addWidget(self.lista)

        # ---------------- fileira 1: as faixas, quem respondeu, gravar ----------------
        f1 = self._f1 = QHBoxLayout()
        f1.setSpacing(6)
        self.bt_add = self.lista.bt_add
        f1.addStretch(1)
        f1.addWidget(_rot("Produtor"))
        self.ed_produtor = QLineEdit()
        self.ed_produtor.setPlaceholderText("quem respondeu")
        self.ed_produtor.setFixedWidth(190)
        f1.addWidget(self.ed_produtor)
        self.bt_gravar = QPushButton("Gravar")
        self.bt_gravar.setObjectName("cta")
        self.bt_gravar.setIcon(qta.icon("mdi6.check-bold", color=estilo.ON_ACCENT))
        self.bt_gravar.setIconSize(QSize(18, 18))
        self.bt_gravar.setMinimumWidth(124)
        self.bt_gravar.setToolTip("gravar o talhão (⌘S)")
        self.bt_gravar.setDefault(True)
        f1.addWidget(self.bt_gravar)
        lay.addLayout(f1)

        # ---------------- fileira 2: a faixa em foco ----------------
        f2 = self._f2 = QHBoxLayout()
        f2.setSpacing(6)
        self.lb_faixa = QLabel("—")
        self.lb_faixa.setMinimumWidth(170)
        f2.addWidget(self.lb_faixa)
        self.rapidas = QHBoxLayout()
        self.rapidas.setSpacing(6)
        f2.addLayout(self.rapidas)
        # ⚠️ combo EDITAVEL com autocompletar: lista fechada nao cobre o que o campo traz
        # ("sorgo forrageiro", "consorcio"); texto cru puro produz "soja"/"Soja"/"SOJA" como tres
        # culturas na hora de somar.
        self.ed_cultura = QComboBox()
        self.ed_cultura.setEditable(True)
        self.ed_cultura.setMinimumWidth(170)
        self.ed_cultura.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.ed_cultura.lineEdit().setPlaceholderText("outra cultura…")
        f2.addWidget(self.ed_cultura, 1)
        f2.addSpacing(6)
        self.seg_conf = Segmentado([(c, CONF_ROTULO[c], "o quanto o produtor tem certeza desta "
                                                        "faixa") for c in CONFIANCA])
        self.seg_conf.marca(CONFIANCA[0])
        f2.addWidget(self.seg_conf)
        lay.addLayout(f2)

        self.bt_add.clicked.connect(self._add_manual)
        self.bt_gravar.clicked.connect(self._emite)
        self.ed_cultura.currentTextChanged.connect(self._foco_editado)
        self.seg_conf.escolheu.connect(lambda _v: self._foco_editado())

        # ⚠️ A FAIXA SE SELECIONA CLICANDO NELA, E SE CRIA ARRASTANDO NA CURVA. Antes so' dava pelo
        # chip, e o chip fica longe do desenho: a pessoa olha para a curva, aponta para a corcova
        # que o produtor esta' descrevendo, e o clique ali tem de ser o que seleciona. Arrastar no
        # vazio desenha uma faixa nova -- o mesmo gesto de marcar um trecho em qualquer lugar.
        self.plot.scene().sigMouseClicked.connect(self._clicou_curva)
        self._vb().mouseDragEvent = self._arrastou_curva
        self._novo_reg = None
        self._habilita(False)

    def _vb(self):
        return self.plot.getPlotItem().vb

    def _menu_ajustes(self):
        m = QMenu(self)
        w = QWidget()
        g = QVBoxLayout(w)
        g.addWidget(QLabel("<b>Detecção de ciclos</b>"))
        g.addWidget(QLabel(f"<span style='color:{estilo.TEXT_2}'>o que o motor conta como um "
                           "ciclo</span>"))
        l1 = QHBoxLayout(); l1.addWidget(QLabel("piso de amplitude"))
        self.sl_piso = QSlider(Qt.Orientation.Horizontal)
        self.sl_piso.setRange(2, 40); self.sl_piso.setValue(8); self.sl_piso.setFixedWidth(150)
        self.lb_piso = QLabel("0.08")
        l1.addWidget(self.sl_piso); l1.addWidget(self.lb_piso); g.addLayout(l1)
        l2 = QHBoxLayout(); l2.addWidget(QLabel("subida mínima    "))
        self.sl_sub = QSlider(Qt.Orientation.Horizontal)
        self.sl_sub.setRange(0, 25); self.sl_sub.setValue(0); self.sl_sub.setFixedWidth(150)
        self.lb_sub = QLabel("0.00")
        l2.addWidget(self.sl_sub); l2.addWidget(self.lb_sub); g.addLayout(l2)
        self.bt_sug = QPushButton("Refazer as faixas pelo motor")
        g.addWidget(self.bt_sug)
        a = QWidgetAction(m); a.setDefaultWidget(w); m.addAction(a)
        self.sl_piso.valueChanged.connect(self._limiar_mudou)
        self.sl_sub.valueChanged.connect(self._limiar_mudou)
        self.bt_sug.clicked.connect(lambda: (m.close(), self._sugere(force=True)))
        return m

    # ================= estado =================
    def _habilita(self, on):
        for w in (self.bt_add, self.bt_gravar, self.bt_ajustes, self.ed_cultura):
            w.setEnabled(on)
        # o que nao tem o que mostrar fica fora da tela, nao vazio nela
        self.vazio.setVisible(not on)
        for w in (self.plot, self.geral, self.titulo, self.subtitulo, self.lb_faixa, self.lista,
                  self.seg_fonte, self.seg_janela, self.bt_ajustes, self.seg_conf):
            w.setVisible(on)
        for fila in (self._f1, self._f2, self.rapidas):
            for i in range(fila.count()):
                w = fila.itemAt(i).widget()
                if w is not None:
                    w.setVisible(on)

    @property
    def piso(self):
        return self.sl_piso.value() / 100.0

    @property
    def subida(self):
        return self.sl_sub.value() / 100.0

    @property
    def produtor(self):
        return self.ed_produtor.text().strip()

    def cor_de(self, cultura):
        return self.cores.get((cultura or "").strip().lower())

    def define_fonte(self, disponivel, atual, recorte=False):
        """Pixel/Media: a media so' existe quando o clique caiu dentro de um talhao pronto."""
        self.seg_fonte.bts["talhao"].setEnabled(disponivel)
        self.seg_fonte.marca(atual)

    # ================= abrir um talhao =================
    def mostra(self, row, col, curva, meses, janela=None, ja_gravado=None, produtor=None,
               titulo=None, subtitulo=""):
        """`curva` e `meses` sao a SERIE INTEIRA; `janela` sao os meses a mostrar ampliados."""
        if produtor:
            self.ed_produtor.setText(produtor)
        self.rc = (row, col)
        self.curva = np.asarray(curva, float)
        self.meses = list(meses)
        self.nd = ndvi_da_curva(self.curva)
        self._tocado = bool(ja_gravado)
        self._titulo = titulo or f"Ponto {row}, {col}"
        self._subtitulo = subtitulo

        self._limpa()
        x = np.arange(len(self.nd))
        # a curva: linha na cor de acao, com um veu por baixo -- e' o que o olho segue
        veu = QColor(estilo.ACCENT); veu.setAlpha(28)
        self.plot.plot(x, self.nd, pen=pg.mkPen(COR_CURVA, width=2.5),
                       fillLevel=0, brush=pg.mkBrush(veu),
                       symbol="o", symbolSize=6, symbolBrush=COR_CURVA,
                       symbolPen=pg.mkPen(estilo.PANEL, width=1.5))
        self.geral.plot(x, self.nd, pen=pg.mkPen(estilo.TEXT_3, width=1))
        self.geral.getAxis("bottom").setTicks([self._ticks_geral()])
        # ⚠️ sem isto o pyqtgraph re-enquadra a cada item novo (cada faixa) e desfaz o zoom:
        # o usuario escolhe 12 meses e o grafico volta sozinho para os 54.
        self.plot.getPlotItem().vb.disableAutoRange()
        self.geral.setXRange(-0.5, len(x) - 0.5, padding=0)
        self.janela.setBounds([0, len(x) - 1])

        self._cursor = pg.InfiniteLine(angle=90, movable=False,
                                       pen=pg.mkPen(estilo.TEXT, width=1.5,
                                                    style=Qt.PenStyle.DashLine),
                                       label="no mapa", labelOpts={
                                           "position": 0.92, "color": estilo.TEXT_2,
                                           "fill": pg.mkBrush(estilo.PANEL)})
        self._cursor.setZValue(5)
        self.plot.addItem(self._cursor)
        self.marca_mes(self._mes_mapa)

        alvo = [self.meses.index(m) for m in (janela or []) if m in self.meses]
        if alvo:
            self.janela.setRegion((min(alvo), max(alvo)))
            self.seg_janela.marca(12)
        else:
            self.define_janela(12)
        self._habilita(True)
        self._atualiza_rapidas()
        self._atualiza_sugestao()
        if ja_gravado:
            for s in ja_gravado:
                self._nova(s["ini"], s["fim"], s.get("cultura", ""), s.get("confianca"),
                           silencioso=True)
            self._refaz_chips()
            self._foca(0)
        else:
            self._sugere()
        self._janela_mudou()
        self.abriu.emit()

    def marca_mes(self, m):
        """A linha 'no mapa' vai para o mes m (AAAAMM)."""
        self._mes_mapa = m
        cur = getattr(self, "_cursor", None)
        if cur is None:
            return
        if m in self.meses:
            cur.setPos(self.meses.index(m))
            cur.show()
        else:
            cur.hide()

    def _ticks(self, i0, i1):
        """⚠️ Rotulos raleados conforme a janela: 54 rotulos no mesmo eixo viram um borrao."""
        passo = max(1, int(np.ceil((i1 - i0 + 1) / 16)))
        return [(i, rotulo_mes(m)) for i, m in enumerate(self.meses)
                if i0 <= i <= i1 and (i - i0) % passo == 0]

    def _ticks_geral(self):
        return [(i, str(m // 100)) for i, m in enumerate(self.meses) if m % 100 == 1]

    def _limpa(self):
        for f in self._faixas:
            self.plot.removeItem(f["reg"])
            self.plot.removeItem(f["txt"])
        self._faixas = []
        self._foco = -1
        self._picos = []
        self.plot.clear()
        self.geral.clear()
        self.geral.addItem(self.janela)
        self._cursor = None
        self._refaz_chips()

    # ================= janela de meses =================
    def define_janela(self, n):
        if not self.meses:
            return
        self.seg_janela.marca(n)
        total = len(self.meses)
        if n <= 0 or n >= total:
            self.janela.setRegion((0, total - 1))
            return
        a, _b = self.janela.getRegion()
        a = int(np.clip(round(a), 0, total - n))
        self.janela.setRegion((a, a + n - 1))

    def _janela_mudou(self):
        if self._ajustando or not self.meses:
            return
        a, b = self.janela.getRegion()
        n = len(self.meses)
        i0, i1 = int(np.clip(round(a), 0, n - 1)), int(np.clip(round(b), 0, n - 1))
        if (a, b) != (i0, i1):                      # a janela tambem gruda no mes
            self._ajustando = True
            self.janela.setRegion((i0, i1))
            self._ajustando = False
        self.plot.setXRange(i0 - 0.45, i1 + 0.45, padding=0)
        self.plot.getAxis("bottom").setTicks([self._ticks(i0, i1)])
        self._escreve_titulo()
        self._pinta()

    def _escreve_titulo(self, erro=None):
        if not self.meses:
            return
        a, b = self.janela.getRegion()
        i0, i1 = int(round(a)), int(round(b))
        self.titulo.setText(
            f"{self._titulo} &nbsp;<span style='color:{estilo.TEXT_2};font-weight:400'>· "
            f"{rotulo_mes(self.meses[i0])} → {rotulo_mes(self.meses[i1])}</span>")
        l1, _, l2 = (self._subtitulo or "").partition("<br>")     # 1a linha: pixel; 2a: fazenda
        sub = [s for s in (l1, self._leitura()) if s]
        if erro:
            sub = [f"<span style='color:#e8a33d'>{erro}</span>"]
        self.subtitulo.setText(" &nbsp;·&nbsp; ".join(sub) + ("<br>" + l2 if l2 else ""))

    def _leitura(self):
        """Quantos ciclos o motor leu na janela, em palavras."""
        a, b = self.janela.getRegion()
        navista = sorted({n for i, f, _p, n in self._sug if not (f < a - 0.5 or i > b + 0.5)})
        if not navista:
            return "nenhum ciclo detectado"
        if len(navista) == 1:
            n = navista[0]
            return f"{n:.0f} ciclo detectado" if n == 1 else f"{n:.0f} ciclos detectados"
        return "ciclos detectados por ano: " + " · ".join(f"{n:.0f}" for n in navista)

    # ================= deteccao =================
    def _atualiza_sugestao(self):
        for it in self._picos:
            self.plot.removeItem(it)
        self._picos = []
        if self.nd is None:
            return
        self._sug = deteccao(self.nd, self.meses, self.piso, self.subida)
        for _i, _f, pico, _n in self._sug:
            li = pg.InfiniteLine(pos=pico, angle=90,
                                 pen=pg.mkPen(estilo.BORDER_STRONG, width=1,
                                              style=Qt.PenStyle.DotLine))
            self.plot.addItem(li)
            self._picos.append(li)

    def _limiar_mudou(self):
        self.lb_piso.setText(f"{self.piso:.2f}")
        self.lb_sub.setText(f"{self.subida:.2f}")
        self._atualiza_sugestao()
        if not self._tocado:
            self._sugere(_manter=True)
        self._escreve_titulo()

    def _sugere(self, force=False, _manter=False):
        """⚠️ So' as faixas DENTRO DA JANELA A' VISTA: criar faixa para os quatro anos de uma vez
        entregaria oito faixas a quem clicou para responder sobre uma safra."""
        if not _manter:
            self._atualiza_sugestao()
        if self._faixas and not force and not _manter:
            return
        for f in self._faixas:
            self.plot.removeItem(f["reg"])
            self.plot.removeItem(f["txt"])
        self._faixas = []
        self._foco = -1
        a, b = self.janela.getRegion()
        for ini, fim, _p, _n in self._sug:
            if fim < a - 0.5 or ini > b + 0.5:
                continue
            self._nova(max(ini, int(round(a))), min(fim, int(round(b))), "", silencioso=True)
        if not self._faixas:
            self._nova(int(round(a)), int(round(b)), "", silencioso=True)
        self._refaz_chips()
        self._foca(0)

    # ================= faixas =================
    def _nova(self, ini, fim, cultura="", confianca=None, silencioso=False):
        n = len(self.meses)
        ini = int(np.clip(ini, 0, n - 1)); fim = int(np.clip(fim, ini, n - 1))
        reg = pg.LinearRegionItem(values=(ini, fim), bounds=(0, n - 1), movable=True)
        # bordas GROSSAS e com realce no hover: e' o que diz "isto se arrasta"
        for li in reg.lines:
            li.setPen(pg.mkPen(COR_FOCO, width=3))
            li.setHoverPen(pg.mkPen("#ffffff", width=4))
            li.setCursor(Qt.CursorShape.SizeHorCursor)      # <-> : "esta borda se arrasta"
        reg.setZValue(-10)
        self.plot.addItem(reg)
        txt = pg.TextItem("", anchor=(0.5, 0))
        f_ = QFont(); f_.setPixelSize(12); f_.setBold(True)
        txt.setFont(f_)
        txt.setZValue(6)
        self.plot.addItem(txt)
        f = {"ini": ini, "fim": fim, "cultura": cultura,
             "confianca": confianca or CONFIANCA[0], "reg": reg, "txt": txt}
        self._faixas.append(f)
        reg.sigRegionChanged.connect(lambda *_: self._regiao_mudou(f))
        reg.sigRegionChangeFinished.connect(lambda *_: setattr(self, "_tocado", True))
        if not silencioso:
            self._refaz_chips()
            self._foca(len(self._faixas) - 1)
        return f

    # ================= gestos na curva =================
    def _x_do_evento(self, ev):
        return self._vb().mapSceneToView(ev.scenePos()).x()

    def _clicou_curva(self, ev):
        """Clique na curva: seleciona a faixa sob ele E leva o mapa para aquele mes."""
        if not self.meses or ev.button() != Qt.MouseButton.LeftButton:
            return
        x = self._x_do_evento(ev)
        i = int(np.clip(round(x), 0, len(self.meses) - 1))
        self.mesEscolhido.emit(int(self.meses[i]))
        for k, f in enumerate(self._faixas):
            if f["ini"] - 0.5 <= x <= f["fim"] + 0.5:
                if k != self._foco:
                    self._foca(k)
                return

    def _arrastou_curva(self, ev, axis=None):
        """Arrastar no vazio desenha uma faixa nova, ja' grudada nos meses."""
        if not self.meses:
            return
        ev.accept()
        x0 = self._vb().mapSceneToView(ev.buttonDownScenePos()).x()
        x1 = self._vb().mapSceneToView(ev.scenePos()).x()
        n = len(self.meses)
        a = int(np.clip(round(min(x0, x1)), 0, n - 1))
        b = int(np.clip(round(max(x0, x1)), 0, n - 1))
        if ev.isFinish():
            if self._novo_reg is not None:
                self.plot.removeItem(self._novo_reg)
                self._novo_reg = None
            if b > a:                       # arrasto curto demais e' clique, nao faixa
                self._nova(a, b)
                self._tocado = True
            return
        if self._novo_reg is None:
            self._novo_reg = pg.LinearRegionItem(values=(a, b), movable=False,
                                                 brush=pg.mkBrush(0, 229, 255, 60),
                                                 pen=pg.mkPen(COR_FOCO, width=2))
            self._novo_reg.setZValue(-5)
            self.plot.addItem(self._novo_reg)
        self._novo_reg.setRegion((a, b))

    def _add_manual(self):
        a, b = self.janela.getRegion()
        meio = (a + b) / 2
        larg = max(1, (b - a) * 0.15)
        self._nova(int(round(meio - larg)), int(round(meio + larg)))
        self._tocado = True

    def _regiao_mudou(self, f):
        """⚠️ Aqui mora o grude no mes -- ver o aviso do topo do modulo."""
        if self._ajustando:
            return
        a, b = f["reg"].getRegion()
        n = len(self.meses)
        ia = int(np.clip(round(a), 0, n - 1))
        ib = int(np.clip(round(b), ia, n - 1))
        if (a, b) != (ia, ib):
            self._ajustando = True
            f["reg"].setRegion((ia, ib))
            self._ajustando = False
        f["ini"], f["fim"] = ia, ib
        if 0 <= self._foco < len(self._faixas) and self._faixas[self._foco] is f:
            self._mostra_foco()
        self._texto_chip(self._faixas.index(f))      # a linha da lista mostra o periodo novo
        self._pinta()

    def _apaga(self, i):
        if not (0 <= i < len(self._faixas)):
            return
        self.plot.removeItem(self._faixas[i]["reg"])
        self.plot.removeItem(self._faixas[i]["txt"])
        self._faixas.pop(i)
        self._tocado = True
        self._refaz_chips()
        self._foca(min(i, len(self._faixas) - 1))

    def _foco_editado(self, *_):
        if not (0 <= self._foco < len(self._faixas)):
            return
        f = self._faixas[self._foco]
        f["cultura"] = self.ed_cultura.currentText().strip()
        f["confianca"] = self.seg_conf.valor() or CONFIANCA[0]
        self._tocado = True
        self._pinta()
        self._texto_chip(self._foco)
        self._marca_rapida(f["cultura"])

    # ================= culturas de um clique =================
    def _atualiza_rapidas(self):
        """Os botoes das culturas mais provaveis: as mais gravadas primeiro, depois as de sempre."""
        while self.rapidas.count():
            w = self.rapidas.takeAt(0).widget()
            if w:
                w.setParent(None)
        conhecidas = {c.lower(): c for c in self._conhecidas()}
        ordem, vistos = [], set()
        for c in list(self._mais_usadas()) + RAPIDAS:
            k = c.lower()
            if k in vistos or (k not in conhecidas and c not in RAPIDAS):
                continue
            vistos.add(k)
            ordem.append(conhecidas.get(k, c))
        self._bts_rapidos = {}
        for c in ordem[:N_RAPIDAS]:
            b = QPushButton(c)
            b.setObjectName("cultura")
            b.setCheckable(True)
            b.setIcon(qta.icon("mdi6.circle", color=self.cor_de(c) or estilo.TEXT_3))
            b.setIconSize(QSize(11, 11))
            b.setToolTip(f"esta faixa é {c}")
            b.clicked.connect(lambda _, c=c: self.escolhe_cultura(c))
            self.rapidas.addWidget(b)
            self._bts_rapidos[c.lower()] = b

    def escolhe_cultura(self, c):
        """Um clique: nomeia a faixa em foco e passa para a proxima ainda sem nome."""
        if not (0 <= self._foco < len(self._faixas)):
            return
        self.ed_cultura.setCurrentText(c)          # dispara _foco_editado
        prox = [k for k, f in enumerate(self._faixas) if not f["cultura"]]
        depois = [k for k in prox if k > self._foco] or prox
        if depois:
            self._foca(depois[0])

    def _marca_rapida(self, cultura):
        for k, b in getattr(self, "_bts_rapidos", {}).items():
            b.setChecked(k == (cultura or "").lower())

    # ================= foco e chips =================
    def _foca(self, i):
        self._foco = i if 0 <= i < len(self._faixas) else -1
        if self._foco >= 0:
            self._mostra_foco()
        else:
            self.lb_faixa.setText("—")
            self.ed_cultura.setCurrentText("")
        self._pinta()
        self.lista.foca(self._foco)

    def _mostra_foco(self):
        f = self._faixas[self._foco]
        self.lb_faixa.setText(
            f"<b>Faixa {self._foco + 1}</b> <span style='color:{estilo.TEXT_2}'>de "
            f"{len(self._faixas)}</span> &nbsp; "
            f"<span style='color:{COR_FOCO}'>{rotulo_mes(self.meses[f['ini']])} → "
            f"{rotulo_mes(self.meses[f['fim']])}</span>")
        conhecidas = sorted(set(self._conhecidas()))
        self.ed_cultura.blockSignals(True)
        self.ed_cultura.clear()
        self.ed_cultura.addItems(conhecidas)
        comp = QCompleter(conhecidas, self.ed_cultura)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.ed_cultura.setCompleter(comp)
        self.ed_cultura.setCurrentText(f["cultura"])
        self.ed_cultura.blockSignals(False)
        self.seg_conf.marca(f["confianca"])
        self._marca_rapida(f["cultura"])

    def _refaz_chips(self):
        self.lista.refaz(len(self._faixas))
        for i in range(len(self._faixas)):
            self._texto_chip(i)

    def _texto_chip(self, i):
        if 0 <= i < len(self._faixas):
            f = self._faixas[i]
            per = f"{rotulo_mes(self.meses[f['ini']])} → {rotulo_mes(self.meses[f['fim']])}"
            conf = "" if f["confianca"] == CONFIANCA[0] else CONF_ROTULO[f["confianca"]].lower()
            self.lista.texto(i, per, f["cultura"], conf, i == self._foco, self.cor_de(f["cultura"]))

    def _pinta(self):
        """Cada faixa na cor da sua cultura; a em foco acesa, a duvida mais apagada que a certeza."""
        for i, f in enumerate(self._faixas):
            foco = (i == self._foco)
            base = self.cor_de(f["cultura"]) or (COR_FOCO if foco else COR_FUNDO)
            cor = pg.mkColor(base)
            alfa = ALFA.get(f["confianca"], 70)
            cor.setAlpha(alfa if foco else int(alfa * 0.55))
            f["reg"].setBrush(pg.mkBrush(cor))
            # ⚠️ o hoverBrush do LinearRegionItem e' calculado NO CONSTRUTOR a partir da cor padrao
            # (azul); trocar so' o brush deixa a faixa azul-escura assim que o mouse passa por cima.
            hv = pg.mkColor(cor)
            hv.setAlpha(min(cor.alpha() + 40, 255))
            f["reg"].setHoverBrush(pg.mkBrush(hv))
            # ⚠️ so' a faixa em foco se arrasta: com varias moveis, arrastar a errada e' questao de
            # tempo, e a resposta de um talhao vai para o mes de outra lavoura sem ninguem notar.
            f["reg"].setMovable(foco)
            borda = COR_FOCO if foco else pg.mkColor(base).darker(110)
            for li in f["reg"].lines:
                li.setPen(pg.mkPen(borda, width=3 if foco else 1))
            f["reg"].update()
            rot = f"{i + 1} · {f['cultura'] or '?'}"
            f["txt"].setText(rot, color=estilo.TEXT if foco else estilo.TEXT_2)
            f["txt"].setPos((f["ini"] + f["fim"]) / 2, 1.04)

    # ================= saida =================
    def segmentos(self):
        return [{"ini": f["ini"], "fim": f["fim"], "cultura": f["cultura"],
                 "confianca": f["confianca"],
                 "mes_ini": self.meses[f["ini"]], "mes_fim": self.meses[f["fim"]]}
                for f in sorted(self._faixas, key=lambda f: f["ini"])]

    def _emite(self):
        if self.rc is None:
            return
        segs = [s for s in self.segmentos() if s["cultura"]]
        if segs:
            self.gravar.emit(segs)
        else:
            self._escreve_titulo(erro="Escolha o que foi plantado antes de gravar")
            self.recado.emit("Escolha o que foi plantado em pelo menos uma faixa", "erro")
