# -*- coding: utf-8 -*-
"""ANALISE: tudo o que foi levantado na safra, numa tela so'.

A tabela responde "o que ha' em cada linha"; aqui a pergunta e' outra -- "o que ja' fizemos, o que
esta' saindo, e o que precisa ser olhado de novo antes de ir embora da cooperativa".

  - numeros de cima: talhoes, hectares, produtores, sistemas, quantos tem duvida;
  - SISTEMAS: cada sequencia gravada ("Soja > Milho safrinha"), em talhoes e hectares;
  - CALENDARIO: quantos talhoes tem cada cultura em cada mes da safra;
  - CURVAS: o vigor medio de cada sistema -- um talhao gravado como soja com curva de pasto salta;
  - PARA CONFERIR: o que ficou sem cultura, com duvida, sem produtor, repetido.

⚠️⚠️ DAQUI SE CHEGA AO MAPA, como na tabela: duplo clique num talhao da lista centra o mapa nele e
reabre a curva. Um painel de onde nao se volta ao dado e' so' um enfeite.

⚠️ `resume()` e' pura (lista de pontos -> dicionario), sem Qt: e' ela que os testes exercitam.
"""
from collections import Counter, defaultdict

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                             QLabel, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from . import estilo
from .texto import data_br, plural
from .tabelas import MES, resumo_faixas

SEM_NOME = "sem cultura"


def _ndvi(curva):
    c = np.asarray(curva, float)
    if c.ndim != 2 or c.shape[1] < 4:
        return None
    return (c[:, 3] - c[:, 2]) / (c[:, 3] + c[:, 2] + 1e-6)


def _sistema(pt):
    cic = pt.get("ciclos") or []
    if not cic:
        return str(pt.get("class") or SEM_NOME)
    return " > ".join((s.get("cultura") or "?") for s in cic)


def pendencias(pt, repetidos=()):
    """Por que este talhao merece ser olhado de novo: lista de motivos (vazia = tudo certo)."""
    m = []
    cic = pt.get("ciclos") or []
    if not cic:
        m.append("sem faixas")
    if any(not (s.get("cultura") or "").strip() for s in cic):
        m.append("faixa sem cultura")
    conf = {s.get("confianca") for s in cic} - {"certo", None}
    if conf:
        m.append("dúvida: " + ", ".join(sorted(str(c).replace("nao", "não") for c in conf)))
    if not (pt.get("produtor") or "").strip():
        m.append("sem produtor")
    if pt.get("id") in repetidos:
        m.append("mesmo ponto gravado mais de uma vez")
    return m


def resume(pts, meses):
    """Lista de pontos da safra + os 12 meses dela -> tudo o que a tela mostra."""
    pts = list(pts)
    por_sam = defaultdict(list)
    for p in pts:
        if p.get("sam_id"):
            por_sam[p["sam_id"]].append(p.get("id"))
    repetidos = {i for ids in por_sam.values() if len(ids) > 1 for i in ids}

    sistemas = defaultdict(lambda: {"n": 0, "ha": 0.0, "curvas": []})
    cal = defaultdict(lambda: np.zeros(len(meses), int))        # cultura -> talhoes por mes
    culturas = Counter()
    ha_total, sem_area = 0.0, 0
    produtores, levantadores, fazendas = set(), Counter(), set()
    conferir = []
    for p in pts:
        s = sistemas[_sistema(p)]
        s["n"] += 1
        ha = p.get("talhao_ha")
        if ha:
            s["ha"] += float(ha); ha_total += float(ha)
        else:
            sem_area += 1
        nd = _ndvi(p.get("curve")) if p.get("curve") is not None else None
        if nd is not None and len(nd) == len(meses):
            s["curvas"].append(nd)
        for f in (p.get("ciclos") or []):
            nome = (f.get("cultura") or "").strip() or SEM_NOME
            culturas[nome] += 1
            for k, m in enumerate(meses):
                if f.get("mes_ini") and f.get("mes_fim") and f["mes_ini"] <= m <= f["mes_fim"]:
                    cal[nome][k] += 1
        if (p.get("produtor") or "").strip():
            produtores.add(p["produtor"].strip().lower())
        if p.get("fazenda_id"):
            fazendas.add(p["fazenda_id"])
        levantadores[(p.get("levantador") or "?").strip() or "?"] += 1
        mot = pendencias(p, repetidos)
        if mot:
            conferir.append((p, mot))
    for s in sistemas.values():
        s["curva"] = np.nanmean(np.array(s.pop("curvas")), axis=0) if s["curvas"] else None
    ordem = sorted(sistemas.items(), key=lambda kv: (-kv[1]["n"], kv[0]))
    return {"n": len(pts), "ha": ha_total, "sem_area": sem_area, "produtores": len(produtores),
            "fazendas": len(fazendas), "levantadores": dict(levantadores),
            "sistemas": ordem, "calendario": dict(cal), "culturas": culturas,
            "conferir": conferir, "ultimo": max((p.get("gravado_em") or "" for p in pts),
                                               default="")}


