# -*- coding: utf-8 -*-
"""AS DUAS TABELAS DE ATRIBUTO: as fazendas e os pontos rotulados.

São duas camadas diferentes, com chaves diferentes (poligono x pixel) e perguntas diferentes -- "de
quem e' esta area" e "o que foi plantado neste talhao". Em SIG cada camada tem a sua tabela, e
juntar as duas numa so' obrigaria a repetir o cadastro da fazenda em cada ponto.

⚠️⚠️ DA LINHA SE CHEGA AO MAPA. Uma tabela de rotulos de onde nao se acha o ponto no mapa e' uma
lista de numeros: ninguem confere se o rotulo esta' no lugar certo, e o erro de digitacao vira dado.
Duplo-clique na linha centraliza o mapa no ponto e reabre a curva com as faixas.

⚠️ A COLUNA `faixas` E' LEGIVEL, NAO UM CODIGO. "Soja (out/23→fev/24) · Milho safrinha (mar→jul/24)"
responde na propria linha o que cada parte do ano significa. Guardar so' "2 faixas" obrigaria a
abrir cada ponto para saber o que ha' dentro.
"""
import logging

import pyqtgraph as pg
import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                             QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import estilo
from .fazendas import COLUNAS as COL_FAZ, COR_STATUS

log = logging.getLogger(__name__)

COL_PTS = [("id", "ID"), ("fazenda", "Fazenda"), ("produtor", "Produtor"),
           ("period", "Safra"), ("faixas", "O que foi plantado"),
           ("levantador", "Levantador"), ("gravado_em", "Gravado em"),
           ("x", "X (UTM)"), ("y", "Y (UTM)")]

MES = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
       7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}


def _m(v):
    return f"{MES[v % 100]}/{str(v // 100)[2:]}" if v else "?"


def resumo_faixas(pt):
    """'Soja (out/23→fev/24) · Milho safrinha (mar→jul/24)' -- o que a linha precisa dizer."""
    cic = pt.get("ciclos") or []
    if not cic:
        return pt.get("class", "")
    partes = []
    for s in cic:
        dúvida = "" if s.get("confianca") == "certo" else f" [{s.get('confianca')}]"
        partes.append(f"{s.get('cultura') or '?'} ({_m(s.get('mes_ini'))}→"
                      f"{_m(s.get('mes_fim'))}){dúvida}")
    return " · ".join(partes)


def _tabela(colunas):
    t = QTableWidget(0, len(colunas))
    t.setHorizontalHeaderLabels([r for _k, r in colunas])
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSortingEnabled(True)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    return t


class AbaFazendas(QWidget):
    editarContorno = pyqtSignal(object)
    editarDados = pyqtSignal(object)
    excluir = pyqtSignal(object)
    irPara = pyqtSignal(object)
    exportar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self.vazio = QLabel("Nenhuma fazenda cadastrada. Use <b>Desenhar fazenda</b> na barra de cima.")
        self.vazio.setObjectName("vazio")
        self.vazio.setWordWrap(True)
        lay.addWidget(self.vazio)
        self.tab = _tabela(COL_FAZ)
        self.tab.cellDoubleClicked.connect(lambda *_: self.irPara.emit(self.selecionada()))
        lay.addWidget(self.tab, 1)
        b = QHBoxLayout()
        self.lb = QLabel(""); self.lb.setObjectName("contador")
        b.addWidget(self.lb)
        b.addStretch(1)
        self.bt_dados = QPushButton("Preencher cadastro…")
        self.bt_contorno = QPushButton("Editar contorno")
        self.bt_excluir = QPushButton("Excluir"); self.bt_excluir.setObjectName("perigo")
        self.bt_exp = QPushButton("Exportar…")
        self.bt_exp.setIcon(qta.icon("mdi6.export", color=estilo.TEXT))
        for x in (self.bt_dados, self.bt_contorno, self.bt_excluir, self.bt_exp):
            b.addWidget(x)
        lay.addLayout(b)
        self.bt_dados.clicked.connect(lambda: self.editarDados.emit(self.selecionada()))
        self.bt_contorno.clicked.connect(lambda: self.editarContorno.emit(self.selecionada()))
        self.bt_excluir.clicked.connect(lambda: self.excluir.emit(self.selecionada()))
        self.bt_exp.clicked.connect(self.exportar)

    def selecionada(self):
        it = self.tab.item(self.tab.currentRow(), 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def lista(self, cadastro, selecionar=None):
        tem = bool(cadastro and len(cadastro))
        self.tab.setVisible(tem)
        self.vazio.setVisible(not tem)
        for x in (self.bt_dados, self.bt_contorno, self.bt_excluir, self.bt_exp):
            x.setEnabled(tem)
        self.lb.setText(f"{len(cadastro)} fazenda(s)" if tem else "")
        if not tem:
            self.tab.setRowCount(0)
            return
        self.tab.setSortingEnabled(False)
        self.tab.setRowCount(len(cadastro.fazendas))
        for i, f in enumerate(cadastro.fazendas):
            for j, (k, _r) in enumerate(COL_FAZ):
                v = f.get(k)
                txt = ("" if v is None else
                       f"{v:,.1f}".replace(",", ".") if k == "area_ha" else str(v))
                it = QTableWidgetItem(txt)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, f["id"])
                if k == "status":
                    it.setForeground(pg.mkColor(COR_STATUS.get(v, "#9aa0a6")))
                self.tab.setItem(i, j, it)
        self.tab.setSortingEnabled(True)
        if selecionar is not None:
            for i in range(self.tab.rowCount()):
                if self.tab.item(i, 0).data(Qt.ItemDataRole.UserRole) == selecionar:
                    self.tab.selectRow(i)
                    break


