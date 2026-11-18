# -*- coding: utf-8 -*-
"""O NAVEGADOR: le' o continuo de sistemas de cultivo em vez de consultar uma legenda.

O motor fenometrico e a interface vem do pacote `pheno-engine`, declarado como dependencia. Este
pacote e' a APLICACAO: configuracao, montagem e ponto de entrada. Ele nao reimplementa nada do motor,
e ha' um teste que falha se alguem tentar (`tests/test_motor_compartilhado.py`).

Uso:  cycle-navigator [--config caminho.toml]
"""
import argparse
import logging
import sys

import warnings
from collections import Counter

import numpy as np
import pyqtgraph as pg
import rasterio
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QCompleter, QDialog, QFileDialog, QMessageBox,
                             QToolButton)

# ⚠️ TUDO que se importa daqui existe no ts-annotator PUBLICO. A versao anterior usava
# `ui.continuum_window` e `ui.phenology_panel`, que so' existem num clone local nao publicado --
# e por isso `pip install` produzia um pacote que nao abria em outra maquina. Como o levantamento
# vai a campo em OUTROS computadores, isso deixou de ser detalhe. Nao reintroduza esses imports.
from ts_annotator.core.raster_source import RasterSource
from ts_annotator.core.timeseries import TimeSeriesSource
from ts_annotator.render import (CLASS_COLORS, make_bands_rgb_colorizer, make_class_colorizer,
                                 make_rgb_colorizer)
from ts_annotator.ui.tiled_map_view import TiledMapView

from .ciclos import PainelCiclo
from .config import ConfiguracaoAusente, carrega
from . import estilo
from . import exporta
from .analise import JanelaAnalise
from .busca import Indice
from .posicao import OndeEstou
from .recorte import RecorteVivo
from .sugestoes import Caixa
from .janela_sugestoes import JanelaSugestoes
from .car import (COR_SAM, CamadaCAR, dados_do_car, dados_do_sam, html_sam,
                  resumo as resumo_car)
from .fazendas import CadastroFazendas, CamadaFazendas, DesenhoPoligono, DialogoFazenda
from .janela import DESENHAR, EDITAR, IDENTIFICAR, JanelaCampo
from .pontos import CamadaPontos, PainelPontos, abre_store
from .tabelas import JanelaTabelas

log = logging.getLogger(__name__)

# as constantes e a leitura dos rasters moram em montagem/fontes.py; ficam visiveis aqui para
# quem importava de `cycle_navigator.app`
from .montagem.fontes import CAMADAS_ANO, CAMADAS_MES, RGB_FC, RGB_NAT, _tabela_de_ciclos, _tem_dado, cinza, cor_ndvi, monta, serie  # noqa: F401,E402
from . import montagem  # noqa: E402


def monta_app(cfg, app):
    """Monta a janela inteira e devolve o contexto (janela, camadas, handlers).

    ⚠️ Separado de main() para o FLUXO REAL ser testavel: clicar, ligar camadas, adotar, trocar de
    modo. Um crash nativo do Qt (abort em C++) nao vira excecao Python -- so' aparece rodando o
    fluxo de verdade, e com isto da' para rodar num subprocesso e ler o codigo de saida.
    """
    import types
    ctx = types.SimpleNamespace(cfg=cfg, app=app)
    # ⚠️ A ORDEM IMPORTA: cada peca usa o que as anteriores deixaram em `ctx` (ver montagem/__init__.py)
    for peca in montagem.ORDEM:
        peca.instala(ctx)
    return ctx


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="cycle-navigator", description=__doc__.splitlines()[0])
    ap.add_argument("--config", help="caminho do .toml; se omitido, procura os lugares de sempre")
    ap.add_argument("--autoteste", action="store_true",
                    help="abre, recorta um talhao, monta a analise, fecha; o codigo de saida diz "
                         "se o PACOTE esta' inteiro (e' assim que se confere um executavel novo)")
    args = ap.parse_args(argv)
    try:
        cfg = carrega(args.config)
    except ConfiguracaoAusente as e:                # erro de uso, nao defeito: sem stack trace
        print(f"\n{e}\n", file=sys.stderr)
        return 2
    log.info("configuration: %s", cfg.origem)

    app = QApplication(sys.argv[:1])
    estilo.aplica(app)
    _tela_acordada()
    ctx = monta_app(cfg, app)
    ctx.win.showMaximized()
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(2500, ctx.aviso_de_resposta)
    QTimer.singleShot(250, ctx.enquadra_largura)      # so' depois de a janela ter o tamanho final
    if args.autoteste:
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: app.exit(_autoteste(ctx)))
    return app.exec()


def _tela_acordada():
    """⚠️ No Mac a tela apaga em 2 minutos na bateria -- no meio da conversa com o produtor. Enquanto
    o programa estiver aberto o `caffeinate` do proprio macOS segura a tela (e o sono); ele sai
    sozinho quando este processo termina (-w). Fora do Mac, ou sem o comando: nada acontece."""
    if sys.platform != "darwin":
        return
    try:
        import os
        import subprocess
        subprocess.Popen(["/usr/bin/caffeinate", "-d", "-i", "-w", str(os.getpid())],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        log.info("tela acordada indisponivel (%s)", e)


def _autoteste(ctx):
    """⚠️ O que so' quebra DEPOIS de empacotar: pyproj (CRS), o modelo do recorte (hydra le^ .yaml de
    dentro do pacote), os icones. Nada e' gravado: so' leitura. 0 = inteiro; 1 = algo faltou."""
    falhas = []
    try:
        import pyproj
        log.info("autoteste: pyproj %s", pyproj.__version__)
    except Exception as e:
        falhas.append(f"pyproj: {e}")
    try:
        if ctx.cam_sam is not None:
            p = ctx.cam_sam.polys[ctx.cam_sam.n // 2].representative_point()
            row, col = int(p.y), int(p.x)
        else:
            row, col = ctx.view.height() // 2, ctx.view.width() // 2
        ctx.ao_clicar(row, col)
        log.info("autoteste: clique abriu %s", ctx.p_ciclo.rc)
        if ctx.recorte.ok:
            rec = ctx.pede_recorte([(row, col, 1)])
            if rec is None:
                falhas.append("recorte: o modelo nao devolveu contorno")
            else:
                log.info("autoteste: recorte de %d vertices, nota %.2f",
                         len(rec["poli"].exterior.coords), rec["nota"])
        else:
            log.info("autoteste: recorte desligado (%s)", ctx.recorte.motivo)
        ctx.abre_analise()
        log.info("autoteste: analise com %d talhao(oes)", len(ctx.analise._pts))
        ctx.abre_sugestoes()                     # so' abre a janela: nada e' enviado
        ctx.j_sug.close()
        log.info("autoteste: sugestoes com %d na fila", len(ctx.caixa.lista()))
    except Exception as e:
        log.exception("autoteste")
        falhas.append(f"{type(e).__name__}: {e}")
    for f in falhas:
        log.error("autoteste FALHOU: %s", f)
    log.info("autoteste: %s", "FALHOU" if falhas else "inteiro")
    ctx.win.close()
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
