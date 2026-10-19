# -*- coding: utf-8 -*-
"""EXPORTAR PARA SIG: fazendas (poligonos) e pontos rotulados (uma feicao por FAIXA).

⚠️ UMA FEICAO POR FAIXA, NAO POR PONTO. Quem abre isto no QGIS quer colorir por cultura e filtrar
por mes -- e isso so' funciona se cultura e mes forem colunas de cada linha. Uma feicao por ponto
com as faixas empacotadas num texto obrigaria a desempacotar de novo do outro lado.

⚠️ GEOPACKAGE POR PADRAO; SHAPEFILE SO' SE PEDIREM. O shapefile corta nome de coluna em 10
caracteres e nao guarda acento direito; "levantador" vira "levantador" por sorte, "data_visita"
vira "data_visit". O GeoPackage nao tem nenhum desses limites, abre em qualquer SIG atual, e e' um
arquivo so' em vez de cinco. Ainda assim o .shp existe, porque e' o que muita gente ainda pede.
"""
import logging

log = logging.getLogger(__name__)

# nomes curtos (<= 10 chars) para o shapefile; o GeoPackage usa os nomes completos
CURTO = {"proprietario": "proprietar", "data_visita": "data_visit", "atualizado_em": "atualizado",
         "levantador": "levantador", "gravado_em": "gravado_em", "confianca": "confianca",
         "n_faixas": "n_faixas"}


def _gpd():
    try:
        import geopandas as gpd
        from shapely.geometry import Point, Polygon
        return gpd, Point, Polygon
    except ImportError as e:          # extra `pivots`; sem ele, so' CSV
        raise RuntimeError("exportar para GeoPackage/Shapefile precisa do geopandas "
                           "(pip install 'cycle-navigator[pivots]')") from e


def _grava(gdf, caminho, camada):
    caminho = str(caminho)
    if caminho.lower().endswith(".shp"):
        gdf = gdf.rename(columns={c: CURTO.get(c, c[:10]) for c in gdf.columns if c != "geometry"})
        gdf.to_file(caminho, driver="ESRI Shapefile", encoding="utf-8")
    else:
        gdf.to_file(caminho, layer=camada, driver="GPKG")
    return caminho


def fazendas(cadastro, caminho):
    gpd, _Point, Polygon = _gpd()
    linhas, geoms = [], []
    for f in cadastro.fazendas:
        utm = f.get("poligono_utm")
        if not utm or len(utm) < 3:
            continue
        geoms.append(Polygon([(x, y) for x, y in utm]))
        linhas.append({"id": f["id"], "nome": f.get("nome", ""),
                       "proprietario": f.get("proprietario", ""),
                       "contato": f.get("contato", ""), "status": f.get("status", ""),
                       "data_visita": f.get("data_visita", ""), "obs": f.get("obs", ""),
                       "car": f.get("car", ""),          # codigo do imovel, quando adotado do CAR
                       "car_municipio": f.get("car_municipio", ""),
                       "car_area_ha": f.get("car_area_ha"),
                       "car_mod_fiscal": f.get("car_mod_fiscal"),
                       "car_status": f.get("car_status", ""),
                       "car_tipo": f.get("car_tipo", ""),
                       "car_condicao": f.get("car_condicao", ""),
                       "car_atualizado": f.get("car_atualizado", ""),
                       "area_ha": f.get("area_ha"), "atualizado_em": f.get("atualizado_em", "")})
    if not linhas:
        raise RuntimeError("nenhuma fazenda com contorno para exportar")
    gdf = gpd.GeoDataFrame(linhas, geometry=geoms, crs=cadastro.crs)
    out = _grava(gdf, caminho, "fazendas")
    log.info("exportadas %d fazenda(s) -> %s", len(gdf), out)
    return len(gdf), out


def pontos(store, caminho):
    gpd, Point, _Polygon = _gpd()
    linhas, geoms = [], []
    for p in store.points:
        if p.get("x") is None:
            continue
        cic = p.get("ciclos") or [{}]
        for i, s in enumerate(cic, 1):
            geoms.append(Point(p["x"], p["y"]))
            linhas.append({"id": p["id"], "faixa": i, "n_faixas": len(cic),
                           "cultura": s.get("cultura", p.get("class", "")),
                           "confianca": s.get("confianca", ""),
                           "mes_ini": s.get("mes_ini"), "mes_fim": s.get("mes_fim"),
                           "safra": p.get("period", ""), "fazenda": p.get("fazenda", ""),
                           "produtor": p.get("produtor", ""), "contato": p.get("contato", ""),
                           "levantador": p.get("levantador", ""),
                           "gravado_em": p.get("gravado_em", ""),
                           "row": p["row"], "col": p["col"]})
    if not linhas:
        raise RuntimeError("nenhum ponto rotulado para exportar")
    gdf = gpd.GeoDataFrame(linhas, geometry=geoms, crs=store.crs)
    out = _grava(gdf, caminho, "pontos")
    log.info("exportadas %d faixa(s) de %d ponto(s) -> %s", len(gdf), len(store.points), out)
    return len(gdf), out
