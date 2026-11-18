# -*- coding: utf-8 -*-
"""MONTAGEM · curvas: a curva media de um talhao ou de um poligono qualquer.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import numpy as np
import warnings


def instala(ctx):
    _curvas = ctx._curvas
    cam_sam = ctx.cam_sam
    ts_todo = ctx.ts_todo

    def curva_do_talhao(i):
        """A curva MEDIA do talhao i do SAM: (curva (T, bandas), n de amostras) ou (None, 0).

        ⚠️ O produtor descreve o TALHAO, nao um pixel de 4,8 m. A curva de um pixel carrega o ruido
        dele (uma arvore, um carreador, a borda do pivo); a media do talhao e' a resposta sobre o
        que a pessoa esta' apontando. O contorno e' encolhido 1,5 px para nao misturar o vizinho, e
        talhao grande e' lido decimado (os overviews fazem isso barato): ate' ~48 x 48 amostras.
        """
        return curva_do_poligono(cam_sam.polys[i], i)

    def curva_do_poligono(poly, chave):
        """A mesma media, para qualquer poligono em pixels (talhao pronto ou recortado na hora)."""
        i = chave
        if i in _curvas:
            return _curvas[i]
        import shapely
        dentro = poly.buffer(-1.5)
        if dentro.is_empty:
            dentro = poly
        c0, r0, c1, r1 = dentro.bounds
        c0, r0 = int(np.floor(c0)), int(np.floor(r0))
        w, h = max(1, int(np.ceil(c1)) - c0), max(1, int(np.ceil(r1)) - r0)
        passo = max(1, int(np.ceil(max(h, w) / 48)))
        bloco = ts_todo.read_block(r0, c0, h, w, passo)          # (Hs, Ws, T, bandas)
        hs, ws = bloco.shape[:2]
        xs = c0 + (np.arange(ws) + 0.5) * w / ws
        ys = r0 + (np.arange(hs) + 0.5) * h / hs
        X, Y = np.meshgrid(xs, ys)
        m = shapely.contains_xy(dentro, X, Y)
        if int(m.sum()) < 4:
            res = (None, 0)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)      # mes todo nodata -> NaN
                res = (np.nanmean(bloco[m].astype(np.float64), axis=0), int(m.sum()))
        _curvas.clear()                                              # guarda so' o ultimo
        _curvas[i] = res
        return res
    _fontes = {}

    # o que esta peca deixa para as outras
    ctx._fontes = _fontes
    ctx.curva_do_poligono = curva_do_poligono
    ctx.curva_do_talhao = curva_do_talhao
