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

import numpy as np
import rasterio
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

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
from .car import CamadaCAR, dados_do_car, resumo as resumo_car
from .fazendas import CadastroFazendas, CamadaFazendas, DesenhoPoligono, DialogoFazenda
from .janela import DESENHAR, EDITAR, IDENTIFICAR, JanelaCampo
from .pontos import CamadaPontos, PainelPontos, abre_store
from .tabelas import JanelaTabelas

log = logging.getLogger(__name__)


def cinza(nodata=0, escurece=0.55):
    """RGB medio -> cinza escurecido: base neutra para o eixo colorido saltar."""
    def fn(arr):
        g = arr[:3].astype(np.float32).mean(0)
        gv = np.clip(g * escurece, 0, 255).astype(np.uint8)
        rgba = np.dstack([gv, gv, gv, np.full(gv.shape, 255, np.uint8)])
        rgba[(arr[:3].sum(0) == nodata * 3), 3] = 0
        return rgba
    return fn


def _tabela_de_ciclos(pred_tif):
    """idx da predicao -> numero de ciclos, lido do sidecar .json do proprio raster.

    ⚠️ le' os rotulos do arquivo em vez de assumir a ordem das classes. A ordem muda entre modelos, e
    uma tabela escrita a mao aponta para a classe errada sem avisar.
    """
    import json
    import re
    labs = json.load(open(str(pred_tif).replace(".tif", ".json"), encoding="utf-8"))["labs"]
    lut = np.zeros(256, np.float32)
    for i, l in enumerate(labs):
        if l.startswith("Cultivo") and "perene" not in l.lower():
            m = re.search(r"(\d)", l)
            if m:
                lut[i] = int(m.group(1))
    return lut


def serie(cfg, safra_ou_meses, T):
    """A serie temporal de um ano-safra (nome) ou de uma lista de meses, na grade da base.

    ⚠️ Carregar a serie inteira aqui e' seguro -- o que NAO pode e' entregar 54 meses de uma vez ao
    motor fenometrico, que pressupoe doze meses a partir de outubro (`derive_feat` tem os meses da
    seca fixos nos indices 8..12). Quem cuida disso e' `ciclos.deteccao`, que fatia por ano-safra
    antes de chamar o motor. Entregar a serie toda nao daria erro -- daria numero, e errado.
    """
    meses = (cfg.meses_de(safra_ou_meses) if isinstance(safra_ou_meses, str)
             else list(safra_ou_meses))
    arquivos = [str(cfg.aoi / "cube" / f"ride_{m}_aoi.tif") for m in meses]
    # cada mes pode estar deslocado em relacao a' base; o deslocamento sai do proprio geotransform
    offs = [round((rasterio.open(f).transform.f - T.f) / T.a) for f in arquivos]
    ts = TimeSeriesSource(arquivos, bands=(1, 2, 3, 4), row_offsets=offs, nodata=65535, scale=10000)
    if not ts.has_overviews:
        log.warning("⚠️ %d mes(es) sem overviews: a navegacao vai ler em resolucao cheia e travar "
                    "em area grande. Gere com: gdaladdo -r average <mes>.tif 2 4 8 16 32",
                    len(arquivos))
    return ts


# Esticamento FIXO do RGB dos meses (bandas do cubo: 1=B 2=G 3=R 4=NIR -> indices 0..3).
# ⚠️ FIXO, nao por-viewport: o ponto de ver mes a mes e' COMPARAR os meses entre si. Um esticamento
# recalculado a cada vista deixa todo mes com a mesma cara e some com a diferenca que se queria ver.
# Os valores do RGB natural vem do projeto ride_review, ajustados nesta cena.
RGB_NAT = {"idx": [2, 1, 0], "lo": [260, 375, 171], "hi": [1879, 1247, 795]}
RGB_FC = {"idx": [3, 2, 1], "lo": [900, 260, 375], "hi": [4200, 1879, 1247]}

# As camadas que dependem da DATA, e as que resumem o ano inteiro.
CAMADAS_MES = ["RGB natural", "Falsa-cor (infravermelho)", "NDVI do mês"]
CAMADAS_ANO = ["NDVI-temporal (ano)", "Fenologia (ano)", "MNF (ano)",
               "RGB da chuva (jan)", "RGB da seca (ago)", "Classificação"]


