# -*- coding: utf-8 -*-
"""O ARTIGO AFIRMA QUE ESTE REPOSITORIO NAO TEM MOTOR PROPRIO. Estes testes cobram isso.

A frase publicada e' que o que o usuario arrasta na ferramenta e' o mesmo codigo que produziu os
numeros do artigo. Ela e' verdadeira enquanto o motor fenometrico vier do pacote `pheno-engine`, e
falsa no dia em que alguem copiar `pheno.py` para ca' "para simplificar" ou "para nao depender de
outro repo". O modo de falha e' silencioso: tudo continua rodando, os numeros e' que deixam de ser os
mesmos, e nenhum revisor teria como perceber.

Sao quatro perguntas:
  1. existe arquivo de motor DENTRO deste repositorio?          (copia explicita)
  2. o motor que importamos vem mesmo de `pheno_engine`?        (import sequestrado)
  3. o modulo importado esta' FORA da arvore deste repositorio? (copia no sys.path)
  4. o commit fixado do motor existe no remoto PUBLICO?         (pin que so' resolve nesta maquina)
"""
import ast
import inspect
import json
import pathlib
import re
import urllib.error
import urllib.request

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"

# nomes de arquivo que so' existem no motor; se um deles aparecer aqui, e' copia
ARQUIVOS_DO_MOTOR = {"pheno.py", "leg_engine.py", "trainer.py", "timeseries.py", "raster_source.py"}
# funcoes que sao O motor: definir uma delas aqui e' reimplementar, mesmo com outro nome de arquivo
FUNCOES_DO_MOTOR = {"derive_feat", "decompose", "spatial_cv"}


def test_nenhum_arquivo_do_motor_foi_copiado():
    achados = [str(p.relative_to(RAIZ)) for p in SRC.rglob("*.py") if p.name in ARQUIVOS_DO_MOTOR]
    assert not achados, (
        "arquivo do motor copiado para dentro deste repositorio: " + ", ".join(achados) +
        ". O motor tem que vir do pacote pheno-engine, senao a afirmacao do artigo de que a ferramenta "
        "roda o mesmo codigo dos resultados publicados deixa de ser verdade.")


def test_nenhuma_funcao_do_motor_foi_reimplementada():
    achados = []
    for p in SRC.rglob("*.py"):
        arvore = ast.parse(p.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name in FUNCOES_DO_MOTOR:
                achados.append(f"{p.relative_to(RAIZ)}:{no.lineno} def {no.name}")
    assert not achados, ("funcao do motor redefinida aqui: " + "; ".join(achados) +
                         ". Importe de pheno_engine em vez de reimplementar.")


def test_o_motor_importado_vem_do_pacote_instalado():
    ts = pytest.importorskip("pheno_engine", reason="pheno-engine nao instalado neste ambiente")
    import pheno_engine as pheno
    assert hasattr(pheno, "derive_feat"), "pheno_engine sem derive_feat: pacote errado"
    # ⚠️ o teste que importa: o modulo carregado NAO pode estar dentro desta arvore. Um `pheno.py`
    # solto em src/ seria importado por este mesmo nome e passaria pelos dois testes acima.
    onde = pathlib.Path(inspect.getfile(pheno)).resolve()
    assert RAIZ not in onde.parents, (
        f"pheno_engine foi carregado de DENTRO deste repositorio ({onde}). "
        "O motor tem que vir do pacote instalado.")


def test_o_commit_fixado_do_motor_existe_no_remoto():
    """⚠️ Um pin que so' resolve na maquina do autor e' pior do que nao ter pin.

    `pip install` le' a referencia do pyproject e vai busca-la no GitHub. Se ela nunca foi empurrada,
    a instalacao quebra para todo mundo menos para quem escreveu, e o leitor nao tem como conferir que
    a ferramenta roda o motor dos resultados. Aqui isso foi real: a versao 0.1.0 nasceu fixada em
    bb2e997, que so' existia num branch local, antes de o motor virar pacote proprio.

    ⚠️ O pin pode ser SHA ou TAG, e a checagem tem que servir aos dois. Para SHA a API devolve o
    proprio commit; para tag ela devolve o commit que a tag aponta, que naturalmente NAO comeca pelo
    texto da tag. Comparar por prefixo funcionava so' no primeiro caso, e passou a reprovar um pin
    perfeitamente valido assim que trocamos SHA por tag. O que este teste tem que cobrar e' que a
    referencia RESOLVA no remoto, e nao a forma dela.
    """
    pin = re.search(r"pheno-engine @ git\+(https://github\.com/([^/]+/[^/.]+))\.git@([\w.]+)",
                    (RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert pin, "pyproject.toml sem o pin do pheno-engine: a dependencia do motor e' obrigatoria"
    repo, ref = pin.group(2), pin.group(3)
    try:
        with urllib.request.urlopen(
                f"https://api.github.com/repos/{repo}/commits/{ref}", timeout=15) as r:
            visto = json.load(r)["sha"]
    except urllib.error.HTTPError as e:
        if e.code in (404, 422):
            pytest.fail(f"a referencia fixada {ref} nao existe em {repo}: empurre a tag ou o branch do "
                        f"motor, senao `pip install` so' funciona aqui")
        pytest.skip(f"GitHub respondeu {e.code}; sem rede confiavel para conferir o pin")
    except (urllib.error.URLError, TimeoutError):
        pytest.skip("sem rede: o pin nao foi conferido")
    assert re.fullmatch(r"[0-9a-f]{40}", visto), f"{repo}@{ref} resolveu para algo estranho: {visto}"
    if re.fullmatch(r"[0-9a-f]{7,40}", ref):          # pin por SHA: tem que ser o proprio commit
        assert visto.startswith(ref), f"o remoto resolveu {ref} para {visto}"
