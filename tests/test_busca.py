# -*- coding: utf-8 -*-
"""A busca le^ a coordenada do jeito que as pessoas colam."""
import pytest

from cycle_navigator.busca import coordenada

BRASILIA = (-15.7939, -47.8828)


@pytest.mark.parametrize("txt, esperado", [
    ("-15.7939, -47.8828", BRASILIA), ("-15,7939 -47,8828", BRASILIA), ("(-15.7939, -47.8828)", BRASILIA),
    ("15.7939S 47.8828W", BRASILIA), ("S 15.7939 W 47.8828", BRASILIA), ("15,7939 S; 47,8828 O", BRASILIA),
    ("lat -15.7939 lon -47.8828", BRASILIA), ("Lat: -15,7939 Long: -47,8828", BRASILIA),
    ("15°47'38.0\"S 47°52'58.0\"W", BRASILIA), ("15 47 38 S, 47 52 58 W", BRASILIA),
    ("15 47.634 S 47 52.968 W", BRASILIA), ("-47.8828 -15.7939", (-47.8828, -15.7939)),
    ("15,47", (15.0, 47.0)), ("-15,-47", (-15.0, -47.0)),
])
def test_formatos_de_coordenada(txt, esperado):
    r = coordenada(txt)
    assert r is not None and r == pytest.approx(esperado, abs=2e-4)


def test_utm_23_sul_vira_graus():
    lat, lon = coordenada("219578 8178548")
    assert -17 < lat < -16 and -48 < lon < -47


@pytest.mark.parametrize("txt", ["brasilia", "GO-5200258-ABCD", "999", "", "DF-5300108", "Cristalina 12"])
def test_o_que_nao_e_coordenada(txt):
    assert coordenada(txt) is None
