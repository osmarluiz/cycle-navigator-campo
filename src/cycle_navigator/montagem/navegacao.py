# -*- coding: utf-8 -*-
"""MONTAGEM · navegacao: ir ate' um ponto ou fazenda; excluir um ponto.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
from PyQt6.QtWidgets import QMessageBox
from ..janela import IDENTIFICAR


def instala(ctx):
    ao_clicar = ctx.ao_clicar
    cadastro = ctx.cadastro
    cam_pontos = ctx.cam_pontos
    conta = ctx.conta
    estado = ctx.estado
    p_ciclo = ctx.p_ciclo
    p_pontos = ctx.p_pontos
    refresca_analise = ctx.refresca_analise
    tabs = ctx.tabs
    usa_modo = ctx.usa_modo
    view = ctx.view
    win = ctx.win

    # ---------------- tabela ----------------
    def centra(col, row, meia=600):
        """Enquadra o mapa num ponto (col/row em pixel) com uma margem."""
        view.vb.setRange(xRange=(col - meia, col + meia), yRange=(row - meia, row + meia),
                         padding=0)

    def vai_ao_ponto(row, col):
        """Da linha da tabela ao mapa E a' curva: e' assim que se confere um rotulo."""
        usa_modo(IDENTIFICAR)
        centra(col, row)
        ao_clicar(row, col)
        win.raise_(); win.activateWindow()

    def centra_fazenda(fid):
        f = cadastro.por_id(fid)
        poli = (f or {}).get("poligono") or []
        if not poli:
            return
        xs = [q[0] for q in poli]; ys = [q[1] for q in poli]
        meia = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.7 + 50
        centra((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, meia)
        win.raise_(); win.activateWindow()

    def exclui_ponto(row, col):
        if p_pontos.store is None:
            return
        # ⚠️ a pergunta DIZ o que vai ser excluido: "este ponto" nao deixava ver que se estava na aba
        # de pontos e nao na de fazendas
        alvo = p_pontos.store.find_at(row, col) or {}
        que = f"o ponto nº {alvo.get('id', '?')} ({alvo.get('class') or 'sem cultura'}"
        que += f", {alvo['produtor']})" if alvo.get("produtor") else ")"
        if QMessageBox.question(tabs, "Excluir ponto", f"Excluir {que}?\n\nAs fazendas não são afetadas."
                                ) != QMessageBox.StandardButton.Yes:
            return
        # ⚠️ o excluido fica guardado (so' o ultimo, so' enquanto o programa esta' aberto): com o
        # produtor ao lado, um clique errado em "Excluir" nao pode custar a conversa inteira
        velho = p_pontos.store.find_at(row, col)
        estado["excluido"] = (estado["safra"], dict(velho)) if velho is not None else None
        p_pontos.store.remove_at(row, col)
        _depois_de_mexer(row, col)
        tabs.pontos.bt_desfaz.setEnabled(estado["excluido"] is not None)
        import sys
        tecla = "⌘Z" if sys.platform == "darwin" else "Ctrl+Z"
        win.avisa(f"Ponto excluído  ·  {tecla} desfaz", "info", 6000)

    def _depois_de_mexer(row, col):
        p_pontos.atualiza_info()
        cam_pontos.redesenha()
        tabs.pontos.lista(p_pontos.store)
        conta()
        refresca_analise()
        if p_ciclo.rc == (row, col) and estado["modo"] == IDENTIFICAR:
            ao_clicar(row, col)                 # o painel aberto volta a dizer a verdade

    def desfaz_exclusao():
        guardado = estado.get("excluido")
        st = p_pontos.store
        if not guardado or st is None:
            return
        safra, pt = guardado
        if safra != estado["safra"]:
            win.avisa(f"O ponto excluído é da safra {safra}: volte a ela para desfazer", "info", 5000)
            return
        if st.find_at(pt["row"], pt["col"]) is not None:      # ja' regravaram no mesmo lugar
            win.avisa("Já existe um ponto gravado nesse lugar", "info")
            return
        if any(q.get("id") == pt.get("id") for q in st.points):
            pt["id"] = max(q["id"] for q in st.points) + 1
        st.points.append(pt)
        st._reindex()
        st.save()
        estado["excluido"] = None
        tabs.pontos.bt_desfaz.setEnabled(False)
        _depois_de_mexer(pt["row"], pt["col"])
        win.avisa("Ponto de volta", "ok")

    # o que esta peca deixa para as outras
    ctx.centra = centra
    ctx.centra_fazenda = centra_fazenda
    ctx.exclui_ponto = exclui_ponto
    ctx.desfaz_exclusao = desfaz_exclusao
    ctx.vai_ao_ponto = vai_ao_ponto
