# -*- coding: utf-8 -*-
"""ARQUIVO DANIFICADO NAO SE APAGA NEM SE SOBRESCREVE: poe-se de lado, com outro nome.

Os pontos e o cadastro sao o trabalho de campo. Se um deles nao abre (disco cheio, HD arrancado no
meio da gravacao), "abrir vazio e seguir" faria o proximo Gravar escrever por cima do que ainda da'
para recuperar. Aqui o arquivo e' renomeado para `<nome>.danificado-AAAAMMDD-HHMMSS` e quem chamou
avisa na tela.
"""
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def guarda_danificado(caminho):
    """Renomeia (nunca apaga) e devolve o novo caminho."""
    caminho = Path(caminho)
    lado = caminho.with_name(caminho.name + ".danificado-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.replace(caminho, lado)
    return lado


def poe_de_lado(caminho):
    """`guarda_danificado` que nao levanta: devolve o novo caminho, ou None se nem renomear deu."""
    try:
        return guarda_danificado(caminho)
    except OSError as e:
        log.error("nao consegui por %s de lado: %s", caminho, e)
        return None
