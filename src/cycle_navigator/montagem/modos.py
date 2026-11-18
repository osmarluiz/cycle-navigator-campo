# -*- coding: utf-8 -*-
"""MONTAGEM · modos: Identificar / Desenhar / Editar e o desenho de fazendas.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from ..barra_desenho import AUTO, COPIAR, POLIGONO, BarraDesenho
from ..fazendas import DesenhoPoligono
from ..fazendas import DialogoFazenda
from ..janela import DESENHAR
from ..janela import EDITAR
from ..janela import IDENTIFICAR

log = logging.getLogger(__name__)


def instala(ctx):
    cadastro = ctx.cadastro
    cam_car = ctx.cam_car
    cam_faz = ctx.cam_faz
    camadas = ctx.camadas
    estado = ctx.estado
    sob_o_clique = ctx.sob_o_clique
    status = ctx.status
    tabs = ctx.tabs
    view = ctx.view
    win = ctx.win

    # ---------------- modos ----------------
    desenho = DesenhoPoligono(view, None)
    barra_des = BarraDesenho(view)
    barra_des.hide()
    estado["ferramenta"] = POLIGONO
    estado["auto"] = None            # proposta do SAM em curso: {"poli", "pontos", "nota"}

    def _pt_br_no_menu_do_vertice():
        """O menu de botao direito do vertice vem em ingles do pyqtgraph ("Remove handle")."""
        roi = desenho._roi
        if roi is None:
            return
        for h in roi.getHandles():
            if getattr(h, "removeAction", None) is not None:
                h.removeAction.setText("Apagar vértice")

    def atualiza_barra():
        """A barra diz o que o proximo clique faz; some fora do Desenhar."""
        if estado["modo"] != DESENHAR:
            barra_des.hide()
            win.extra_topo = 0
            ctx.alfinete.setVisible(True)
            ctx.p_ciclo.setVisible(True)        # volta o que estava identificado
            return
        # ⚠️⚠️ DESENHANDO, SO' O DESENHO: o alfinete e a serie do ultimo pixel identificado nao
        # dizem respeito ao contorno e disputavam a tela com ele.
        ctx.alfinete.setVisible(False)
        ctx.p_ciclo.setVisible(False)           # o divisor entrega a altura toda ao mapa
        if desenho._roi is not None:
            fase = "ajuste"
            _pt_br_no_menu_do_vertice()
            try:
                desenho._roi.sigRegionChangeFinished.connect(_pt_br_no_menu_do_vertice,
                                                             Qt.ConnectionType.UniqueConnection)
            except TypeError:
                pass
        elif estado["auto"]:
            fase = "proposta"
        elif desenho.pts:
            fase = "tracando"
        else:
            fase = "vazio"
        pode = fase in ("ajuste", "proposta") or len(desenho.pts) >= 3
        volta = bool(desenho.pts) or bool(estado["auto"])
        barra_des.mostra(estado["ferramenta"], fase, pode, volta, auto=ctx.recorte.ok)
        barra_des.move(14, 14 + win.barra.ferramentas.height() + 8)
        barra_des.show(); barra_des.raise_()
        win.extra_topo = barra_des.height() + 8     # o aviso desce: nao pode cobrir a barra

    def _larga_proposta():
        estado["auto"] = None
        ctx.desenha_recorte(None)

    def usa_ferramenta(f):
        """Troca a maneira de obter o contorno; o que estava em curso e' abandonado."""
        if f == AUTO and not ctx.recorte.ok:
            f = POLIGONO
        estado["ferramenta"] = f
        _larga_proposta()
        desenho.cancela()
        cam_faz.oculto = None; cam_faz.redesenha()
        estado["semente_dados"] = {}
        if f == POLIGONO:
            desenho.comeca(None, None)
        view.setCursor(Qt.CursorShape.CrossCursor)
        atualiza_barra()

    def usa_modo(m, fid=None, semente=None):
        """`semente` = (pontos, cod_car): abre o modo Desenhar ja' com esse contorno editavel."""
        if estado["modo"] == DESENHAR and m != DESENHAR:
            desenho.cancela(); cam_faz.oculto = None; cam_faz.redesenha()
        _larga_proposta()
        estado["modo"] = m
        estado["semente_dados"] = dict(semente[1]) if semente else {}
        win.barra.mostra_modo(m)
        win._posiciona()
        if cam_car is not None:
            ctx.aviso_car()
        if m == DESENHAR:
            cam_faz.oculto = fid
            cam_faz.redesenha()
            if semente:
                desenho.comeca(None, semente[0])
            elif fid:
                desenho.comeca(fid, (cadastro.por_id(fid) or {}).get("poligono"))
            elif estado["ferramenta"] == POLIGONO:
                desenho.comeca(None, None)
            else:
                desenho.cancela()
        view.setCursor(Qt.CursorShape.CrossCursor if m == DESENHAR
                       else Qt.CursorShape.ArrowCursor)
        atualiza_barra()

    def confirma():
        """Enter / duplo-clique / Concluir: fecha o contorno e abre o cadastro."""
        if estado["modo"] != DESENHAR:
            return
        if estado["auto"]:
            # ⚠️ a mascara do SAM vem com centenas de vertices (um por degrau de pixel); para um
            # contorno que a pessoa ainda vai ajustar a' mao, 1,5 px de tolerancia (~7 m) basta
            limpo = estado["auto"]["poli"].simplify(1.5)
            pts = [(float(x), float(y)) for x, y in limpo.exterior.coords[:-1]]
        else:
            pts = desenho.pontos()
        if len(pts) < 3:
            return
        fid = desenho.editando
        extra = dict(estado.get("semente_dados") or {})
        desenho.cancela()
        _larga_proposta()
        cam_faz.oculto = None
        f = cadastro.salva(fid, pts, extra or None)
        dlg = DialogoFazenda(f, win)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dados = dlg.dados()
            dados.update(extra)          # os dados do CAR nao se editam no formulario
            f = cadastro.salva(f["id"], None, dados)
        cam_faz.redesenha()
        tabs.fazendas.lista(cadastro, selecionar=f["id"])
        ctx.atualiza_busca()
        win.avisa(f"Fazenda gravada · {f.get('nome') or 'sem nome'}")
        log.info("fazenda #%d: %s (%.1f ha)", f["id"], f.get("nome") or "-", f.get("area_ha") or 0)
        usa_modo(IDENTIFICAR)

    def cancela():
        for c in camadas:
            c.limpa_selecao()
        if estado["modo"] in (DESENHAR, EDITAR):
            usa_modo(IDENTIFICAR)

    def desfaz():
        """Um passo atras: o ultimo vertice, ou a ultima correcao da proposta automatica."""
        if estado["modo"] != DESENHAR:
            return
        rec = estado["auto"]
        if rec:
            pontos = rec["pontos"][:-1]
            novo = ctx.pede_recorte(pontos) if pontos else None
            estado["auto"] = novo
            ctx.desenha_recorte(novo)
        else:
            desenho.desfaz_vertice()
        atualiza_barra()

    def _clique_auto(row, col, mods):
        """Automatico: o clique propoe; ⇧ soma e ⌥ tira da proposta aberta; clique simples recomeca."""
        rec = estado["auto"]
        soma = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        tira = bool(mods & Qt.KeyboardModifier.AltModifier)
        if rec and (soma or tira):
            pontos = rec["pontos"] + [(row, col, 0 if tira else 1)]
        else:
            pontos = [(row, col, 1)]
        novo = ctx.pede_recorte(pontos)
        if novo is None or novo["poli"].area * ctx.PX_HA > 3000:
            win.avisa("Não consegui propor um contorno aqui — tente outro ponto ou desenhe à mão",
                      "info", 4000)
            return
        estado["auto"] = novo
        ctx.desenha_recorte(novo)
        ha = f"{novo['poli'].area * ctx.PX_HA:.1f}".replace(".", ",")
        incerto = "  ·  contorno incerto, confira" if 0 < novo["nota"] < 0.8 else ""
        status(f"Contorno proposto: {ha} ha{incerto}")

    def _clique_copia(row, col):
        cam, i = sob_o_clique(row, col)
        if cam is None:
            win.avisa("Ligue CAR ou Talhões e clique dentro de um contorno", "info", 4000)
            return
        cs, rs = cam.aneis[i]
        pts = [(float(c), float(r)) for c, r in zip(cs, rs)]
        if len(pts) > 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        desenho.comeca(None, pts)
        estado["semente_dados"] = cam.dados(cam.attr[i])
        status(f"Contorno copiado de {cam.titulo} — ajuste os vértices ou conclua")

    def no_clique(ev):
        """⚠️ Roda ANTES do pixelClicked: no modo desenho o clique desenha, nao identifica."""
        if estado["modo"] == DESENHAR:
            if desenho.ativo:                       # Poligono, vertice a vertice
                if desenho.clique(ev) and not desenho.ativo:
                    confirma()                      # duplo-clique fechou
                atualiza_barra()
                return
            if desenho._roi is not None:            # contorno aberto para ajuste: os cliques sao dele
                return
            if ev.button() != Qt.MouseButton.LeftButton or ev.double():
                return
            p = view.vb.mapSceneToView(ev.scenePos())
            row, col = int(p.y()), int(p.x())
            if estado["ferramenta"] == AUTO:
                _clique_auto(row, col, ev.modifiers())
            elif estado["ferramenta"] == COPIAR:
                _clique_copia(row, col)
            atualiza_barra()
            return
        if estado["modo"] == EDITAR and ev.double():
            p = view.vb.mapSceneToView(ev.scenePos())
            f = cadastro.em(int(p.y()), int(p.x()))
            if f:
                dlg = DialogoFazenda(f, win)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    cadastro.salva(f["id"], None, dlg.dados())
                    cam_faz.redesenha()
                    tabs.fazendas.lista(cadastro, selecionar=f["id"])

    view.glw.scene().sigMouseClicked.connect(no_clique)
    barra_des.ferramenta.connect(usa_ferramenta)
    barra_des.desfazer.connect(desfaz)
    barra_des.concluir.connect(confirma)
    barra_des.cancelar.connect(cancela)

    # o que esta peca deixa para as outras
    ctx.cancela = cancela
    ctx.confirma = confirma
    ctx.desenho = desenho
    ctx.no_clique = no_clique
    ctx.usa_modo = usa_modo
    ctx.usa_ferramenta = usa_ferramenta
    ctx.desfaz_desenho = desfaz
    ctx.barra_des = barra_des
    ctx.atualiza_barra = atualiza_barra
