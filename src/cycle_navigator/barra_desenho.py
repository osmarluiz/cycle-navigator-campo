# -*- coding: utf-8 -*-
"""A BARRA DE DESENHO: as ferramentas de contorno, juntas e a' vista, como num SIG.

⚠️⚠️ O SAM E' FERRAMENTA DE DESENHO, NAO FONTE DE INFORMACAO. Identificar le^ o que ha' num lugar
(a serie do pixel, a fazenda); desenhar cria um contorno. Antes as duas coisas vinham no mesmo
clique -- o recorte automatico aparecia ao identificar -- e ninguem sabia dizer o que o clique
fazia. Aqui ficam as tres maneiras de obter um contorno, lado a lado:

    Polígono     vertice a vertice, a' mao
    Automático   um clique e o SAM propoe o contorno; ⇧ clique soma, ⌥ clique tira
    Copiar       adota o contorno de um imovel do CAR ou de um talhao pronto

e os tres comandos que todo desenho precisa: desfazer, concluir, cancelar. A linha de baixo diz, a
cada momento, o que o proximo clique faz.
"""
import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import estilo

POLIGONO, AUTO, COPIAR = "poligono", "auto", "copiar"

DICAS = {
    (POLIGONO, "vazio"): "Clique para pôr o primeiro vértice",
    (POLIGONO, "tracando"): "Clique põe vértice · duplo clique ou Enter conclui · botão direito "
                            "tira o último · Esc cancela",
    (AUTO, "vazio"): "Clique dentro do talhão: o contorno é proposto na hora",
    (AUTO, "proposta"): "⇧ clique soma uma parte · ⌥ clique tira · outro clique recomeça · "
                        "Enter conclui",
    (COPIAR, "vazio"): "Clique dentro de um imóvel do CAR ou de um talhão pronto (ligue a camada)",
    "ajuste": "Arraste um vértice · clique na linha cria vértice · botão direito no vértice "
              "apaga · Enter conclui",
}


class BarraDesenho(QWidget):
    ferramenta = pyqtSignal(str)
    desfazer = pyqtSignal()
    concluir = pyqtSignal()
    cancelar = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("flutuante")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(6, 6, 10, 6); raiz.setSpacing(2)
        linha = QHBoxLayout(); linha.setSpacing(4)
        self.grupo = QButtonGroup(self); self.grupo.setExclusive(True)
        self.bts = {}
        for chave, txt, ico, dica in (
                (POLIGONO, "Polígono", "mdi6.vector-polygon", "desenhar vértice a vértice"),
                (AUTO, "Automático", "mdi6.auto-fix", "um clique e o contorno é proposto (SAM)"),
                (COPIAR, "Copiar contorno", "mdi6.content-copy",
                 "adotar o contorno de um imóvel do CAR ou de um talhão pronto")):
            b = QPushButton(txt)
            b.setCheckable(True)
            b.setIcon(qta.icon(ico, color=estilo.TEXT, color_on=estilo.ON_ACCENT))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(dica)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=chave: self.ferramenta.emit(c))
            self.grupo.addButton(b); self.bts[chave] = b
            linha.addWidget(b)
        sep = QLabel("│"); sep.setObjectName("dica")
        linha.addWidget(sep)
        self.bt_desfaz = self._acao("mdi6.undo", "Desfazer", "desfazer o último passo (⌫)",
                                    self.desfazer)
        self.bt_conclui = self._acao("mdi6.check", "Concluir", "gravar o contorno (Enter)",
                                     self.concluir)
        self.bt_cancela = self._acao("mdi6.close", "Cancelar", "abandonar o desenho (Esc)",
                                     self.cancelar)
        for b in (self.bt_desfaz, self.bt_conclui, self.bt_cancela):
            linha.addWidget(b)
        raiz.addLayout(linha)
        self.dica = QLabel(""); self.dica.setObjectName("dica")
        self.dica.setContentsMargins(8, 0, 0, 2)
        raiz.addWidget(self.dica)

    def _acao(self, ico, txt, dica, sinal):
        b = QPushButton(txt)
        b.setIcon(qta.icon(ico, color=estilo.TEXT))
        b.setIconSize(QSize(16, 16))
        b.setToolTip(dica)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(sinal)
        return b

    def mostra(self, ferramenta, fase, pode_concluir, pode_desfazer, auto=True):
        """`fase`: "vazio" | "tracando" | "proposta" | "ajuste" (contorno fechado, vertices soltos)."""
        self.bts[AUTO].setVisible(auto)
        # ⚠️ com o contorno ja' fechado nenhuma ferramenta esta' "em uso": deixar uma acesa dizia
        # que o proximo clique ia desenhar, quando ele so' ajusta vertices
        self.grupo.setExclusive(False)
        for chave, b in self.bts.items():
            b.setChecked(chave == ferramenta and fase != "ajuste")
        self.grupo.setExclusive(True)
        self.dica.setText(DICAS["ajuste"] if fase == "ajuste" else DICAS.get((ferramenta, fase), ""))
        self.bt_conclui.setEnabled(pode_concluir)
        self.bt_desfaz.setEnabled(pode_desfazer)
        self.adjustSize()
