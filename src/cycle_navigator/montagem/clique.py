# -*- coding: utf-8 -*-
"""MONTAGEM · clique: o clique no mapa: de onde vem a curva e o que o painel mostra.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
import numpy as np
from .. import estilo
from ..janela import DESENHAR
from ..janela import IDENTIFICAR
from PyQt6.QtWidgets import QMessageBox

log = logging.getLogger(__name__)


def instala(ctx):
    PX_HA = ctx.PX_HA
    cadastro = ctx.cadastro
    cam_car = ctx.cam_car
    cam_sam = ctx.cam_sam
    camadas = ctx.camadas
    cfg = ctx.cfg
    classe = ctx.classe
    curva_do_poligono = ctx.curva_do_poligono
    curva_do_talhao = ctx.curva_do_talhao
    desenha_recorte = ctx.desenha_recorte
    estado = ctx.estado
    latlon = ctx.latlon
    p_ciclo = ctx.p_ciclo
    p_pontos = ctx.p_pontos
    poe_alfinete = ctx.poe_alfinete
    recorte_gravado = ctx.recorte_gravado
    sob_o_clique = ctx.sob_o_clique
    status = ctx.status
    tabs = ctx.tabs
    ts_todo = ctx.ts_todo
    usa_modo = ctx.usa_modo
    win = ctx.win

    # ---------------- clique no mapa ----------------
    def _assinatura():
        return (tuple((s["ini"], s["fim"], s["cultura"], s["confianca"]) for s in p_ciclo.segmentos()),
                p_ciclo.ed_produtor.text().strip())

    def marca_limpo():
        estado["limpo"] = _assinatura() if p_ciclo.rc is not None else None

    def pode_sair():
        """⚠️⚠️ NADA DITO PELO PRODUTOR SE PERDE CALADO. Sair de um ponto com cultura nomeada e nao
        gravada (outro clique, outro modo) descartava tudo sem aviso. Agora pergunta -- e so' quando
        ha' de fato algo nomeado e diferente do que esta' gravado."""
        if p_ciclo.rc is None or estado.get("limpo") is None or _assinatura() == estado["limpo"]:
            return True
        if not any(s["cultura"] for s in p_ciclo.segmentos()):
            return True
        cx = QMessageBox(win)
        cx.setWindowTitle("Faixas não gravadas")
        cx.setText("Você nomeou as faixas deste ponto e ainda não gravou.")
        grava = cx.addButton("Gravar", QMessageBox.ButtonRole.AcceptRole)
        larga = cx.addButton("Descartar", QMessageBox.ButtonRole.DestructiveRole)
        cx.addButton("Voltar", QMessageBox.ButtonRole.RejectRole)
        cx.setDefaultButton(grava)
        cx.exec()
        if cx.clickedButton() is larga:
            return True
        if cx.clickedButton() is grava:
            p_ciclo._emite()
            return _assinatura() == estado.get("limpo")      # gravou de fato (tinha levantador)?
        return False

    def clique_do_mapa(row, col):
        if estado["modo"] == IDENTIFICAR and not pode_sair():
            return
        ao_clicar(row, col)

    def ao_clicar(row, col, manter=None, rec=None):
        if estado["modo"] == DESENHAR:
            return
        i_sam = cam_sam.em_idx(row, col) if cam_sam is not None else None
        # ⚠️ CLICAR DE NOVO NO MESMO TALHAO REABRE O QUE FOI GRAVADO. O deposito procura o pixel
        # EXATO; sem isto o segundo clique (2 m ao lado) abria um talhao "novo" e gravava um
        # segundo ponto no mesmo lugar.
        if manter is None and rec is None:
            ja = ctx.ponto_gravado_em(row, col, i_sam)
            if ja is not None:
                row, col = ja
        curva, n_am = None, 0
        # ⚠️⚠️ IDENTIFICAR NAO RECORTA. O SAM e' ferramenta do Desenhar (ver barra_desenho.py); aqui
        # o clique so' LE^: a serie do pixel -- ou, se pedida, a media do talhao pronto -- e a
        # fazenda do lugar. Excecao unica: ponto antigo gravado com contorno recortado reabre com ele.
        if rec is None and estado["fonte"] == "talhao":
            gravado = p_pontos.store.find_at(row, col) if p_pontos.store is not None else None
            if gravado and gravado.get("fonte_curva") == "recorte":
                rec = recorte_gravado(gravado)
        if rec is not None:
            try:
                curva, n_am = curva_do_poligono(rec["poli"], ("rec", rec["poli"].wkb))
            except Exception as e:
                log.warning("media do recorte indisponivel em (%d,%d): %s", row, col, e)
            if curva is None or not np.isfinite(curva).any():
                rec, curva = None, None
        if rec is None and i_sam is not None and estado["fonte"] == "talhao":
            try:
                curva, n_am = curva_do_talhao(i_sam)
            except Exception as e:
                log.warning("media do talhao indisponivel em (%d,%d): %s", row, col, e)
        do_talhao = rec is None and curva is not None and np.isfinite(curva).any()
        if rec is None and not do_talhao:
            curva = None
        estado["recorte"] = rec
        desenha_recorte(rec)
        if curva is None:
            try:
                curva = ts_todo.read_curve(row, col)
            except Exception as e:
                log.warning("curva indisponivel em (%d,%d): %s", row, col, e)
                return
        if not np.isfinite(curva).any():
            win.avisa("Sem imagem neste ponto", "info")
            log.info("pixel (%d,%d) sem dado em nenhum mes", row, col)
            return
        faixas, produtor = p_pontos.existente(row, col)
        ja_levantado = bool(faixas)
        if manter:
            faixas = manter
        faz = cadastro.em(row, col)
        ctx.lugar.mostra_fazenda(faz)
        # ⚠️ com o CAR/SAM ligado, o clique tambem SELECIONA o contorno sob o pixel: destaque e
        # cartao com os dados. Nao muda de modo nem adota -- so' mostra.
        cam, i = sob_o_clique(row, col)
        for c in camadas:
            if c is not cam:
                c.limpa_selecao()
        if cam is not None:
            cam.seleciona(i)
        # o talhao que deu a curva fica contornado mesmo com a camada desligada: e' ele a resposta
        # a "esta curva e' de onde?"
        if do_talhao and cam is not cam_sam:
            cam_sam.seleciona(i_sam, cartao=False)
        elif rec is not None and cam_sam is not None and cam is not cam_sam:
            cam_sam.limpa_selecao()             # o contorno que vale agora e' o recortado
        poe_alfinete(row, col)
        estado["sam"] = i_sam if do_talhao else None
        if faz is not None and not produtor:
            produtor = faz.get("proprietario") or faz.get("nome") or ""

        def br(v, casas=1):
            return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if rec is not None:
            titulo = f"Média do talhão de {br(rec['poli'].area * PX_HA)} ha"
            sub = [f"{n_am} amostras do contorno gravado"]
        elif do_talhao:
            ha = cam_sam.polys[i_sam].area * cam_sam.px_ha
            titulo = f"Média do talhão de {br(ha)} ha"
            sub = [f"{n_am} amostras"]
        else:
            titulo = "Pixel"
            sub = [f"{br(abs(classe.transform.a))} m"]
        if cam_car is not None:
            k = cam_car.em_idx(row, col)
            mun = str(cam_car.attr[k].get("municipio") or "").strip() if k is not None else ""
            if mun:
                sub.append(mun.title())
        ll = latlon(row, col)
        if ll:
            sub.append(f"{ll[0]:.5f}, {ll[1]:.5f}")
        if ja_levantado:
            sub.append(f"<span style='color:{estilo.ACCENT}'>já levantado</span>")
        # a fazenda do lugar NAO entra aqui: ela tem a sua aba (painel_lugar.py), e o rotulo da aba
        # ja' diz o nome dela
        subtitulo = " &nbsp;·&nbsp; ".join(sub)
        p_ciclo.define_fonte(i_sam is not None or rec is not None,
                             "talhao" if (do_talhao or rec is not None) else "pixel")
        p_ciclo.mostra(row, col, curva, cfg.meses, janela=cfg.meses_de(estado["safra"]),
                       ja_gravado=faixas, produtor=produtor, titulo=titulo,
                       subtitulo=subtitulo)
        if not manter:
            marca_limpo()

    # o que esta peca deixa para as outras
    ctx.ao_clicar = ao_clicar
    ctx.clique_do_mapa = clique_do_mapa
    ctx.marca_limpo = marca_limpo
    ctx.pode_sair = pode_sair
