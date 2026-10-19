# UM tile real pelo SAM 2.1: tempo por tile e cara das mascaras. Decide se vale a pre-segmentacao.
import sys, time, pathlib
import numpy as np, rasterio, torch
from rasterio.windows import Window
from rasterio import features
from shapely.geometry import shape
import geopandas as gpd

RAIZ = pathlib.Path(r"D:\PRG_CLAUDE\sam2")
sys.path.insert(0, str(RAIZ))
from sam2.build_sam import build_sam2
from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

IMG = r"F:\sits_aoi_crop\input\basemap_ndvitemporal_aoi.tif"
COL, ROW, N = 16208 - 512, 21884 - 512, 1024          # tile em volta de um pixel de lavoura conhecido
OUT = pathlib.Path(r"F:\sits_aoi_crop\sam"); OUT.mkdir(exist_ok=True)

t0 = time.time()
sam = build_sam2("configs/sam2.1/sam2.1_hiera_l.yaml", str(RAIZ / "checkpoints/sam2.1_hiera_large.pt"),
                 device="cuda")
gen = SAM2AutomaticMaskGenerator(sam, points_per_side=32, pred_iou_thresh=0.8,
                                 stability_score_thresh=0.9, min_mask_region_area=200,
                                 crop_n_layers=0, output_mode="binary_mask")
print(f"modelo carregado em {time.time()-t0:.1f} s", flush=True)

with rasterio.open(IMG) as ds:
    win = Window(COL, ROW, N, N)
    rgb = ds.read([1, 2, 3], window=win)            # (3, N, N) uint8
    T = ds.window_transform(win); crs = ds.crs
img = np.transpose(rgb, (1, 2, 0)).copy()
print(f"tile {N}x{N} lido: media {img.mean():.0f}, nodata {np.mean(img.sum(2)==0)*100:.1f}%", flush=True)

t1 = time.time()
with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    masks = gen.generate(img)
dt = time.time() - t1
print(f"SAM: {len(masks)} mascaras em {dt:.1f} s  (-> {dt*830/3600:.1f} h para os ~830 tiles do AOI)", flush=True)

geoms, atrs = [], []
for m in masks:
    for g, v in features.shapes(m["segmentation"].astype(np.uint8), mask=m["segmentation"], transform=T):
        if v == 1:
            s = shape(g)
            geoms.append(s); atrs.append({"area_ha": s.area / 1e4, "iou": m["predicted_iou"],
                                          "estab": m["stability_score"]})
gdf = gpd.GeoDataFrame(atrs, geometry=geoms, crs=crs)
gdf.to_file(OUT / "sam_probe.gpkg", layer="probe", driver="GPKG")
a = gdf.area_ha
print(f"poligonos: {len(gdf)} | area: min {a.min():.2f}  mediana {a.median():.1f}  max {a.max():.0f} ha "
      f"| cobertura do tile: {gdf.geometry.union_all().area/(N*N*T.a*T.a)*100:.0f}%", flush=True)
print("GPU pico:", round(torch.cuda.max_memory_allocated()/2**30, 1), "GB", flush=True)
