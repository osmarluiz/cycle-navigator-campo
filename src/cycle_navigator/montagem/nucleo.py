# -*- coding: utf-8 -*-
"""MONTAGEM · nucleo: a janela, o mapa, os paineis e os recados: o que todas as outras pecas usam.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
from PyQt6.QtWidgets import QToolButton
from collections import Counter
from ts_annotator.ui.tiled_map_view import TiledMapView
import pyqtgraph as pg
from .. import estilo
from ..analise import JanelaAnalise
from ..ciclos import PainelCiclo
from ..fazendas import CadastroFazendas
from ..janela import JanelaCampo
from ..pontos import PainelPontos
from ..tabelas import JanelaTabelas
from .fontes import CAMADAS_ANO, CAMADAS_MES, monta, serie

log = logging.getLogger(__name__)


def instala(ctx):
    cfg = ctx.cfg

    classe, bases, ndvi, cinz, pivos, cult, lut = monta(cfg)

    safras = list(cfg.safras)
    safra = safras[-1]
    log.info("safras disponiveis: %s", ", ".join(safras))

    view = TiledMapView(ndvi, cinz)
    view.vb.setLimits(xMin=-ndvi.width, xMax=2 * ndvi.width,
                      yMin=-ndvi.height, yMax=2 * ndvi.height)

    # A serie INTEIRA: a curva precisa poder mostrar todos os meses que existem. Sao 54 leituras de
    # UM pixel por clique -- barato. A safra so' define a janela que abre ampliada e o arquivo.
    ts_todo = serie(cfg, cfg.meses, classe.transform)

    cadastro = CadastroFazendas(cfg.pasta_pontos / "fazendas.json", classe.transform, classe.crs)
    tabs = JanelaTabelas()
    analise = JanelaAnalise(cfg.classes)

    def refresca_analise():
        if not analise.isHidden():
            analise.atualiza(p_pontos.store, ctx.estado["safra"], cfg.meses_de(ctx.estado["safra"]))
    p_pontos = PainelPontos(cfg.classes, safras,
                            arquivo_levantador=cfg.pasta_pontos / "_levantador.txt")
    p_pontos.hide()        # vira so' o deposito dos pontos; a interface dele foi para a barra

    def culturas_usadas():
        vistas = set(cfg.classes)
        if p_pontos.store is not None:
            for pt in p_pontos.store.points:
                for sg in (pt.get("ciclos") or []):
                    if sg.get("cultura"):
                        vistas.add(sg["cultura"])
        return vistas

    def mais_usadas():
        """As culturas mais gravadas nesta safra, para virarem os botoes de um clique."""
        n = Counter()
        if p_pontos.store is not None:
            for pt in p_pontos.store.points:
                for sg in (pt.get("ciclos") or []):
                    if sg.get("cultura"):
                        n[sg["cultura"]] += 1
        return [c for c, _ in n.most_common()]

    p_ciclo = PainelCiclo(culturas_usadas, cores=cfg.classes, mais_usadas=mais_usadas)
    win = JanelaCampo(view, safras, CAMADAS_MES, p_ciclo,
                      camadas_ano=[c for c in CAMADAS_ANO if c in bases])
    win.resize(1400, 880)

    def enquadra_largura():
        """⚠️ AO ABRIR, A IMAGEM ENCHE A LARGURA DA JANELA. O recorte e' quase quadrado e a janela
        e' larga: enquadrado inteiro ("caber tudo") ele ocupava 40% do meio, com duas faixas pretas
        dos lados. Aqui sobra imagem em cima e embaixo (arrasta-se), e o botao de enquadrar tudo
        continua no canto para quem quiser ver o recorte inteiro."""
        if view.vb.width() < 50 or view.vb.height() < 50:
            return
        alt = classe.width * view.vb.height() / view.vb.width()
        meio = classe.height / 2
        view.vb.setRange(xRange=(0, classe.width), yRange=(meio - alt / 2, meio + alt / 2),
                         padding=0)
    # os botoes de zoom vem do ts-annotator com cores proprias (azul): aqui entram na paleta
    for b in view.zoom_ctrl.findChildren(QToolButton):
        b.setStyleSheet(f"QToolButton{{background:{estilo.FLUTUA}; color:{estilo.TEXT};"
                        f"border:1px solid {estilo.BORDER_STRONG}; border-radius:8px; font-size:18px;"
                        f"min-height:0; padding:0;}}"
                        f"QToolButton:hover{{background:{estilo.HOVER};}}")

    def status(txt):
        """Recado de contexto, na pilula do canto do mapa (a contagem la' em cima nao e' lugar)."""
        win.barra.dica.setText(txt)
        win._posiciona()

    def conta():
        n = len(p_pontos.store) if p_pontos.store is not None else 0
        win.barra.info.setText("nenhum ponto" if n == 0 else
                               "1 ponto" if n == 1 else f"{n} pontos")

    # ⚠️ O ALFINETE: onde foi o clique. Sem ele, a curva la' embaixo nao dizia DE ONDE era -- o
    # titulo mostrava linha e coluna do pixel, que ninguem sabe achar no mapa.
    alfinete = pg.ScatterPlotItem(pxMode=True)
    alfinete.setZValue(30)
    view.vb.addItem(alfinete)

    def poe_alfinete(row, col):
        pos = (col + 0.5, row + 0.5)
        alfinete.setData([
            {"pos": pos, "size": 24, "pen": pg.mkPen("#000000", width=5), "brush": None},
            {"pos": pos, "size": 24, "pen": pg.mkPen("#ffffff", width=2.5), "brush": None},
            {"pos": pos, "size": 7, "pen": pg.mkPen("#000000", width=1), "brush": pg.mkBrush("#ffffff")}])

    aqui = pg.ScatterPlotItem(pxMode=True)          # o ponto azul do "onde estou"
    aqui.setZValue(29)
    view.vb.addItem(aqui)

    # o que esta peca deixa para as outras
    ctx.alfinete = alfinete
    ctx.analise = analise
    ctx.aqui = aqui
    ctx.b = b
    ctx.bases = bases
    ctx.cadastro = cadastro
    ctx.cinz = cinz
    ctx.classe = classe
    ctx.conta = conta
    ctx.cult = cult
    ctx.culturas_usadas = culturas_usadas
    ctx.enquadra_largura = enquadra_largura
    ctx.lut = lut
    ctx.mais_usadas = mais_usadas
    ctx.ndvi = ndvi
    ctx.p_ciclo = p_ciclo
    ctx.p_pontos = p_pontos
    ctx.pivos = pivos
    ctx.poe_alfinete = poe_alfinete
    ctx.refresca_analise = refresca_analise
    ctx.safra = safra
    ctx.safras = safras
    ctx.status = status
    ctx.tabs = tabs
    ctx.ts_todo = ts_todo
    ctx.view = view
    ctx.win = win