def _br(v, casas=0):
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


class _Numero(QFrame):
    """Um numero grande com a legenda embaixo."""

    def __init__(self, legenda):
        super().__init__()
        self.setObjectName("cartao")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        self.v = QLabel("–"); self.v.setObjectName("numero")
        self.l = QLabel(legenda); self.l.setObjectName("dica")
        lay.addWidget(self.v); lay.addWidget(self.l)

    def poe(self, valor, legenda=None, alerta=False):
        self.v.setText(valor)
        self.v.setProperty("alerta", bool(alerta))
        self.v.style().unpolish(self.v); self.v.style().polish(self.v)
        if legenda is not None:
            self.l.setText(legenda)


def _bloco(titulo, dica=""):
    f = QFrame(); f.setObjectName("cartao")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 12, 16, 14)
    lay.setSpacing(8)
    cab = QHBoxLayout()
    t = QLabel(titulo); t.setObjectName("h2")
    cab.addWidget(t)
    d = QLabel(dica); d.setObjectName("dica")
    cab.addWidget(d, 1)
    lay.addLayout(cab)
    return f, lay, cab, d


def _grafico():
    g = pg.PlotWidget(background=estilo.PANEL)
    g.setMenuEnabled(False)
    g.setMouseEnabled(x=False, y=False)
    g.hideButtons()
    for eixo in ("left", "bottom"):
        ax = g.getAxis(eixo)
        ax.setPen(pg.mkPen(estilo.BORDER_STRONG))
        ax.setTextPen(pg.mkPen(estilo.TEXT_2))
    g.showGrid(y=True, alpha=0.12)
    return g


