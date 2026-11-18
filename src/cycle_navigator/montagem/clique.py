# -*- coding: utf-8 -*-
"""MONTAGEM · clique: o clique no mapa: de onde vem a curva e o que o painel mostra.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
import numpy as np
from .. import estilo
from ..janela import DESENHAR
from ..janela import EDITAR
from ..janela import IDENTIFICAR

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
    pede_recorte = ctx.pede_recorte
    poe_alfinete = ctx.poe_alfinete
    recorte = ctx.recorte
    recorte_gravado = ctx.recorte_gravado
    sob_o_clique = ctx.sob_o_clique
    status = ctx.status
    tabs = ctx.tabs
    ts_todo = ctx.ts_todo
    usa_modo = ctx.usa_modo
    win = ctx.win

    # ---------------- clique no mapa ----------------
    def clique_do_mapa(row, col):
        """⇧ clique e ⌥ clique corrigem o recorte aberto ("isto tambem" / "isto nao")."""
        mods = QApplication.keyboardModifiers()
        rec = estado.get("recorte")
        corrige = None
        if mods & Qt.KeyboardModifier.ShiftModifier:
            corrige = 1
        elif mods & Qt.KeyboardModifier.AltModifier:
            corrige = 0
        if (corrige is not None and rec and recorte.ok and estado["modo"] == IDENTIFICAR
                and p_ciclo.rc is not None):
            novo = pede_recorte(rec["pontos"] + [(int(row), int(col), corrige)])
            if novo is None:
                win.avisa("Não consegui recortar com essa correção", "info")
                return
            manter = p_ciclo.segmentos() if p_ciclo._tocado else None
            ao_clicar(*p_ciclo.rc, manter=manter, rec=novo)
            return
        ao_clicar(row, col)

    def ao_clicar(row, col, manter=None, rec=None):
        if estado["modo"] == DESENHAR:
            return
        if estado["modo"] == EDITAR:
            f = cadastro.em(row, col)
            if f:
                tabs.fazendas.lista(cadastro, selecionar=f["id"])
                usa_modo(DESENHAR, f["id"])      # vertices editaveis
                return
            # ⚠️ clicar num imovel do CAR que ainda nao e' fazenda SELECIONA e abre para editar:
            # o contorno vira poligono editavel na hora, Enter abre o cadastro.
            cam, i = sob_o_clique(row, col)
            if cam is not None:
                cs, rs = cam.aneis[i]
                pts = [(float(c), float(r)) for c, r in zip(cs, rs)]
                if len(pts) > 2 and pts[0] == pts[-1]:
                    pts = pts[:-1]
                usa_modo(DESENHAR, None, semente=(pts, cam.dados(cam.attr[i])))
                status(f"{cam.titulo} selecionado — ajuste os vértices ou dê Enter para cadastrar")
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
        # ⚠️ RECORTE NA HORA. Tres caminhos chegam aqui: (1) o ponto ja' foi gravado com um
        # contorno recortado -> reabre com ele, sem chamar o modelo; (2) a fonte escolhida e'
        # "Recortar"; (3) a fonte e' "Talhao" mas nao ha' talhao pronto sob o clique.
        if rec is None and estado["fonte"] != "pixel":
            gravado = p_pontos.store.find_at(row, col) if p_pontos.store is not None else None
            if gravado and gravado.get("fonte_curva") == "recorte" and estado["fonte"] == "talhao":
                rec = recorte_gravado(gravado)
            elif recorte.ok and (estado["fonte"] == "recorte" or i_sam is None):
                rec = pede_recorte([(int(row), int(col), 1)])
                # ⚠️ fora de lavoura (cerrado, cidade, represa) o modelo devolve "talhoes" de
                # milhares de hectares com nota baixa. Sem ninguem ter pedido o recorte, isso e'
                # ruido: fica o ponto. Pedido de proposito ("Recortar"), so' o absurdo e' recusado.
                if rec is not None:
                    ha = rec["poli"].area * PX_HA
                    pedido = estado["fonte"] == "recorte"
                    if ha > (3000 if pedido else 400) or (not pedido and rec["nota"] < 0.75):
                        rec = None
                if rec is None and estado["fonte"] == "recorte":
                    win.avisa("Não consegui recortar um talhão aqui — mostrando só o ponto", "info")
        if rec is not None:
            try:
                curva, n_am = curva_do_poligono(rec["poli"], ("rec", rec["poli"].wkb))
            except Exception as e:
                log.warning("media do recorte indisponivel em (%d,%d): %s", row, col, e)
            if curva is None or not np.isfinite(curva).any():
                rec, curva = None, None
        if rec is None and i_sam is not None and estado["fonte"] != "pixel":
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
            titulo = f"Talhão de {br(rec['poli'].area * PX_HA)} ha"
            n_cor = len(rec["pontos"]) - 1
            # nota baixa = o modelo nao tinha certeza do que era "isto": dizer, em vez de esconder
            incerto = (f" · <span style='color:#e0a23a'>contorno incerto — confira</span>"
                       if 0 < rec["nota"] < 0.8 else "")
            sub = ["recortado agora" + (f" com {n_cor} correção(ões)" if n_cor else "") + incerto,
                   f"média de {n_am} amostras", "⇧ clique soma · ⌥ clique tira"]
        elif do_talhao:
            ha = cam_sam.polys[i_sam].area * cam_sam.px_ha
            titulo = f"Talhão de {br(ha)} ha"
            sub = [f"média de {n_am} amostras do talhão"]
        else:
            titulo = "Ponto"
            sub = [f"um pixel de {br(abs(classe.transform.a))} m"]
        if faz is not None and (faz.get("nome") or faz.get("proprietario")):
            sub.insert(0, f"<b>{faz.get('nome') or faz.get('proprietario')}</b>")
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
        p_ciclo.define_fonte(i_sam is not None or rec is not None,
                             "recorte" if (rec is not None and estado["fonte"] == "recorte") else
                             "talhao" if (do_talhao or rec is not None) else "pixel",
                             recorte=recorte.ok)
        p_ciclo.mostra(row, col, curva, cfg.meses, janela=cfg.meses_de(estado["safra"]),
                       ja_gravado=faixas, produtor=produtor, titulo=titulo,
                       subtitulo=" &nbsp;·&nbsp; ".join(sub))

    # o que esta peca deixa para as outras
    ctx.ao_clicar = ao_clicar
    ctx.clique_do_mapa = clique_do_mapa
