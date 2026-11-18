# -*- coding: utf-8 -*-
"""O padrao do codigo (trazido do iRest): pasta por assunto, arquivo pequeno.

`app.py` chegou a ter 1.200 linhas numa funcao so' -- mudar uma coisa era ler tudo. A montagem foi
cortada em pecas (`montagem/`), uma por assunto, e este teste impede a volta: peca nova que passar do
limite tem de ser cortada, nao tolerada.
"""
from pathlib import Path

import cycle_navigator

RAIZ = Path(cycle_navigator.__file__).parent
LIMITE = 300
# ⚠️ divida conhecida, anterior ao padrao: entram no limite quando forem cortados. Nao acrescentar.
GRANDES = {"ciclos.py": 900, "janela.py": 500, "analise.py": 440, "fazendas.py": 360, "car.py": 320}


def _linhas(p):
    return len(p.read_text(encoding="utf-8").splitlines())


def test_pecas_da_montagem_sao_pequenas():
    grandes = {p.name: _linhas(p) for p in (RAIZ / "montagem").glob("*.py") if _linhas(p) > LIMITE}
    assert not grandes, f"pecas acima de {LIMITE} linhas: {grandes}"


def test_nenhum_arquivo_cresce_alem_do_que_ja_era():
    fora = {}
    for p in RAIZ.glob("*.py"):
        teto = GRANDES.get(p.name, LIMITE)
        if _linhas(p) > teto:
            fora[p.name] = (_linhas(p), teto)
    assert not fora, f"arquivos acima do teto (linhas, teto): {fora}"


def test_toda_peca_tem_instala_e_esta_na_ordem():
    from cycle_navigator import montagem
    nomes = {m.__name__.rsplit(".", 1)[-1] for m in montagem.ORDEM}
    arquivos = {p.stem for p in (RAIZ / "montagem").glob("*.py")} - {"__init__", "fontes"}
    assert nomes == arquivos and all(callable(m.instala) for m in montagem.ORDEM)
