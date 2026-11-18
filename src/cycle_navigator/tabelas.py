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
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import estilo
from .texto import data_br, plural
from .fazendas import COLUNAS as COL_FAZ, COR_STATUS

log = logging.getLogger(__name__)

COL_PTS = [("id", "ID"), ("fazenda", "Fazenda"), ("produtor", "Produtor"),
           ("period", "Safra"), ("faixas", "O que foi plantado"),
           ("talhao_ha", "Área (ha)"), ("confianca", "Confiança"), ("fonte_curva", "Contorno"),
           ("levantador", "Levantador"), ("gravado_em", "Gravado em"),
           ("x", "X (UTM)"), ("y", "Y (UTM)")]
NUMERICAS = {"id", "talhao_ha", "x", "y"}
FONTE = {"talhao": "Talhão", "recorte": "Recorte", "pixel": "Ponto"}
# a pior das faixas e' a confianca do talhao: uma duvida numa faixa e' uma duvida no sistema
ORDEM_CONF = {"certo": 0, "acho que": 1, "nao sei": 2}
ROTULO_CONF = {"certo": "Certo", "acho que": "Acho que", "nao sei": "Não sei"}


def confianca_do_ponto(pt):
    cs = [s.get("confianca") or "certo" for s in (pt.get("ciclos") or [])]
    return ROTULO_CONF.get(max(cs, key=lambda c: ORDEM_CONF.get(c, 0)), "") if cs else ""


def _sem_acento(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower())
                   if unicodedata.category(c) != "Mn")


class _Celula(QTableWidgetItem):
    """⚠️ Coluna de numero ordena como numero: como texto, 100 ha vinha antes de 20 ha."""

    def __init__(self, txt, valor=None):
        super().__init__(txt)
        self.valor = valor

    def __lt__(self, outra):
        a, b = self.valor, getattr(outra, "valor", None)
        if a is not None and b is not None:
            return a < b
        return super().__lt__(outra)

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
        dúvida = "" if s.get("confianca") == "certo" else f" [{ROTULO_CONF.get(s.get('confianca'), '?').lower()}]"
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
    t.horizontalHeader().setStretchLastSection(True)      # cabecalho alinhado como o conteudo:
    t.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
        self.lb.setText(plural(len(cadastro), "fazenda", "fazendas") if tem else "")
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
    desfazer = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self.vazio = QLabel("Nenhum talhão levantado nesta safra. Clique num talhão no mapa.")
        self.vazio.setObjectName("vazio")
        self.vazio.setWordWrap(True)
        lay.addWidget(self.vazio)
        self.ed_filtro = QLineEdit()
        self.ed_filtro.setObjectName("busca")
        self.ed_filtro.setPlaceholderText("Filtrar: cultura, produtor, fazenda, levantador…")
        self.ed_filtro.setClearButtonEnabled(True)
        self.ed_filtro.textChanged.connect(self._filtra)
        lay.addWidget(self.ed_filtro)
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
        self.bt_desfaz = QPushButton("Desfazer exclusão"); self.bt_desfaz.setEnabled(False)
        self.bt_desfaz.clicked.connect(self.desfazer)
        for x in (self.bt_ir, self.bt_excluir, self.bt_desfaz, self.bt_exp):
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

    def _filtra(self, *_):
        """Todas as palavras digitadas tem de aparecer na linha, em qualquer coluna, sem ligar para
        acento nem maiuscula. So' esconde linhas: nada e' alterado."""
        palavras = _sem_acento(self.ed_filtro.text()).split()
        n = 0
        for i in range(self.tab.rowCount()):
            linha = _sem_acento(" ".join(self.tab.item(i, j).text() for j in range(self.tab.columnCount())
                                         if self.tab.item(i, j) is not None))
            some = any(p not in linha for p in palavras)
            self.tab.setRowHidden(i, some)
            n += not some
        total = self.tab.rowCount()
        if total:
            self.lb.setText(f"{n} de {total}" if palavras else self._contagem)

    def lista(self, store):
        pts = list(store.points) if store is not None else []
        self.ed_filtro.setVisible(bool(pts))
        self.tab.setVisible(bool(pts))
        self.vazio.setVisible(not pts)
        for x in (self.bt_ir, self.bt_excluir, self.bt_exp):
            x.setEnabled(bool(pts))
        nf = sum(len(p.get("ciclos") or []) for p in pts)
        self._contagem = f"{plural(len(pts), 'ponto', 'pontos')} · {plural(nf, 'faixa', 'faixas')}" if pts else ""
        self.lb.setText(self._contagem)
        self.tab.setSortingEnabled(False)
        self.tab.setRowCount(len(pts))
        for i, p in enumerate(pts):
            for j, (k, _r) in enumerate(COL_PTS):
                v = p.get(k)
                if k == "faixas":
                    txt = resumo_faixas(p)
                elif k == "confianca":
                    txt = confianca_do_ponto(p)
                elif k == "fonte_curva":
                    txt = FONTE.get(v, "")
                elif k == "talhao_ha":
                    txt = f"{v:.1f}".replace(".", ",") if v else ""
                elif k in ("x", "y"):
                    txt = f"{v:.0f}" if v is not None else ""
                else:
                    txt = data_br(v) if k == "gravado_em" else str(v or "")
                it = _Celula(txt, (float(v) if v else 0.0) if k in NUMERICAS else None)
                if k in NUMERICAS:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, (int(p["row"]), int(p["col"])))
                self.tab.setItem(i, j, it)
        self.tab.setSortingEnabled(True)
        self._filtra()


class JanelaTabelas(QWidget):
    """As duas tabelas, em abas, numa janela que se abre quando se precisa."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tabelas de atributos")
        self.resize(1400, 480)
        self.fazendas = AbaFazendas()
        self.pontos = AbaPontos()
        self.abas = QTabWidget()
        self.abas.addTab(self.fazendas, "Fazendas")
        self.abas.addTab(self.pontos, "Talhões levantados")
        self.abas.setCurrentIndex(1)     # abre no que se veio ver: o que ja' foi levantado
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 8)
        lay.addWidget(self.abas)

    def mostra(self, aba=None):
        if aba is not None:
            self.abas.setCurrentIndex(aba)
        self.show()
        self.raise_()
        self.activateWindow()