def cor_ndvi(nodata=65535):
    """NDVI de um mes cru -> rampa de cor. ⚠️ So' visualizacao: a fenometria vem do pheno_engine."""
    import pyqtgraph as pg
    lut = pg.colormap.get("RdYlGn", source="matplotlib").getLookupTable(0.0, 1.0, 256)

    def fn(arr):
        a = arr.astype(np.float32)
        red, nir = a[2], a[3]
        mau = (~np.isfinite(red)) | (~np.isfinite(nir)) | (red == nodata) | (nir == nodata)
        nd = (nir - red) / (nir + red + 1e-6)
        i = np.clip(((np.nan_to_num(nd) + 0.2) / 1.2 * 255), 0, 255).astype(np.uint8)
        rgba = np.dstack([lut[i], np.full(i.shape, 255, np.uint8)])
        rgba[mau, 3] = 0
        return rgba
    return fn


def monta(cfg):

    """Abre as fontes e devolve o que a janela precisa."""
    bm = cfg.basemaps
    classe = RasterSource(str(bm["classe"]))

    rgb, cinz = make_rgb_colorizer(nodata=0), cinza(nodata=0)
    ndvi = RasterSource(str(bm["ndvi"]))
    # ⚠️⚠️ OS ROTULOS TEM DE SER EXATAMENTE OS QUE O COMBO MOSTRA. O `_set_base` do ContinuumWindow
    # faz `if label in self.basemaps:` e NAO RECLAMA quando nao acha -- so' nao troca o mapa. Este
    # arquivo chamava as chaves de "Image · NDVI-temporal" (ingles) enquanto o painel listava
    # "Imagem · NDVI-temporal" (portugues): o seletor funcionava na aparencia e nao fazia nada.
    # Por isso o combo e' RE-POPULADO a partir deste dicionario (ver `aplica_bases`), em vez de
    # confiar que duas listas escritas em lugares diferentes continuem iguais.
    bases = {"Imagem · NDVI-temporal": (ndvi, rgb),
             "Imagem · Fenologia": (RasterSource(str(bm["pheno"])), rgb),
             "Imagem · MNF": (RasterSource(str(bm["mnf"])), rgb),
             "Imagem · Cinza (fundo neutro)": (ndvi, cinz)}
    for chave, rotulo in (("rgb_chuvoso", "RGB natural · chuva (jan)"),
                          ("rgb_seco", "RGB natural · seca (ago)")):
        p = cfg.basemaps_extra[chave]
        if p.exists():
            bases[rotulo] = (RasterSource(str(p)), rgb)
        else:
            log.info("visualizacao opcional ausente (segue sem ela): %s", p.name)
    bases["Classificação"] = (classe, make_class_colorizer(CLASS_COLORS, 255))

    pivos = []
    if cfg.pivos:
        try:
            import geopandas as gpd
            pivos = list(gpd.read_file(str(cfg.pivos)).geometry)
            log.info("pivot register: %d polygons", len(pivos))
        except Exception as e:                      # opcional: a ferramenta abre sem isso
            log.warning("pivot register unavailable (%s): %s", type(e).__name__, e)

    cult, lut = None, None
    if cfg.predicao:
        try:
            cult = RasterSource(str(cfg.predicao))
            lut = _tabela_de_ciclos(cfg.predicao)
        except Exception as e:
            log.warning("cropland prediction unavailable (%s): %s; "
                        "falling back to the phenological detector", type(e).__name__, e)
            cult, lut = None, None
    return classe, bases, ndvi, cinz, pivos, cult, lut


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="cycle-navigator", description=__doc__.splitlines()[0])
    ap.add_argument("--config", help="caminho do .toml; se omitido, procura os lugares de sempre")
    args = ap.parse_args(argv)
    try:
        cfg = carrega(args.config)
    except ConfiguracaoAusente as e:                # erro de uso, nao defeito: sem stack trace
        print(f"\n{e}\n", file=sys.stderr)
        return 2
    log.info("configuration: %s", cfg.origem)

    app = QApplication(sys.argv[:1])
    estilo.aplica(app)
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

    p_ciclo = PainelCiclo(culturas_usadas)
    win = JanelaCampo(view, safras, CAMADAS_MES + CAMADAS_ANO, p_ciclo)
    win.resize(1600, 980)
    win.barra.ed_levantador.setText(p_pontos.levantador)
    win.barra.ed_levantador.editingFinished.connect(
        lambda: (p_pontos.ed_levantador.setText(win.barra.ed_levantador.text()),
                 p_pontos._salva_levantador()))

    cam_pontos = CamadaPontos(view, cfg.classes)
    cam_faz = CamadaFazendas(view)
    cam_faz.usar(cadastro)
    cam_car = CamadaCAR(view, cfg.car, classe.transform, classe.crs) if cfg.car else None
    if cam_car is not None and cam_car.ok:
        win.barra.bt_car.show()
        # ⚠️ visivel em QUALQUER modo enquanto o botao estiver ligado. A versao anterior so' mostrava
        # no modo Desenhar: quem abria o programa nao via o CAR e nao tinha como clicar em cima.
        win.barra.carToggled.connect(cam_car.visivel)
        view.vb.sigRangeChanged.connect(cam_car.redesenha)
        view.vb.sigRangeChanged.connect(lambda *_: aviso_car())
        log.info("CAR: %d imoveis como referencia", cam_car.n)
    else:
        cam_car = None
    tabs.fazendas.lista(cadastro)
    estado = {"safra": safra, "modo": IDENTIFICAR, "mes": None, "camada": CAMADAS_MES[0],
              "car_semente": ""}
    _fontes = {}

    # ---------------- camadas ----------------
    def fonte_mes(m):
        if m not in _fontes:
            _fontes[m] = RasterSource(str(cfg.aoi / "cube" / f"ride_{m}_aoi.tif"))
        return _fontes[m]

    def pinta_mapa():
        cam, m = estado["camada"], estado["mes"]
        if cam in CAMADAS_MES and m:
            src = fonte_mes(m)
            if cam == "RGB natural":
                col = make_bands_rgb_colorizer(RGB_NAT["idx"], RGB_NAT["lo"], RGB_NAT["hi"], 65535)
            elif cam == "Falsa-cor (infravermelho)":
                col = make_bands_rgb_colorizer(RGB_FC["idx"], RGB_FC["lo"], RGB_FC["hi"], 65535)
            else:
                col = cor_ndvi()
            view.set_source(src, col)
        else:
            par = bases.get(cam)
            if par is not None:
                view.set_source(*par)

    def usa_camada(nome):
        estado["camada"] = nome
        win.barra.data_ativa(nome in CAMADAS_MES)
        pinta_mapa()

    def usa_data(m):
        estado["mes"] = int(m)
        if estado["camada"] in CAMADAS_MES:
            pinta_mapa()

    def usa_safra(s):
        estado["safra"] = s
        store = abre_store(cfg, s, classe.transform, classe.crs)
        p_pontos.usar(store)
        cam_pontos.usar(store)
        meses = cfg.meses_de(s)
        estado["mes"] = meses[0] if estado["mes"] not in meses else estado["mes"]
        win.barra.lista_datas(meses, atual=estado["mes"])
        pinta_mapa()
        tabs.pontos.lista(store)
        win.barra.info.setText(f"{len(store)} talhao(oes)")
        log.info("safra %s: %d talhao(oes)", s, len(store))

    # ---------------- modos ----------------
    desenho = DesenhoPoligono(view, None)

    def usa_modo(m, fid=None, semente=None):
        """`semente` = (pontos, cod_car): abre o modo Desenhar ja' com esse contorno editavel."""
        if estado["modo"] == DESENHAR and m != DESENHAR:
            desenho.cancela(); cam_faz.oculto = None; cam_faz.redesenha()
        estado["modo"] = m
        estado["car_semente"] = semente[1] if semente else None
        win.barra.mostra_modo(m)
        if cam_car is not None:
            aviso_car()
        tabs.fazendas.setEnabled(m != DESENHAR)
        if m == DESENHAR:
            cam_faz.oculto = fid
            cam_faz.redesenha()
            if semente:
                desenho.comeca(None, semente[0])
            else:
                desenho.comeca(fid, (cadastro.por_id(fid) or {}).get("poligono") if fid else None)
        view.setCursor(Qt.CursorShape.CrossCursor if m == DESENHAR
                       else Qt.CursorShape.ArrowCursor)

    def confirma():
        """Enter / duplo-clique: fecha o contorno e abre o cadastro."""
        if estado["modo"] != DESENHAR:
            return
        pts = desenho.pontos()
        if len(pts) < 3:
            return
        fid = desenho.editando
        extra = dados_do_car(estado.get("car_semente"))
        desenho.cancela()
        cam_faz.oculto = None
        f = cadastro.salva(fid, pts, extra or None)
        dlg = DialogoFazenda(f, win)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dados = dlg.dados()
            dados.update(extra)          # os dados do CAR nao se editam no formulario
            f = cadastro.salva(f["id"], None, dados)
        cam_faz.redesenha()
        tabs.fazendas.lista(cadastro, selecionar=f["id"])
        log.info("fazenda #%d: %s (%.1f ha)", f["id"], f.get("nome") or "-", f.get("area_ha") or 0)
        usa_modo(IDENTIFICAR)

    def cancela():
        if cam_car is not None:
            cam_car.limpa_selecao()
        if estado["modo"] in (DESENHAR, EDITAR):
            usa_modo(IDENTIFICAR)

    def no_clique(ev):
        """⚠️ Roda ANTES do pixelClicked: no modo desenho o clique poe vertice, nao abre talhao."""
        if estado["modo"] == DESENHAR and desenho.ativo:
            # ⚠️ CAR como PONTO DE PARTIDA: sem vertice ainda, um clique dentro de um imovel carrega
            # o contorno dele ja' editavel. A pessoa ajusta ou so' da' Enter e nomeia.
            if (not desenho.pts and cam_car is not None and win.barra.bt_car.isChecked()
                    and ev.button() == Qt.MouseButton.LeftButton and not ev.double()):
                p = view.vb.mapSceneToView(ev.scenePos())
                a, anel = cam_car.em(int(p.y()), int(p.x()))
                if a is not None:
                    cs, rs = anel
                    pts = [(float(c), float(r)) for c, r in zip(cs, rs)]
                    if len(pts) > 2 and pts[0] == pts[-1]:
                        pts = pts[:-1]
                    desenho.comeca(None, pts)
                    estado["car_semente"] = dict(a)
                    win.barra.info.setText(f"contorno do CAR carregado ({resumo_car(a)}) — "
                                           "ajuste os vértices ou dê Enter")
                    return
            if desenho.clique(ev) and not desenho.ativo:
                confirma()                      # duplo-clique fechou
            return
        if estado["modo"] == EDITAR and ev.double():
            p = view.vb.mapSceneToView(ev.scenePos())
            f = cadastro.em(int(p.y()), int(p.x()))
            if f:
                dlg = DialogoFazenda(f, win)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    cadastro.salva(f["id"], None, dlg.dados())
                    cam_faz.redesenha()
                    tabs.fazendas.lista(cadastro, selecionar=f["id"])

    view.glw.scene().sigMouseClicked.connect(no_clique)

    # ---------------- clique no mapa ----------------
    def ao_clicar(row, col):
        if estado["modo"] == DESENHAR:
            return
        if estado["modo"] == EDITAR:
            f = cadastro.em(row, col)
            if f:
                tabs.fazendas.lista(cadastro, selecionar=f["id"])
                usa_modo(DESENHAR, f["id"])      # vertices editaveis
                return
            # ⚠️ clicar num imovel do CAR que ainda nao e' fazenda SELECIONA e abre para editar:
            # o contorno vira poligono editavel na hora, Enter abre o cadastro.
            if cam_car is not None and win.barra.bt_car.isChecked():
                a, anel = cam_car.em(row, col)
                if a is not None:
                    cs, rs = anel
                    pts = [(float(c), float(r)) for c, r in zip(cs, rs)]
                    if len(pts) > 2 and pts[0] == pts[-1]:
                        pts = pts[:-1]
                    usa_modo(DESENHAR, None, semente=(pts, dict(a)))
                    win.barra.info.setText(f"imóvel do CAR selecionado ({resumo_car(a)}) — "
                                           "ajuste os vértices ou dê Enter para cadastrar")
            return
        try:
            curva = ts_todo.read_curve(row, col)
        except Exception as e:
            log.warning("curva indisponivel em (%d,%d): %s", row, col, e)
            return
        if not np.isfinite(curva).any():
            log.info("pixel (%d,%d) sem dado em nenhum mes", row, col)
            return
        faixas, produtor = p_pontos.existente(row, col)
        faz = cadastro.em(row, col)
        # ⚠️ com o CAR ligado, o clique tambem SELECIONA o imovel sob o pixel: contorno destacado e
        # cartao com os dados. Nao muda de modo nem adota -- so' mostra.
        if cam_car is not None and cam_car._visivel:
            i = cam_car.em_idx(row, col)
            if i is not None:
                cam_car.seleciona(i)
                win.barra.info.setText(f"CAR: {resumo_car(cam_car.attr[i])}")
            else:
                cam_car.limpa_selecao()
                win.barra.info.setText(f"{len(p_pontos.store)} talhao(oes)")
        if faz is not None and not produtor:
            produtor = faz.get("proprietario") or faz.get("nome") or ""
        p_ciclo.mostra(row, col, curva, cfg.meses, janela=cfg.meses_de(estado["safra"]),
                       ja_gravado=faixas, produtor=produtor)

    def ao_gravar(segmentos):
        if p_ciclo.rc is None:
            return
        row, col = p_ciclo.rc
        if not p_pontos.levantador:
            QMessageBox.information(win, "Quem esta levantando?",
                                    "Preencha o seu nome na barra de cima antes de gravar.")
            return
        faz = cadastro.em(row, col)
        # ⚠️ grava a curva DA SAFRA (12 x 4), nao a serie inteira (54 x 4). O rotulo e' sobre
        # esta safra; a serie toda custaria 4,5x o tamanho por ponto para nao dizer nada a mais.
        idx = [cfg.meses.index(m) for m in cfg.meses_de(estado["safra"])]
        pt, atualizou = p_pontos.registra(row, col, p_ciclo.curva[idx], segmentos,
                                          p_ciclo.produtor, fazenda=faz)
        log.info("%s talhao #%d: %s", "atualizado" if atualizou else "gravado",
                 pt["id"], pt["class"])
        cam_pontos.redesenha()
        tabs.pontos.lista(p_pontos.store)
        win.barra.info.setText(f"{len(p_pontos.store)} talhao(oes)")

    # ---------------- CAR ----------------
    def aviso_car():
        """Diz na barra por que os perimetros nao aparecem, quando nao aparecem."""
        # no modo Identificar a barra e' do talhao clicado; nos outros, da camada
        if cam_car is None or estado["modo"] == IDENTIFICAR or not win.barra.bt_car.isChecked():
            return
        n = f"{cam_car.em_vista:,}".replace(",", ".")
        if cam_car.escondida:
            win.barra.info.setText(f"CAR: {n} imóveis — aproxime")
        elif cam_car.em_vista == 0:
            win.barra.info.setText("CAR: nenhum imóvel na vista")
        else:
            win.barra.info.setText(f"CAR: {n} imóveis" + (" · simplificado" if cam_car.simplificada
                                                           else ""))

    # ---------------- tabela ----------------
    def centra(col, row, meia=600):
        """Enquadra o mapa num ponto (col/row em pixel) com uma margem."""
        view.vb.setRange(xRange=(col - meia, col + meia), yRange=(row - meia, row + meia),
                         padding=0)

    def vai_ao_ponto(row, col):
        """Da linha da tabela ao mapa E a' curva: e' assim que se confere um rotulo."""
        usa_modo(IDENTIFICAR)
        centra(col, row)
        ao_clicar(row, col)
        win.raise_(); win.activateWindow()

    def centra_fazenda(fid):
        f = cadastro.por_id(fid)
        poli = (f or {}).get("poligono") or []
        if not poli:
            return
        xs = [q[0] for q in poli]; ys = [q[1] for q in poli]
        meia = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.7 + 50
        centra((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, meia)
        win.raise_(); win.activateWindow()

    def exclui_ponto(row, col):
        if p_pontos.store is None:
            return
        if QMessageBox.question(tabs, "Excluir", "Excluir este ponto rotulado?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        p_pontos.store.remove_at(row, col)
        p_pontos.atualiza_info()
        cam_pontos.redesenha()
        tabs.pontos.lista(p_pontos.store)
        win.barra.info.setText(f"{len(p_pontos.store)} talhao(oes)")

    def exporta_camada(qual):
        sug = str(cfg.pasta_pontos / (f"{qual}.gpkg" if qual == "fazendas"
                                      else f"pontos_{estado['safra'].replace('/', '_')}.gpkg"))
        dest, _ = QFileDialog.getSaveFileName(
            tabs, f"Exportar {qual}", sug,
            "GeoPackage (*.gpkg);;Shapefile (*.shp);;CSV (*.csv)")
        if not dest:
            return
        try:
            if dest.lower().endswith(".csv"):
                if qual != "pontos":
                    raise RuntimeError("CSV so' para os pontos; fazendas tem geometria")
                p_pontos.exporta_para(dest)
                n = sum(len(x.get("ciclos") or []) for x in p_pontos.store.points)
            elif qual == "fazendas":
                n, dest = exporta.fazendas(cadastro, dest)
            else:
                n, dest = exporta.pontos(p_pontos.store, dest)
        except Exception as e:
            QMessageBox.warning(tabs, "Exportar", str(e))
            return
        QMessageBox.information(tabs, "Exportar", f"{n} feição(ões) em\n{dest}")

    def preenche(fid):
        f = cadastro.por_id(fid)
        if f is None:
            return
        dlg = DialogoFazenda(f, win)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cadastro.salva(fid, None, dlg.dados())
            cam_faz.redesenha()
            tabs.fazendas.lista(cadastro, selecionar=fid)

    def exclui(fid):
        if fid is None:
            return
        f = cadastro.por_id(fid)
        if QMessageBox.question(tabs, "Excluir",
                                f"Excluir a fazenda '{(f or {}).get('nome') or fid}'?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        cadastro.remove(fid)
        cam_faz.redesenha()
        tabs.fazendas.lista(cadastro)

    win.barra.safraMudou.connect(usa_safra)
    win.barra.camadaMudou.connect(usa_camada)
    win.barra.dataMudou.connect(usa_data)
    win.barra.modoMudou.connect(usa_modo)
    win.barra.abrirTabela.connect(lambda: tabs.mostra())
    win.barra.exportar.connect(lambda: exporta_camada('pontos'))
    win.confirmou.connect(confirma)
    win.cancelou.connect(cancela)
    win.desfezVertice.connect(desenho.desfaz_vertice)
    view.pixelClicked.connect(ao_clicar)
    p_ciclo.gravar.connect(ao_gravar)
    tabs.fazendas.editarContorno.connect(lambda fid: fid and usa_modo(DESENHAR, fid))
    tabs.fazendas.editarDados.connect(preenche)
    tabs.fazendas.excluir.connect(exclui)
    tabs.fazendas.irPara.connect(centra_fazenda)
    tabs.fazendas.exportar.connect(lambda: exporta_camada('fazendas'))
    tabs.pontos.irPara.connect(vai_ao_ponto)
    tabs.pontos.excluir.connect(exclui_ponto)
    tabs.pontos.exportar.connect(lambda: exporta_camada('pontos'))
    view.vb.sigRangeChanged.connect(cam_pontos.redesenha)

    win.barra.cb_safra.blockSignals(True)
    win.barra.cb_safra.setCurrentText(safra)
    win.barra.cb_safra.blockSignals(False)
    usa_safra(safra)
    usa_camada(CAMADAS_MES[0])
    if cam_car is not None:
        cam_car.visivel(win.barra.bt_car.isChecked())     # aparece desde a abertura
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
