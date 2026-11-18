# -*- coding: utf-8 -*-
"""O que a tabela de talhoes diz sem abrir janela nenhuma."""
from cycle_navigator.tabelas import _sem_acento, confianca_do_ponto, resumo_faixas


def test_confianca_do_talhao_e_a_pior_das_faixas():
    pt = {"ciclos": [{"confianca": "certo"}, {"confianca": "acho que"}]}
    assert confianca_do_ponto(pt) == "Acho que"
    assert confianca_do_ponto({"ciclos": [{"confianca": "certo"}]}) == "Certo"
    assert confianca_do_ponto({"ciclos": [{"confianca": "nao sei"}, {"confianca": "acho que"}]}) == "Não sei"
    assert confianca_do_ponto({}) == ""


def test_filtro_nao_liga_para_acento_nem_maiuscula():
    assert _sem_acento("José AÇÃO") == "jose acao"
    assert "feijao" in _sem_acento(resumo_faixas({"ciclos": [{"cultura": "Feijão", "confianca": "certo",
                                                             "mes_ini": 202310, "mes_fim": 202402}]}))
