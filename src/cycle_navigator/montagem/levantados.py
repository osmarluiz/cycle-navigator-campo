# -*- coding: utf-8 -*-
"""MONTAGEM · levantados: reabrir o que ja' foi gravado, ver todos, trocar a fonte da curva.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
from ..janela import IDENTIFICAR


def instala(ctx):
    ao_clicar = ctx.ao_clicar
    cam_sam = ctx.cam_sam
    estado = ctx.estado
    p_ciclo = ctx.p_ciclo
    p_pontos = ctx.p_pontos
    view = ctx.view
    win = ctx.win

    def ponto_gravado_em(row, col, i_sam):
        """(row, col) do ponto ja' gravado que este clique quer dizer, ou None: o do mesmo talhao
        (curva pela media) ou a bolinha a menos de ~12 px de tela do clique."""
        st = p_pontos.store
        if st is None or len(st) == 0:
            return None
        if st.find_at(row, col):
            return None                                    # ja' e' ele
        if i_sam is not None and estado["fonte"] == "talhao":
            x0, y0, x1, y1 = cam_sam.polys[i_sam].bounds
            for p in st.query(x0, y0, x1, y1):
                if cam_sam.em_idx(p["row"], p["col"]) == i_sam:
                    return int(p["row"]), int(p["col"])
        if estado["fonte"] == "talhao":
            from shapely.geometry import Point, Polygon
            for p in st.points:
                cont = p.get("contorno")
                if cont and len(cont) >= 3:
                    try:
                        if Polygon(cont).contains(Point(col + 0.5, row + 0.5)):
                            return int(p["row"]), int(p["col"])
                    except Exception:
                        pass
        raio = 12 * view.vb.viewRect().width() / max(1, view.width())
        perto = st.query(col - raio, row - raio, col + raio, row + raio)
        # ⚠️ clicar DENTRO DE OUTRO TALHAO nao reabre o vizinho so' porque a bolinha dele esta'
        # perto: com o mapa afastado, 12 px de tela sao centenas de metros.
        if i_sam is not None:
            perto = [q for q in perto if cam_sam.em_idx(q["row"], q["col"]) in (None, i_sam)]
        if perto:
            p = min(perto, key=lambda q: (q["row"] - row) ** 2 + (q["col"] - col) ** 2)
            return int(p["row"]), int(p["col"])
        return None

    def ve_levantados():
        """Enquadra todos os talhoes levantados da safra: 'o que eu ja' fiz?' de uma olhada."""
        st = p_pontos.store
        pts = list(st.points) if st is not None else []
        if not pts:
            win.avisa("Nenhum talhão levantado nesta safra ainda", "info")
            return
        xs = [p["col"] for p in pts]; ys = [p["row"] for p in pts]
        m = max(300, 0.15 * max(max(xs) - min(xs), max(ys) - min(ys)))
        view.vb.setRange(xRange=(min(xs) - m, max(xs) + m), yRange=(min(ys) - m, max(ys) + m),
                         padding=0)
        win.avisa(f"{len(pts)} levantado(s) nesta safra — clique numa bolinha para reabrir; "
                  "a lista está em Tabelas", "info", 5000)

    def recado_camada(cam, nome, on):
        """⚠️ Ligar a camada afastado demais nao desenha nada (ver car.py): sem recado, parecia
        que o botao nao tinha funcionado."""
        if not on:
            win.avisa(f"{nome}: contornos desligados", "info", 1600)
        elif cam.escondida:
            win.avisa(f"{nome} ligados — aproxime o mapa para ver os contornos", "info", 4000)
        else:
            n = f"{cam.em_vista:,}".replace(",", ".")
            win.avisa(f"{nome}: {n} contornos na vista — clique num para ver os dados", "info")

    def troca_fonte(f):
        """Talhao <-> Ponto: reabre o mesmo clique com a outra curva, sem perder o que ja' se disse."""
        estado["fonte"] = f
        if p_ciclo.rc is not None and estado["modo"] == IDENTIFICAR:
            manter = p_ciclo.segmentos() if p_ciclo._tocado else None
            ao_clicar(*p_ciclo.rc, manter=manter)

    # o que esta peca deixa para as outras
    ctx.ponto_gravado_em = ponto_gravado_em
    ctx.recado_camada = recado_camada
    ctx.troca_fonte = troca_fonte
    ctx.ve_levantados = ve_levantados
