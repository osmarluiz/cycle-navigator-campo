# -*- coding: utf-8 -*-
"""A geometria do recorte na hora, sem o modelo: blocos, segunda passada e contorno."""
import numpy as np

from cycle_navigator.recorte import FATOR_CAIXA, N, RecorteVivo, bloco_da_caixa


def _disco(raio, cy=N // 2, cx=N // 2):
    y, x = np.ogrid[:N, :N]
    return (y - cy) ** 2 + (x - cx) ** 2 <= raio ** 2


def test_bloco_da_caixa_e_centrado_e_da_vizinhanca():
    r0, c0, lado = bloco_da_caixa((1000, 2000, 1100, 2200))
    assert lado == round(200 * FATOR_CAIXA)
    assert (r0 + lado / 2, c0 + lado / 2) == (1050, 2100)
    assert bloco_da_caixa((0, 0, 10, 10))[2] == 256          # caixa minuscula ainda tem contexto


def test_bloco_fino_so_quando_amplia():
    rv = RecorteVivo.__new__(RecorteVivo)
    bloco = (5000, 7000, 1024)
    fino = rv._bloco_fino(_disco(100), bloco)                # objeto de 200 px num bloco de 1024
    assert fino is not None and 235 <= fino[2] <= 245        # 20% maior que a mascara
    assert abs(fino[0] + fino[2] / 2 - 5512) <= 1 and abs(fino[1] + fino[2] / 2 - 7512) <= 1
    assert rv._bloco_fino(_disco(400), bloco) is None        # ja' ocupa o bloco: nao ha' o que ampliar


def test_segunda_passada_so_vale_se_for_o_mesmo_objeto():
    bloco, fino = (0, 0, 1024), (384, 384, 256)              # fino = centro do bloco, ampliado 4x
    primeira = _disco(100)
    assert RecorteVivo._concorda(primeira, bloco, _disco(400), fino) is True
    assert RecorteVivo._concorda(primeira, bloco, _disco(60, 200, 200), fino) is False


def test_poligono_volta_para_a_grade():
    bloco = (5000, 7000, 512)                                # cada pixel do modelo = 0,5 px da grade
    p = RecorteVivo._poligono(_disco(200), bloco, [(5256, 7256, 1)])
    assert abs(p.area - np.pi * 100 ** 2) / (np.pi * 100 ** 2) < 0.02
    assert abs(p.centroid.x - 7256) < 1 and abs(p.centroid.y - 5256) < 1
