# Junta as bases estaduais do CAR (DF, GO, MG), recorta pelo retangulo do AOI e grava um
# GeoPackage unico em UTM 23S -- a camada de referencia "de quem e'" para o navegador.
#
# ⚠️ Recorta por INTERSECAO com o retangulo, nao por "dentro": um imovel que cruza a borda do AOI
# entra inteiro. Cortar o poligono na borda inventaria um limite de propriedade que nao existe.
import pathlib, sys, zipfile

import geopandas as gpd
from shapely.geometry import box

PASTA = pathlib.Path(r"F:\sits_aoi_crop\car")
SAIDA = PASTA / "car_aoi.gpkg"
# retangulo do AOI em EPSG:32723 (mesmo dos recortes do cubo)
AOI = box(148007.195, 8139988.193, 285655.950, 8284707.375)
CRS = "EPSG:32723"


def shp_dentro(zp):
    with zipfile.ZipFile(zp) as z:
        return [n for n in z.namelist() if n.lower().endswith(".shp")]


partes = []
for zp in sorted(PASTA.glob("*.zip")):
    shps = shp_dentro(zp)
    print(f"{zp.name}: {len(shps)} shapefile(s) -> {shps}", flush=True)
    for shp in shps:
        g = gpd.read_file(f"zip://{zp}!{shp}")
        print(f"   {shp}: {len(g):,} feicoes, CRS {g.crs}, colunas {list(g.columns)}", flush=True)
        g = g.to_crs(CRS)
        dentro = g[g.intersects(AOI)].copy()
        dentro["area_ha"] = dentro.geometry.area / 1e4
        print(f"   -> {len(dentro):,} imoveis tocam o AOI", flush=True)
        partes.append(dentro)

if not partes:
    sys.exit("nenhum zip em " + str(PASTA))
tudo = gpd.GeoDataFrame(gpd.pd.concat(partes, ignore_index=True), crs=CRS)
# imovel com registro em dois estados (divisa) aparece duas vezes: fica uma
if "cod_imovel" in tudo.columns:
    antes = len(tudo)
    tudo = tudo.drop_duplicates("cod_imovel")
    print(f"duplicados por cod_imovel removidos: {antes - len(tudo)}", flush=True)
tudo.to_file(SAIDA, layer="area_imovel", driver="GPKG")
# ⚠️ a soma de area_ha PASSA da area do territorio: o CAR e' autodeclarado e imoveis se sobrepoem
print(f"\n{SAIDA}: {len(tudo):,} imoveis (area declarada somada: {tudo.area_ha.sum()/1e3:,.0f} mil ha,"
      f" com sobreposicoes)", flush=True)
for col in ("cod_estado", "municipio", "ind_status", "ind_tipo"):
    if col in tudo.columns:
        print(f"\n{col}:\n" + tudo.groupby(col).size().sort_values(ascending=False).head(12).to_string())
