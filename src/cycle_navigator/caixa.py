# -*- coding: utf-8 -*-
"""ARRASTAR UMA CAIXA SOBRE O MAPA: o segundo jeito de apontar um objeto para o SAM.

Um clique diz "e' isto aqui"; uma caixa diz "e' o que esta' dentro disto" -- e tira a duvida que o
clique deixa (o pivo ou o talhao dentro dele?). O bloco que o modelo ve^ sai da propria caixa.

⚠️ ARRASTAR E' TAMBEM O JEITO DE ANDAR NO MAPA. Por isso a caixa so' existe quando `ativo()` diz que
sim (Desenhar > Automatico > Caixa, sem contorno em ajuste), so' com o botao esquerdo e sem tecla:
⇧ clique e ⌥ clique continuam sendo as correcoes, e a roda continua aproximando.

⚠️ FILTRO NO VIEWPORT, NAO NA CENA: o ViewBox do pyqtgraph ja' consome o arrasto para mover o mapa;
quem quer o arrasto para si tem de chegar antes dele.
"""
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal

MINIMO = 6        # px de tela: menos que isto foi um clique tremido, nao uma caixa


class ArrastaCaixa(QObject):
    feita = pyqtSignal(float, float, float, float)      # r0, c0, r1, c1 na grade

    def __init__(self, view, ativo):
        super().__init__(view)
        self.view = view
        self.ativo = ativo
        self._de = None
        self._item = pg.PlotCurveItem(pen=pg.mkPen("#ffffff", width=1.6))
        self._item.setZValue(45)
        view.vb.addItem(self._item)
        view.glw.viewport().installEventFilter(self)

    def _grade(self, pos):
        p = self.view.vb.mapSceneToView(self.view.glw.mapToScene(pos))
        return p.y(), p.x()

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Type.MouseButtonPress:
            if (ev.button() == Qt.MouseButton.LeftButton and self.ativo()
                    and ev.modifiers() == Qt.KeyboardModifier.NoModifier):
                self._de = ev.position().toPoint()
                return True
        elif t == QEvent.Type.MouseMove and self._de is not None:
            r0, c0 = self._grade(self._de)
            r1, c1 = self._grade(ev.position().toPoint())
            self._item.setData(np.array([c0, c1, c1, c0, c0]), np.array([r0, r0, r1, r1, r0]))
            return True
        elif t == QEvent.Type.MouseButtonRelease and self._de is not None:
            de, ate = self._de, ev.position().toPoint()
            self._de = None
            self._item.clear()
            if abs(ate.x() - de.x()) >= MINIMO and abs(ate.y() - de.y()) >= MINIMO:
                r0, c0 = self._grade(de)
                r1, c1 = self._grade(ate)
                self.feita.emit(min(r0, r1), min(c0, c1), max(r0, r1), max(c0, c1))
            return True
        return False
