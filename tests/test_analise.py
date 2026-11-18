# -*- coding: utf-8 -*-
"""A tela de analise resume o que foi gravado: os numeros dela tem de bater com os pontos."""
from cycle_navigator.analise import pendencias, resume

MESES = [202310, 202311, 202312, 202401, 202402, 202403, 202404, 202405, 202406, 202407, 202408, 202409]


def _pt(i, faixas, **k):
    cic = [{"cultura": c, "mes_ini": a, "mes_fim": b, "confianca": conf} for c, a, b, conf in faixas]
    d = dict(id=i, row=i, col=i, ciclos=cic, produtor="Joao", fonte_curva="talhao",
             curve=[[0.05, 0.08, 0.1, 0.3]] * 12)
    d.update(k)
    return d


def test_resume_conta_sistemas_hectares_e_calendario():
    pts = [_pt(1, [("Soja", 202310, 202402, "certo"), ("Milho safrinha", 202403, 202407, "certo")],
               talhao_ha=10.0, sam_id=7),
           _pt(2, [("Soja", 202310, 202402, "certo")], talhao_ha=5.5, sam_id=8),
           _pt(3, [("Soja", 202311, 202403, "acho que")], sam_id=8, produtor="")]
    r = resume(pts, MESES)
    assert r["n"] == 3 and abs(r["ha"] - 15.5) < 1e-9 and r["sem_area"] == 1
    sist = dict(r["sistemas"])
    assert sist["Soja"]["n"] == 2 and sist["Soja > Milho safrinha"]["n"] == 1
    assert list(r["calendario"]["Soja"][:6]) == [2, 3, 3, 3, 3, 1]
    assert r["calendario"]["Milho safrinha"][5] == 1 and r["calendario"]["Milho safrinha"][10] == 0
    # 2 e 3 estao no mesmo talhao; o 3 ainda tem duvida e esta' sem produtor
    motivos = {p["id"]: m for p, m in r["conferir"]}
    assert set(motivos) == {2, 3}
    assert any("mais de uma vez" in x for x in motivos[2])
    assert any("dúvida" in x for x in motivos[3]) and "sem produtor" in motivos[3]


def test_ponto_limpo_nao_tem_pendencia_e_safra_vazia_nao_quebra():
    assert pendencias(_pt(1, [("Soja", 202310, 202402, "certo")], talhao_ha=3.0)) == []
    r = resume([], MESES)
    assert r["n"] == 0 and r["sistemas"] == [] and r["conferir"] == []
