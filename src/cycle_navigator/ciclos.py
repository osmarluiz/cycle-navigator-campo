# -*- coding: utf-8 -*-
"""O CICLO DO ANO: o agricultor conta o que foi plantado em cada parte, uma faixa por vez.

⚠️⚠️ AS BORDAS GRUDAM NO MES. A serie e' mensal: "meio de fevereiro" nao existe no dado, e deixar a
borda parar ali promete uma precisao que o dado nao tem -- e ainda faz duas pessoas gravarem limites
diferentes para a mesma resposta. Toda borda cai no mes inteiro mais proximo.

⚠️ AS FAIXAS VEM SUGERIDAS PELO MOTOR, MAS A CULTURA VEM VAZIA. As BORDAS vem de `sos_k`/`eos_k` do
pheno_engine porque ninguem desenha duas bordas por talhao com o produtor esperando, e porque assim
a resposta do agricultor e' uma resposta SOBRE A LEITURA DO MOTOR. A CULTURA vem vazia porque campo
pre-preenchido e' aceito sem ler: deixar "Soja" produziria talhoes de soja que ninguem afirmou.

⚠️ O PAINEL FOI ENXUGADO DE PROPOSITO. A versao anterior tinha cinco fileiras de controle embaixo do
grafico e ninguem achava o que importava. O ponto de operacao do motor (piso/subida) saiu para um
menu: e' ajuste de especialista, usado uma vez por sessao, e estava competindo por atencao com o
campo onde se digita a cultura, que e' usado a cada talhao.
"""
import logging

import numpy as np
import pheno_engine
import pyqtgraph as pg
import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QCompleter, QHBoxLayout, QLabel, QLineEdit, QMenu,
                             QPushButton, QSlider, QToolButton, QVBoxLayout, QWidget,
                             QWidgetAction)

from . import estilo

log = logging.getLogger(__name__)

MES_CURTO = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
             7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}

# ⚠️ A CONFIANCA E' POR FAIXA, NAO POR PONTO. O produtor costuma ter certeza da lavoura principal e
# duvida da segunda. Uma confianca unica obrigaria a rebaixar a resposta inteira por causa da parte
# fraca, ou inflar a parte fraca por causa da forte -- as duas saidas sao mentira.
CONFIANCA = ["certo", "acho que", "nao sei"]
ALFA = {"certo": 85, "acho que": 45, "nao sei": 22}
COR_FOCO = estilo.FOCO
COR_FUNDO = estilo.TEXT_3


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


class Chip(QWidget):
    """Uma faixa na fila: clica para focar, ✕ para apagar.

    ⚠️ O apagar mora AQUI, no proprio chip. Antes era um botao "remover faixa" la' embaixo, que
    apagava a faixa em foco -- so' que para apagar a faixa 2 era preciso primeiro focar a faixa 2,
    e nada na tela dizia isso. Apagar o que se esta' vendo e' um gesto, nao dois.
    """

    focar = pyqtSignal()
    apagar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bt = QPushButton()
        self.bt.setObjectName("chip")
        self.bt.setCheckable(True)
        self.bt.clicked.connect(self.focar)
        self.x = QToolButton()
        self.x.setObjectName("chipx")
        self.x.setIcon(qta.icon("mdi6.close", color=estilo.TEXT_2, color_active=estilo.PERIGO))
        self.x.setIconSize(QSize(14, 14))
        self.x.setToolTip("apagar esta faixa")
        self.x.clicked.connect(self.apagar)
        lay.addWidget(self.bt)
        lay.addWidget(self.x)

    def texto(self, t, aceso):
        self.bt.setText(t)
        self.bt.setChecked(aceso)


