# -*- coding: utf-8 -*-
"""O FLUXO REAL, NUM SUBPROCESSO -- porque um abort do Qt nao vira excecao Python.

Um `qFatal` (ex.: "QThread: Destroyed while thread is still running") derruba o processo inteiro
com 0xC0000409 e nenhum teste dentro do mesmo interprete ve' nada. Rodando o fluxo num
subprocesso, o codigo de saida denuncia. Foi assim que se achou o crash ao fechar o programa
depois de passar meses com as setas (tests/fluxo/estresse.py).

Precisa dos dados reais (cycle-navigator.toml apontando para o recorte); sem eles, e' pulado.
"""
import os
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CONFIG = os.environ.get("CN_CONFIG") or str(RAIZ / "cycle-navigator.toml")


def _tem_dados():
    if not pathlib.Path(CONFIG).exists():
        return False
    try:
        from cycle_navigator.config import carrega
        carrega(CONFIG)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _tem_dados(), reason="sem cycle-navigator.toml com dados reais")
@pytest.mark.parametrize("roteiro", ["fluxo", "estresse"])
def test_fluxo_real_nao_aborta(roteiro):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", CN_CONFIG=CONFIG)
    r = subprocess.run([sys.executable, str(RAIZ / "tests" / "fluxo" / f"{roteiro}.py")],
                       capture_output=True, text=True, timeout=900, env=env)
    assert r.returncode == 0, (f"subprocesso saiu com {r.returncode} "
                               f"({'ABORT do Qt' if r.returncode in (-1073740791, 3221226505) else 'erro'})\n"
                               f"--- stdout ---\n{r.stdout[-2000:]}\n--- stderr ---\n{r.stderr[-2000:]}")
    assert "pronto." in r.stdout
