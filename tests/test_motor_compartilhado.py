# -*- coding: utf-8 -*-
"""O ARTIGO AFIRMA QUE ESTE REPOSITORIO NAO TEM MOTOR PROPRIO. Estes testes cobram isso.

A frase publicada e' que o que o usuario arrasta na ferramenta e' o mesmo codigo que produziu os
numeros do artigo. Ela e' verdadeira enquanto o motor fenometrico vier do pacote `ts-annotator`, e
falsa no dia em que alguem copiar `pheno.py` para ca' "para simplificar" ou "para nao depender de
outro repo". O modo de falha e' silencioso: tudo continua rodando, os numeros e' que deixam de ser os
mesmos, e nenhum revisor teria como perceber.

Sao tres perguntas:
  1. existe arquivo de motor DENTRO deste repositorio?          (copia explicita)
  2. o motor que importamos vem mesmo de `ts_annotator`?        (import sequestrado)
  3. o modulo importado esta' FORA da arvore deste repositorio? (copia no sys.path)
"""
import ast
import inspect
import pathlib

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
        ". O motor tem que vir do pacote ts-annotator, senao a afirmacao do artigo de que a ferramenta "
        "roda o mesmo codigo dos resultados publicados deixa de ser verdade.")


def test_nenhuma_funcao_do_motor_foi_reimplementada():
    achados = []
    for p in SRC.rglob("*.py"):
        arvore = ast.parse(p.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name in FUNCOES_DO_MOTOR:
                achados.append(f"{p.relative_to(RAIZ)}:{no.lineno} def {no.name}")
    assert not achados, ("funcao do motor redefinida aqui: " + "; ".join(achados) +
                         ". Importe de ts_annotator em vez de reimplementar.")


def test_o_motor_importado_vem_do_pacote_instalado():
    ts = pytest.importorskip("ts_annotator", reason="ts-annotator nao instalado neste ambiente")
    from ts_annotator.core import pheno
    assert hasattr(pheno, "derive_feat"), "ts_annotator.core.pheno sem derive_feat: pacote errado"
    # ⚠️ o teste que importa: o modulo carregado NAO pode estar dentro desta arvore. Um `pheno.py`
    # solto em src/ seria importado por este mesmo nome e passaria pelos dois testes acima.
    onde = pathlib.Path(inspect.getfile(pheno)).resolve()
    assert RAIZ not in onde.parents, (
        f"ts_annotator.core.pheno foi carregado de DENTRO deste repositorio ({onde}). "
        "O motor tem que vir do pacote instalado.")
