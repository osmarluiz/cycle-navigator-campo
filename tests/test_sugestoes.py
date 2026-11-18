# -*- coding: utf-8 -*-
"""A fila de sugestoes: o que a equipe escreve chega ao dev, e a resposta volta."""
from cycle_navigator.sugestoes import Caixa


def test_ida_e_volta_de_uma_sugestao(tmp_path):
    cx = Caixa(tmp_path / "sugestoes")
    assert cx.lista() == [] and cx.novidades() == 0
    s = cx.nova("o botao de gravar esta longe", quem="Ana", contexto={"safra": "2023/24"})
    assert s["status"] == "aberta" and cx.lista("aberta")[0]["id"] == s["id"]
    cx.mensagem(s["id"][:8], "O que mudou:\n- o botao subiu", autor="dev", status="implementada")
    assert cx.novidades() == 1 and cx.lista("aberta") == []
    assert cx.marca_vistas() == 1 and cx.novidades() == 0
    # a equipe responde em cima de uma entrega: reabre e volta para a fila do dev
    r = cx.mensagem(s["id"], "ainda ficou longe no notebook pequeno", quem="Ana")
    assert r["status"] == "aberta" and r["reaberta"] and len(r["mensagens"]) == 3


def test_duas_no_mesmo_segundo_nao_se_atropelam(tmp_path):
    cx = Caixa(tmp_path)
    a, b = cx.nova("uma"), cx.nova("outra")
    assert a["id"] != b["id"] and len(cx.lista()) == 2


def test_arquivo_danificado_e_posto_de_lado_nao_apagado(tmp_path):
    from cycle_navigator.arquivos import guarda_danificado
    p = tmp_path / "pontos_2023_24.json"
    p.write_text('{"points": [{"row": 1, "co')
    lado = guarda_danificado(p)
    assert not p.exists() and lado.exists() and lado.read_text().startswith('{"points"')