class JanelaAnalise(QWidget):
    irPara = pyqtSignal(int, int)        # row, col -> o mapa centra e reabre a curva
    exportar = pyqtSignal()

    def __init__(self, cores, parent=None):
        super().__init__(parent)
        self.cores = cores
        self.setWindowTitle("Análise do levantamento")
        self.resize(1400, 860)
        self._pts, self._filtro, self._r = [], None, None
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(18, 14, 18, 16)
        raiz.setSpacing(12)

        cab = QHBoxLayout()
        self.titulo = QLabel("Análise"); self.titulo.setObjectName("h1")
        cab.addWidget(self.titulo)
        self.sub = QLabel(""); self.sub.setObjectName("dica")
        cab.addWidget(self.sub, 1)
        self.bt_exp = QPushButton("Exportar…")
        self.bt_exp.clicked.connect(self.exportar)
        cab.addWidget(self.bt_exp)
        raiz.addLayout(cab)

        self.vazio = QLabel("Nada levantado nesta safra ainda.\nClique num ponto do mapa, diga o "
                            "que foi plantado e grave: os números aparecem aqui.")
        self.vazio.setObjectName("vazio")
        self.vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raiz.addWidget(self.vazio, 1)

        self.corpo = QWidget()
        raiz.addWidget(self.corpo, 1)
        g = QGridLayout(self.corpo)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(12)

        nums = QHBoxLayout(); nums.setSpacing(12)
        self.n_talhoes = _Numero("pontos levantados")
        self.n_ha = _Numero("hectares")
        self.n_prod = _Numero("produtores")
        self.n_sist = _Numero("sistemas de cultivo")
        self.n_conf = _Numero("para conferir")
        for w in (self.n_talhoes, self.n_ha, self.n_prod, self.n_sist, self.n_conf):
            nums.addWidget(w, 1)
        g.addLayout(nums, 0, 0, 1, 2)

        # ---- sistemas ----
        f, lay, _c, _d = _bloco("Sistemas de cultivo", "clique num para ver os pontos dele")
        self.area_sist = QScrollArea(); self.area_sist.setWidgetResizable(True)
        self.area_sist.setFrameShape(QFrame.Shape.NoFrame)
        self.cx_sist = QWidget()
        self.lay_sist = QVBoxLayout(self.cx_sist)
        self.lay_sist.setContentsMargins(0, 0, 0, 0); self.lay_sist.setSpacing(4)
        self.area_sist.setWidget(self.cx_sist)
        # o miolo da rolagem pinta o fundo da janela por cima do cartao: transparente nos tres
        self.area_sist.setStyleSheet("background: transparent;")
        self.area_sist.viewport().setAutoFillBackground(False)
        self.cx_sist.setAutoFillBackground(False)
        self.tab.setColumnWidth(3, 150) if hasattr(self, "tab") else None
        lay.addWidget(self.area_sist, 1)
        g.addWidget(f, 1, 0)

        # ---- calendario ----
        f, lay, _c, _d = _bloco("Calendário da safra", "pontos com cada cultura, mês a mês")
        self.g_cal = _grafico()
        self.legenda = QLabel(""); self.legenda.setObjectName("dica")
        self.legenda.setTextFormat(Qt.TextFormat.RichText); self.legenda.setWordWrap(True)
        lay.addWidget(self.g_cal, 1); lay.addWidget(self.legenda)
        g.addWidget(f, 1, 1)

        # ---- curvas ----
        f, lay, _c, _d = _bloco("Vigor médio por sistema",
                                "a curva (NDVI) média dos pontos de cada sistema")
        self.g_cur = _grafico()
        self.g_cur.setYRange(0, 1, padding=0.02)
        self.leg_cur = QLabel(""); self.leg_cur.setObjectName("dica")
        self.leg_cur.setTextFormat(Qt.TextFormat.RichText); self.leg_cur.setWordWrap(True)
        lay.addWidget(self.g_cur, 1); lay.addWidget(self.leg_cur)
        g.addWidget(f, 2, 0)

        # ---- lista ----
        f, lay, cab2, self.dica_lista = _bloco("Para conferir")
        self.t_lista = f.findChild(QLabel)
        self.bt_todos = QPushButton("Ver todos"); self.bt_todos.setObjectName("ghost")
        self.bt_todos.setCheckable(True)
        self.bt_todos.clicked.connect(lambda: self._lista(None if not self.bt_todos.isChecked()
                                                          else "*"))
        cab2.addWidget(self.bt_todos)
        self.tab = QTableWidget(0, 4)
        self.tab.setHorizontalHeaderLabels(["Produtor / fazenda", "O que foi plantado", "ha",
                                            "Olhar de novo"])
        self.tab.verticalHeader().setVisible(False)
        self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.setShowGrid(False)
        h = self.tab.horizontalHeader()
        # ⚠️ larguras fixas nas pontas e o meio esticando: com "ajustar ao conteudo" a coluna dos
        # motivos tomava a linha e "o que foi plantado" -- a que importa -- ficava com 40 px.
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tab.setColumnWidth(0, 170); self.tab.setColumnWidth(2, 48)
        self.tab.setColumnWidth(3, 190)
        self.tab.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.tab.setWordWrap(False)
        self.tab.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.tab, 1)
        rod = QLabel("duplo clique abre o ponto no mapa"); rod.setObjectName("dica")
        lay.addWidget(rod)
        g.addWidget(f, 2, 1)
        g.setRowStretch(1, 1); g.setRowStretch(2, 1)
        g.setColumnStretch(0, 1); g.setColumnStretch(1, 1)

    # ---------------- dados ----------------
    def cor(self, cultura):
        return self.cores.get(cultura, estilo.TEXT_3)

    def atualiza(self, store, safra, meses):
        self._pts = list(store.points) if store is not None else []
        self._meses = list(meses)
        r = self._r = resume(self._pts, self._meses)
        self.titulo.setText(f"Análise · safra {safra}")
        self.vazio.setVisible(r["n"] == 0)
        self.corpo.setVisible(r["n"] > 0)
        self.bt_exp.setEnabled(r["n"] > 0)
        if r["n"] == 0:
            self.sub.setText("")
            return
        lev = " · ".join(f"{k} ({v})" for k, v in sorted(r["levantadores"].items(),
                                                         key=lambda kv: -kv[1]))
        self.sub.setText(f"levantado por {lev} · último registro "
                         f"{data_br(r['ultimo'])}")
        self.n_talhoes.poe(_br(r["n"]))
        self.n_ha.poe(_br(r["ha"], 1 if r["ha"] < 1000 else 0) if r["ha"] else "—",
                      "hectares de talhão" + (f" · {plural(r['sem_area'], 'ponto', 'pontos')} sem área" if r["sem_area"] else ""))
        self.n_prod.poe(_br(r["produtores"]),
                        "produtores" + (f" · {plural(r['fazendas'], 'fazenda', 'fazendas')}" if r["fazendas"] else ""))
        self.n_sist.poe(_br(len(r["sistemas"])))
        self.n_conf.poe(_br(len(r["conferir"])), alerta=bool(r["conferir"]))
        self._sistemas(r)
        self._calendario(r)
        self._curvas(r)
        self.bt_todos.setChecked(False)
        self._lista(None)

    # ---------------- sistemas ----------------
    def _sistemas(self, r):
        while self.lay_sist.count():
            w = self.lay_sist.takeAt(0).widget()
            if w is not None:
                w.setParent(None)        # some JA': deleteLater sozinho deixa o antigo na tela
                w.deleteLater()          # ate' a proxima volta do laco, por cima do novo
        topo = max(s["n"] for _k, s in r["sistemas"])
        for nome, s in r["sistemas"]:
            b = QPushButton(); b.setObjectName("linha")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setFixedHeight(40)
            b.clicked.connect(lambda _=False, n=nome: self._lista(n))
            lay = QGridLayout(b)
            lay.setContentsMargins(10, 4, 10, 5); lay.setSpacing(3)
            bolas = "".join(f"<span style='color:{self.cor(c.strip())}'>●</span>"
                            for c in nome.split(">"))
            t = QLabel(f"{bolas}&nbsp; {nome}"); t.setTextFormat(Qt.TextFormat.RichText)
            t.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            v = QLabel(f"<b>{s['n']}</b> {'ponto' if s['n'] == 1 else 'pontos'}"
                       + (f" · {_br(s['ha'], 1)} ha" if s["ha"] else ""))
            v.setObjectName("dica"); v.setTextFormat(Qt.TextFormat.RichText)
            v.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(t, 0, 0); lay.addWidget(v, 0, 1, Qt.AlignmentFlag.AlignRight)
            barra = QHBoxLayout(); barra.setSpacing(0)
            cheio = QFrame(); cheio.setFixedHeight(4)
            cheio.setStyleSheet(f"background:{self.cor(nome.split('>')[0].strip())};"
                                "border-radius:2px;")
            fr = max(1, round(100 * s["n"] / topo))
            barra.addWidget(cheio, fr); barra.addStretch(100 - fr)
            lay.addLayout(barra, 1, 0, 1, 2)
            self.lay_sist.addWidget(b)
        self.lay_sist.addStretch(1)

    # ---------------- calendario ----------------
    def _eixo_meses(self, g):
        g.getAxis("bottom").setTicks([[(k, MES[m % 100]) for k, m in enumerate(self._meses)]])
        g.setXRange(-0.6, len(self._meses) - 0.4, padding=0)

    def _calendario(self, r):
        self.g_cal.clear()
        base = np.zeros(len(self._meses))
        leg = []
        for nome, _n in r["culturas"].most_common():
            y = r["calendario"].get(nome)
            if y is None or not y.any():
                continue
            cor = self.cor(nome)
            self.g_cal.addItem(pg.BarGraphItem(x=np.arange(len(y)), y0=base, y1=base + y,
                                               width=0.72, brush=pg.mkBrush(cor),
                                               pen=pg.mkPen(estilo.PANEL, width=1)))
            base = base + y
            leg.append(f"<span style='color:{cor}'>■</span> {nome}")
        self._eixo_meses(self.g_cal)
        self.g_cal.setYRange(0, max(1, base.max()) * 1.08, padding=0)
        self.legenda.setText(" &nbsp; ".join(leg))

    # ---------------- curvas ----------------
    def _curvas(self, r):
        self.g_cur.clear()
        leg = []
        x = np.arange(len(self._meses))
        for nome, s in r["sistemas"][:8]:
            if s["curva"] is None:
                continue
            cor = self.cor(nome.split(">")[0].strip())
            estilo_linha = Qt.PenStyle.SolidLine if ">" not in nome else Qt.PenStyle.DashLine
            self.g_cur.plot(x, s["curva"], pen=pg.mkPen(cor, width=2.4, style=estilo_linha),
                            symbol="o", symbolSize=5, symbolBrush=cor, symbolPen=None)
            traco = "- -" if ">" in nome else "—"
            leg.append(f"<span style='color:{cor}'>{traco}</span> {nome} ({s['n']})")
        self._eixo_meses(self.g_cur)
        self.leg_cur.setText(" &nbsp; ".join(leg))

    # ---------------- lista ----------------
    def _lista(self, filtro):
        """None = so' o que precisa ser conferido; '*' = todos; outro = os talhoes de um sistema."""
        self._filtro = filtro
        r = self._r
        motivos = {id(p): m for p, m in r["conferir"]}
        if filtro is None:
            linhas = [p for p, _m in r["conferir"]]
            self.t_lista.setText("Para conferir")
            self.dica_lista.setText("tudo em ordem" if not linhas else
                                    f"{len(linhas)} de {plural(r['n'], 'ponto', 'pontos')}")
        elif filtro == "*":
            linhas = self._pts
            self.t_lista.setText("Todos os pontos")
            self.dica_lista.setText(plural(len(linhas), "ponto", "pontos"))
        else:
            linhas = [p for p in self._pts if _sistema(p) == filtro]
            self.t_lista.setText(filtro)
            self.dica_lista.setText(plural(len(linhas), "ponto", "pontos"))
            self.bt_todos.setChecked(False)
        self.tab.setRowCount(len(linhas))
        for i, p in enumerate(linhas):
            quem = (p.get("produtor") or "").strip() or "—"
            if p.get("fazenda"):
                quem += f" · {p['fazenda']}"
            ha = p.get("talhao_ha")
            cel = [quem, resumo_faixas(p), _br(float(ha), 1) if ha else "—",
                   " · ".join(motivos.get(id(p), []))]
            for j, txt in enumerate(cel):
                it = QTableWidgetItem(txt)
                it.setToolTip(txt)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, (int(p["row"]), int(p["col"])))
                if j == 2:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if j == 3 and txt:
                    it.setForeground(pg.mkBrush("#e0a23a"))
                self.tab.setItem(i, j, it)

    def _ir(self, linha, _col=0):
        it = self.tab.item(linha, 0)
        rc = it.data(Qt.ItemDataRole.UserRole) if it else None
        if rc:
            self.irPara.emit(*rc)

    def mostra(self):
        self.show(); self.raise_(); self.activateWindow()