class AbaPontos(QWidget):
    irPara = pyqtSignal(int, int)        # row, col -> centraliza e reabre
    excluir = pyqtSignal(int, int)
    exportar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self.vazio = QLabel("Nenhum talhão levantado nesta safra. Clique num talhão no mapa.")
        self.vazio.setObjectName("vazio")
        self.vazio.setWordWrap(True)
        lay.addWidget(self.vazio)
        self.tab = _tabela(COL_PTS)
        self.tab.cellDoubleClicked.connect(self._ir)
        lay.addWidget(self.tab, 1)
        b = QHBoxLayout()
        self.lb = QLabel(""); self.lb.setObjectName("contador")
        b.addWidget(self.lb)
        b.addStretch(1)
        self.bt_ir = QPushButton("Ver no mapa")
        self.bt_ir.setIcon(qta.icon("mdi6.map-marker-outline", color=estilo.TEXT))
        self.bt_excluir = QPushButton("Excluir"); self.bt_excluir.setObjectName("perigo")
        self.bt_exp = QPushButton("Exportar…")
        self.bt_exp.setIcon(qta.icon("mdi6.export", color=estilo.TEXT))
        for x in (self.bt_ir, self.bt_excluir, self.bt_exp):
            b.addWidget(x)
        lay.addLayout(b)
        self.bt_ir.clicked.connect(lambda: self._ir(self.tab.currentRow(), 0))
        self.bt_excluir.clicked.connect(self._excluir)
        self.bt_exp.clicked.connect(self.exportar)

    def _rc(self, linha):
        it = self.tab.item(linha, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _ir(self, linha, _col=0):
        rc = self._rc(linha)
        if rc:
            self.irPara.emit(*rc)

    def _excluir(self):
        rc = self._rc(self.tab.currentRow())
        if rc:
            self.excluir.emit(*rc)

    def lista(self, store):
        pts = list(store.points) if store is not None else []
        self.tab.setVisible(bool(pts))
        self.vazio.setVisible(not pts)
        for x in (self.bt_ir, self.bt_excluir, self.bt_exp):
            x.setEnabled(bool(pts))
        nf = sum(len(p.get("ciclos") or []) for p in pts)
        self.lb.setText(f"{len(pts)} talhão(ões) · {nf} faixa(s)" if pts else "")
        self.tab.setSortingEnabled(False)
        self.tab.setRowCount(len(pts))
        for i, p in enumerate(pts):
            for j, (k, _r) in enumerate(COL_PTS):
                if k == "faixas":
                    txt = resumo_faixas(p)
                elif k in ("x", "y"):
                    txt = f"{p.get(k):.0f}" if p.get(k) is not None else ""
                else:
                    txt = str(p.get(k, "") or "")
                it = QTableWidgetItem(txt)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, (int(p["row"]), int(p["col"])))
                self.tab.setItem(i, j, it)
        self.tab.setSortingEnabled(True)


class JanelaTabelas(QWidget):
    """As duas tabelas, em abas, numa janela que se abre quando se precisa."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tabelas de atributos")
        self.resize(1040, 420)
        self.fazendas = AbaFazendas()
        self.pontos = AbaPontos()
        self.abas = QTabWidget()
        self.abas.addTab(self.fazendas, "Fazendas")
        self.abas.addTab(self.pontos, "Pontos rotulados")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 8)
        lay.addWidget(self.abas)

    def mostra(self, aba=None):
        if aba is not None:
            self.abas.setCurrentIndex(aba)
        self.show()
        self.raise_()
        self.activateWindow()
