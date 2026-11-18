# -*- coding: utf-8 -*-
"""MONTAGEM · gravacao: gravar o talhao e o recado do CAR.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
from ..janela import IDENTIFICAR

log = logging.getLogger(__name__)


def instala(ctx):
    PX_HA = ctx.PX_HA
    cadastro = ctx.cadastro
    cam_car = ctx.cam_car
    cam_pontos = ctx.cam_pontos
    cam_sam = ctx.cam_sam
    cfg = ctx.cfg
    conta = ctx.conta
    estado = ctx.estado
    p_ciclo = ctx.p_ciclo
    p_pontos = ctx.p_pontos
    refresca_analise = ctx.refresca_analise
    status = ctx.status
    tabs = ctx.tabs
    win = ctx.win

    def ao_gravar(segmentos):
        if p_ciclo.rc is None:
            return
        row, col = p_ciclo.rc
        if not p_pontos.levantador:
            # ⚠️ recado e foco no campo, nao caixa de dialogo: a caixa pedia um OK e deixava a
            # pessoa procurando onde digitar.
            win.avisa("Antes de gravar, diga quem está levantando", "erro", 4000)
            win.barra.ed_levantador.setFocus()
            return
        faz = cadastro.em(row, col)
        # ⚠️ grava a curva DA SAFRA (12 x 4), nao a serie inteira (54 x 4). O rotulo e' sobre
        # esta safra; a serie toda custaria 4,5x o tamanho por ponto para nao dizer nada a mais.
        idx = [cfg.meses.index(m) for m in cfg.meses_de(estado["safra"])]
        pt, atualizou = p_pontos.registra(row, col, p_ciclo.curva[idx], segmentos,
                                          p_ciclo.produtor, fazenda=faz)
        log.info("%s talhao #%d: %s", "atualizado" if atualizou else "gravado",
                 pt["id"], pt["class"])
        # de onde veio a curva gravada: a media de um talhao e a de um pixel nao sao a mesma medida
        i_sam = estado.get("sam")
        rec = estado.get("recorte")
        for k in ("contorno", "recorte_pontos", "recorte_nota"):
            pt.pop(k, None)
        pt["fonte_curva"] = "recorte" if rec else "talhao" if i_sam is not None else "pixel"
        if rec:
            # ⚠️ o contorno recortado vai gravado COM o ponto: e' ele que reabre, e e' ele a
            # resposta a "esta curva e' a media de que area?". O modelo nao e' chamado de novo.
            pt["contorno"] = [[round(float(x), 1), round(float(y), 1)]
                              for x, y in rec["poli"].exterior.coords]
            pt["recorte_pontos"] = [[int(r), int(c), int(l)] for r, c, l in rec["pontos"]]
            pt["recorte_nota"] = round(float(rec["nota"]), 3)
            pt["talhao_ha"] = round(float(rec["poli"].area * PX_HA), 2)
            pt.pop("sam_id", None)
        elif i_sam is not None:
            pt["sam_id"] = int(cam_sam.attr[i_sam].get("id") or 0)
            pt["talhao_ha"] = round(float(cam_sam.polys[i_sam].area * cam_sam.px_ha), 2)
        else:
            pt.pop("sam_id", None); pt.pop("talhao_ha", None)
        p_pontos.store.save()
        cam_pontos.redesenha()
        tabs.pontos.lista(p_pontos.store)
        conta()
        refresca_analise()
        win.avisa(("Atualizado · " if atualizou else "Gravado · ") + str(pt["class"]))

    # ---------------- CAR ----------------
    def aviso_car():
        """Diz na barra por que os perimetros nao aparecem, quando nao aparecem."""
        # no modo Identificar a barra e' do talhao clicado; nos outros, da camada
        if cam_car is None or estado["modo"] == IDENTIFICAR or not win.barra.bt_car.isChecked():
            return
        n = f"{cam_car.em_vista:,}".replace(",", ".")
        if cam_car.escondida:
            status(f"CAR: {n} imóveis — aproxime para vê-los")
        elif cam_car.em_vista == 0:
            status("CAR: nenhum imóvel na vista")
        else:
            status(f"CAR: {n} imóveis na vista" + (" · contornos simplificados"
                                                    if cam_car.simplificada else ""))

    # o que esta peca deixa para as outras
    ctx.ao_gravar = ao_gravar
    ctx.aviso_car = aviso_car
