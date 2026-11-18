# -*- coding: utf-8 -*-
"""A janela das sugestoes: escrever uma nova em cima, acompanhar as conversas embaixo."""
import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
                             QFrame, QVBoxLayout, QWidget)

from . import estilo
from .sugestoes import COR, STATUS


def _corpo(txt):
    """Texto do dev com '- ' vira marcador e linha terminada em ':' vira titulo (como no iRest)."""
    out = []
    for ln in str(txt).splitlines():
        t = html.escape(ln.strip())
        if not t:
            out.append("<div style='height:6px'></div>")
        elif t.startswith("- "):
            out.append(f"<div style='margin-left:10px'>• {t[2:]}</div>")
        elif t.endswith(":"):
            out.append(f"<div style='font-weight:600;margin-top:4px'>{t}</div>")
        else:
            out.append(f"<div>{t}</div>")
    return "".join(out)


class JanelaSugestoes(QWidget):
    enviada = pyqtSignal(str)            # o texto da sugestao nova (a foto e o contexto ja' foram)

    def __init__(self, caixa, parent=None):
        super().__init__(parent)
        self.caixa = caixa
        self._foto, self._contexto, self._quem = None, {}, ""
        self.setWindowTitle("Sugestões")
        self.resize(720, 760)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(18, 14, 18, 16); raiz.setSpacing(10)
        t = QLabel("O que você quer mudar ou saber?"); t.setObjectName("h1")
        raiz.addWidget(t)
        self.carimbo = QLabel(""); self.carimbo.setObjectName("dica"); self.carimbo.setWordWrap(True)
        raiz.addWidget(self.carimbo)
        self.ed = QPlainTextEdit()
        self.ed.setPlaceholderText("Escreva do seu jeito: o que atrapalhou, o que faltou, uma ideia, "
                                   "uma dúvida. A tela que você estava vendo vai junto.")
        self.ed.setFixedHeight(110)
        raiz.addWidget(self.ed)
        lin = QHBoxLayout()
        self.aviso = QLabel(""); self.aviso.setObjectName("dica")
        lin.addWidget(self.aviso, 1)
        self.bt = QPushButton("Enviar sugestão"); self.bt.setObjectName("cta")
        self.bt.clicked.connect(self._envia)
        lin.addWidget(self.bt)
        raiz.addLayout(lin)
        h = QLabel("Suas sugestões"); h.setObjectName("h2")
        raiz.addWidget(h)
        self.area = QScrollArea(); self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.area.setStyleSheet("background: transparent;")
        self.area.viewport().setAutoFillBackground(False)
        self.cx = QWidget(); self.cx.setAutoFillBackground(False)
        self.lay = QVBoxLayout(self.cx)
        self.lay.setContentsMargins(0, 0, 0, 0); self.lay.setSpacing(10)
        self.area.setWidget(self.cx)
        raiz.addWidget(self.area, 1)

    def abre(self, foto, contexto, quem):
        """`foto`: a janela principal como estava no instante do clique."""
        self._foto, self._contexto, self._quem = foto, contexto, quem
        partes = [f"safra {contexto.get('safra')}", str(contexto.get("mes_rotulo") or ""),
                  str(contexto.get("camada") or "")]
        if contexto.get("talhao"):
            partes.append(contexto["talhao"])
        self.carimbo.setText("Vai junto: a foto da tela · " + " · ".join(p for p in partes if p))
        self.aviso.setText("")
        self.atualiza()
        self.caixa.marca_vistas()
        self.show(); self.raise_(); self.activateWindow()
        self.ed.setFocus()

    def _envia(self):
        txt = self.ed.toPlainText().strip()
        if len(txt) < 3:
            self.aviso.setText("Escreva a sugestão antes de enviar")
            return
        self.caixa.nova(txt, quem=self._quem, contexto=self._contexto, foto=self._foto)
        self.ed.clear()
        self.aviso.setText("Enviada. A resposta aparece aqui embaixo.")
        self.atualiza()
        self.enviada.emit(txt)

    def atualiza(self):
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w is not None:
                w.setParent(None)        # some JA': deleteLater sozinho deixa o antigo na tela
                w.deleteLater()          # ate' a proxima volta do laco, por cima do novo
        itens = self.caixa.lista()
        if not itens:
            v = QLabel("Nenhuma sugestão ainda."); v.setObjectName("dica")
            self.lay.addWidget(v)
        for s in itens:
            f = QFrame(); f.setObjectName("cartao")
            l = QVBoxLayout(f); l.setContentsMargins(14, 10, 14, 12); l.setSpacing(6)
            st = s.get("status", "aberta")
            novo = "" if s.get("visto_pela_equipe", True) else " &nbsp;<b>· resposta nova</b>"
            cab = QLabel(f"<span style='color:{COR.get(st, estilo.TEXT_2)}'>● "
                         f"{STATUS.get(st, st)}</span>{novo}"
                         f" &nbsp;<span style='color:{estilo.TEXT_3}'>{html.escape(s.get('quem', ''))}"
                         f" · {s.get('quando', '')[:16].replace('T', ' ')}</span>")
            cab.setTextFormat(Qt.TextFormat.RichText)
            l.addWidget(cab)
            for m in s.get("mensagens", []):
                dev = m.get("autor") == "dev"
                b = QLabel(("<div style='color:%s;font-size:11px'>%s</div>" %
                            (estilo.ACCENT if dev else estilo.TEXT_3,
                             "Resposta" if dev else html.escape(m.get("quem") or "você")))
                           + _corpo(m.get("texto", "")))
                b.setTextFormat(Qt.TextFormat.RichText); b.setWordWrap(True)
                b.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                if dev:
                    b.setStyleSheet(f"background:{estilo.RAISED}; border-radius:8px; padding:8px 10px;")
                l.addWidget(b)
            self.lay.addWidget(f)
        self.lay.addStretch(1)