class PainelCiclo(QWidget):
    """A curva do pixel clicado e as faixas que o produtor for contando."""

    gravar = pyqtSignal(list)

    def __init__(self, culturas_conhecidas=None, parent=None):
        super().__init__(parent)
        self._conhecidas = culturas_conhecidas or (lambda: [])
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

        lay = QVBoxLayout(self)
        self.setObjectName("rodape")
        lay.setContentsMargins(16, 10, 16, 12)
        lay.setSpacing(8)

        self.titulo = QLabel("")
        self.titulo.setObjectName("h2")
        lay.addWidget(self.titulo)

        # ⚠️ ESTADO VAZIO. Sem pixel aberto, dois graficos em branco com eixo 0..1 nao dizem nada e
        # ainda parecem defeito. Enquanto nao ha' o que mostrar, mostra-se a instrucao.
        self.vazio = QLabel("Clique num talhão no mapa para ver o ciclo do ano")
        self.vazio.setObjectName("vazio")
        self.vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.vazio, 1)

        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(170)
        self.plot.setBackground(estilo.BG)
        # o botao "A" de auto-range aparece sozinho quando o auto-range e' desligado; aqui o zoom e'
        # da janela de meses, nao do usuario, entao o botao so' confunde
        self.plot.getPlotItem().hideButtons()
        self.plot.setLabel("left", "NDVI")
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setYRange(0, 1)
        self.plot.getPlotItem().setMenuEnabled(False)
        lay.addWidget(self.plot, 1)

        self.geral = pg.PlotWidget()
        self.geral.setFixedHeight(44)
        self.geral.setBackground(estilo.BG)
        self.geral.getPlotItem().hideButtons()
        self.geral.setMouseEnabled(x=False, y=False)
        self.geral.hideAxis("left")
        self.geral.getPlotItem().setMenuEnabled(False)
        self.geral.setYRange(0, 1)
        self.janela = pg.LinearRegionItem(brush=pg.mkBrush(0, 229, 255, 40),
                                          pen=pg.mkPen(COR_FOCO, width=2),
                                          hoverBrush=pg.mkBrush(0, 229, 255, 70))
        self.janela.setZValue(10)
        self.geral.addItem(self.janela)
        self.janela.sigRegionChanged.connect(self._janela_mudou)
        lay.addWidget(self.geral)

        # ---------------- fileira 1: janela, faixas, acoes ----------------
        f1 = self._f1 = QHBoxLayout()
        f1.setSpacing(6)
        for txt, n in (("12 meses", 12), ("24", 24), ("tudo", 0)):
            b = QPushButton(txt); b.setObjectName("ghost")
            b.clicked.connect(lambda _, n=n: self.define_janela(n))
            f1.addWidget(b)
        f1.addSpacing(14)
        f1.addWidget(_rot("Faixas"))
        self.fila = QHBoxLayout()
        self.fila.setSpacing(6)
        f1.addLayout(self.fila)
        self.bt_add = QPushButton("faixa"); self.bt_add.setObjectName("ghost")
        self.bt_add.setIcon(qta.icon("mdi6.plus", color=estilo.TEXT)); self.bt_add.setIconSize(QSize(16, 16))
        f1.addWidget(self.bt_add)
        f1.addStretch(1)
        self.lb_leitura = QLabel("")
        self.lb_leitura.setObjectName("contador")
        f1.addWidget(self.lb_leitura)
        # ⚠️ piso/subida saem para um menu: ajuste de especialista nao pode disputar espaco com o
        # campo que se usa a cada talhao.
        self.bt_ajustes = QToolButton()
        self.bt_ajustes.setObjectName("ghost")
        self.bt_ajustes.setText("detecção")
        self.bt_ajustes.setIcon(qta.icon("mdi6.tune-variant", color=estilo.TEXT_2))
        self.bt_ajustes.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.bt_ajustes.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bt_ajustes.setMenu(self._menu_ajustes())
        f1.addWidget(self.bt_ajustes)
        lay.addLayout(f1)

        # ---------------- fileira 2: a faixa em foco ----------------
        f2 = self._f2 = QHBoxLayout()
        f2.setSpacing(10)
        self.lb_faixa = QLabel("—")
        self.lb_faixa.setMinimumWidth(230)
        f2.addWidget(self.lb_faixa)
        # ⚠️ combo EDITAVEL com autocompletar: lista fechada nao cobre o que o campo traz
        # ("sorgo forrageiro", "consorcio"); texto cru puro produz "soja"/"Soja"/"SOJA" como tres
        # culturas na hora de somar.
        self.ed_cultura = QComboBox()
        self.ed_cultura.setEditable(True)
        self.ed_cultura.setMinimumWidth(260)
        self.ed_cultura.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.ed_cultura.lineEdit().setPlaceholderText("o que foi plantado nesta faixa?")
        f2.addWidget(self.ed_cultura)
        self.cb_conf = QComboBox(); self.cb_conf.addItems(CONFIANCA); self.cb_conf.setFixedWidth(110)
        f2.addWidget(self.cb_conf)
        f2.addStretch(1)
        f2.addWidget(_rot("Produtor"))
        self.ed_produtor = QLineEdit()
        self.ed_produtor.setPlaceholderText("quem respondeu")
        self.ed_produtor.setFixedWidth(200)
        f2.addWidget(self.ed_produtor)
        self.bt_gravar = QPushButton("Gravar")
        self.bt_gravar.setObjectName("cta")
        self.bt_gravar.setIcon(qta.icon("mdi6.content-save", color=estilo.ON_ACCENT))
        self.bt_gravar.setIconSize(QSize(18, 18))
        self.bt_gravar.setMinimumWidth(130)
        self.bt_gravar.setDefault(True)
        f2.addWidget(self.bt_gravar)
        lay.addLayout(f2)

        self.bt_add.clicked.connect(self._add_manual)
        self.bt_gravar.clicked.connect(self._emite)
        self.ed_cultura.currentTextChanged.connect(self._foco_editado)
        self.cb_conf.currentTextChanged.connect(self._foco_editado)

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
        g.addWidget(QLabel("<b>Ponto de operação do motor</b>"))
        g.addWidget(QLabel("<span style='color:#999'>o que conta como um ciclo</span>"))
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
        for w in (self.bt_add, self.bt_gravar, self.bt_ajustes, self.ed_cultura, self.cb_conf):
            w.setEnabled(on)
        # o que nao tem o que mostrar fica fora da tela, nao vazio nela
        self.vazio.setVisible(not on)
        for w in (self.plot, self.geral, self.titulo, self.lb_faixa, self.lb_leitura):
            w.setVisible(on)
        for fila in (self._f1, self._f2):
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

    # ================= abrir um pixel =================
    def mostra(self, row, col, curva, meses, janela=None, ja_gravado=None, produtor=None):
        """`curva` e `meses` sao a SERIE INTEIRA; `janela` sao os meses a mostrar ampliados."""
        if produtor:
            self.ed_produtor.setText(produtor)
        self.rc = (row, col)
        self.curva = np.asarray(curva, float)
        self.meses = list(meses)
        self.nd = ndvi_da_curva(self.curva)
        self._tocado = bool(ja_gravado)

        self._limpa()
        x = np.arange(len(self.nd))
        self.plot.plot(x, self.nd, pen=pg.mkPen("#e8e8e8", width=2),
                       symbol="o", symbolSize=5, symbolBrush="#e8e8e8")
        self.geral.plot(x, self.nd, pen=pg.mkPen("#9a9a9a", width=1))
        self.geral.getAxis("bottom").setTicks([self._ticks_geral()])
        # ⚠️ sem isto o pyqtgraph re-enquadra a cada item novo (cada faixa) e desfaz o zoom:
        # o usuario escolhe 12 meses e o grafico volta sozinho para os 54.
        self.plot.getPlotItem().vb.disableAutoRange()
        self.geral.setXRange(-0.5, len(x) - 0.5, padding=0)
        self.janela.setBounds([0, len(x) - 1])

        alvo = [self.meses.index(m) for m in (janela or []) if m in self.meses]
        if alvo:
            self.janela.setRegion((min(alvo), max(alvo)))
        else:
            self.define_janela(12)
        self._habilita(True)
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
        self._faixas = []
        self._foco = -1
        self._picos = []
        self.plot.clear()
        self.geral.clear()
        self.geral.addItem(self.janela)
        self._refaz_chips()

    # ================= janela de meses =================
    def define_janela(self, n):
        if not self.meses:
            return
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
        self.titulo.setText(
            f"<b>Pixel {self.rc}</b> &nbsp;·&nbsp; {rotulo_mes(self.meses[i0])} → "
            f"{rotulo_mes(self.meses[i1])} &nbsp;<span style='color:#888'>"
            f"({i1 - i0 + 1} meses · arraste as bordas coloridas para ajustar cada faixa)</span>")

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
                                 pen=pg.mkPen("#6a6a6a", width=1, style=Qt.PenStyle.DotLine))
            self.plot.addItem(li)
            self._picos.append(li)
        a, b = self.janela.getRegion()
        navista = sorted({n for i, f, _p, n in self._sug if not (f < a - 0.5 or i > b + 0.5)})
        txt = " · ".join(f"{n:.1f}" for n in navista) or "—"
        self.lb_leitura.setText(f"<span style='color:#999'>motor lê</span> <b>{txt}</b> ciclo/ano")

    def _limiar_mudou(self):
        self.lb_piso.setText(f"{self.piso:.2f}")
        self.lb_sub.setText(f"{self.subida:.2f}")
        self._atualiza_sugestao()
        if not self._tocado:
            self._sugere(_manter=True)

    def _sugere(self, force=False, _manter=False):
        """⚠️ So' as faixas DENTRO DA JANELA A' VISTA: criar faixa para os quatro anos de uma vez
        entregaria oito faixas a quem clicou para responder sobre uma safra."""
        if not _manter:
            self._atualiza_sugestao()
        if self._faixas and not force and not _manter:
            return
        for f in self._faixas:
            self.plot.removeItem(f["reg"])
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
        reg.setZValue(-10)
        self.plot.addItem(reg)
        f = {"ini": ini, "fim": fim, "cultura": cultura,
             "confianca": confianca or CONFIANCA[0], "reg": reg}
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
        """Clique dentro de uma faixa seleciona aquela faixa."""
        if not self._faixas or ev.button() != Qt.MouseButton.LeftButton:
            return
        x = self._x_do_evento(ev)
        for i, f in enumerate(self._faixas):
            if f["ini"] - 0.5 <= x <= f["fim"] + 0.5:
                if i != self._foco:
                    self._foca(i)
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
        self._pinta()

    def _apaga(self, i):
        if not (0 <= i < len(self._faixas)):
            return
        self.plot.removeItem(self._faixas[i]["reg"])
        self._faixas.pop(i)
        self._tocado = True
        self._refaz_chips()
        self._foca(min(i, len(self._faixas) - 1))

    def _foco_editado(self, *_):
        if not (0 <= self._foco < len(self._faixas)):
            return
        f = self._faixas[self._foco]
        f["cultura"] = self.ed_cultura.currentText().strip()
        f["confianca"] = self.cb_conf.currentText()
        self._tocado = True
        self._pinta()
        self._texto_chip(self._foco)

    # ================= foco e chips =================
    def _foca(self, i):
        self._foco = i if 0 <= i < len(self._faixas) else -1
        if self._foco >= 0:
            self._mostra_foco()
        else:
            self.lb_faixa.setText("—")
            self.ed_cultura.setCurrentText("")
        self._pinta()
        for j, c in enumerate(self._chips()):
            c.bt.setChecked(j == self._foco)

    def _mostra_foco(self):
        f = self._faixas[self._foco]
        self.lb_faixa.setText(
            f"<b>Faixa {self._foco + 1}/{len(self._faixas)}</b> &nbsp; "
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
        self.cb_conf.blockSignals(True)
        self.cb_conf.setCurrentText(f["confianca"])
        self.cb_conf.blockSignals(False)

    def _chips(self):
        return [self.fila.itemAt(i).widget() for i in range(self.fila.count())
                if self.fila.itemAt(i).widget()]

    def _refaz_chips(self):
        while self.fila.count():
            w = self.fila.takeAt(0).widget()
            if w:
                w.setParent(None)
        for i in range(len(self._faixas)):
            c = Chip()
            c.focar.connect(lambda i=i: self._foca(i))
            c.apagar.connect(lambda i=i: self._apaga(i))
            self.fila.addWidget(c)
        for i in range(len(self._faixas)):
            self._texto_chip(i)

    def _texto_chip(self, i):
        chips = self._chips()
        if 0 <= i < len(chips):
            f = self._faixas[i]
            chips[i].texto(f"{i + 1}. {f['cultura'] or '—'}", i == self._foco)

    def _pinta(self):
        """A em foco acesa, as outras esmaecidas; a duvida mais apagada que a certeza."""
        for i, f in enumerate(self._faixas):
            foco = (i == self._foco)
            cor = pg.mkColor(COR_FOCO if foco else COR_FUNDO)
            cor.setAlpha(ALFA.get(f["confianca"], 70) if foco else 25)
            f["reg"].setBrush(pg.mkBrush(cor))
            # ⚠️ o hoverBrush do LinearRegionItem e' calculado NO CONSTRUTOR a partir da cor padrao
            # (azul); trocar so' o brush deixa a faixa azul-escura assim que o mouse passa por cima.
            hv = pg.mkColor(cor)
            hv.setAlpha(min(cor.alpha() + 40, 255))
            f["reg"].setHoverBrush(pg.mkBrush(hv))
            # ⚠️ so' a faixa em foco se arrasta: com varias moveis, arrastar a errada e' questao de
            # tempo, e a resposta de um talhao vai para o mes de outra lavoura sem ninguem notar.
            f["reg"].setMovable(foco)
            for li in f["reg"].lines:
                li.setPen(pg.mkPen(COR_FOCO if foco else COR_FUNDO, width=3 if foco else 1))
            f["reg"].update()

    # ================= saida =================
    def segmentos(self):
        return [{"ini": f["ini"], "fim": f["fim"], "cultura": f["cultura"],
                 "confianca": f["confianca"],
                 "mes_ini": self.meses[f["ini"]], "mes_fim": self.meses[f["fim"]]}
                for f in sorted(self._faixas, key=lambda f: f["ini"])]

    def _emite(self):
        segs = [s for s in self.segmentos() if s["cultura"]]
        if segs:
            self.gravar.emit(segs)
        else:
            self.titulo.setText("<b style='color:#e8a33d'>Escreva o que foi plantado antes de "
                                "gravar.</b>")


def _rot(txt):
    l = QLabel(txt)
    l.setObjectName("rotulo")
    return l
