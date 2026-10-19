# Pre-segmentacao do AOI inteiro com SAM 2.1 (hiera-large) sobre o composto NDVI-temporal.
# Saida: F:\sits_aoi_crop\sam\sam_aoi.gpkg -- os talhoes como poligonos, para o navegador usar
# no modo Desenhar do mesmo jeito que usa o CAR (clicar dentro -> contorno editavel).
#
# Tiles de 1024 px com sobreposicao de 128; cada poligono so' e' aceito no tile em que seu
# centroide cai na zona central (fora da sobreposicao), para nao sair duplicado.
# Por tile grava um GPKG parcial (retomavel); no fim junta tudo.
import sys, time, pathlib, math
import numpy as np, rasterio, torch
from rasterio.windows import Window
from rasterio import features
from shapely.geometry import shape, box
from shapely.ops import unary_union
import geopandas as gpd

RAIZ = pathlib.Path(r"D:\PRG_CLAUDE\sam2"); sys.path.insert(0, str(RAIZ))
from sam2.build_sam import build_sam2
from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

IMG = r"F:\sits_aoi_crop\input\basemap_ndvitemporal_aoi.tif"
OUT = pathlib.Path(r"F:\sits_aoi_crop\sam"); PARTES = OUT / "partes"; PARTES.mkdir(parents=True, exist_ok=True)
N, OV = 1024, 128
AREA_MIN_HA = 0.5
SOLAPAMENTO_MAX = 0.90      # poligono contido >= 90% num maior do mesmo tile: descarta (mascara aninhada)

sam = build_sam2("configs/sam2.1/sam2.1_hiera_l.yaml", str(RAIZ / "checkpoints/sam2.1_hiera_large.pt"), device="cuda")
gen = SAM2AutomaticMaskGenerator(sam, points_per_side=32, pred_iou_thresh=0.8, stability_score_thresh=0.9,
                                 min_mask_region_area=200, crop_n_layers=0, output_mode="binary_mask")

with rasterio.open(IMG) as ds:
    W, H, crs = ds.width, ds.height, ds.crs
    passo = N - OV
    cols = list(range(0, max(W - OV, 1), passo)); rows = list(range(0, max(H - OV, 1), passo))
    total = len(cols) * len(rows)
    print(f"{W}x{H} -> {len(cols)}x{len(rows)} = {total} tiles de {N} (sobreposicao {OV})", flush=True)
    t_ini = time.time(); feitos = 0; pulados = 0
    for ri, r0 in enumerate(rows):
        for ci, c0 in enumerate(cols):
            k = ri * len(cols) + ci
            parte = PARTES / f"t_{ri:03d}_{ci:03d}.gpkg"
            if parte.exists():
                pulados += 1; continue
            w = min(N, W - c0); h = min(N, H - r0)
            rgb = ds.read([1, 2, 3], window=Window(c0, r0, w, h))
            if (rgb.sum(0) == 0).mean() > 0.98:          # tile praticamente sem dado
                parte.touch(); continue
            img = np.ascontiguousarray(np.transpose(rgb, (1, 2, 0)))
            T = ds.window_transform(Window(c0, r0, w, h))
            t0 = time.time()
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                masks = gen.generate(img)
            # zona central do tile (em pixel do tile): so' aceita centroide aqui
            mx0 = 0 if ci == 0 else OV // 2; my0 = 0 if ri == 0 else OV // 2
            mx1 = w if ci == len(cols) - 1 else w - OV // 2
            my1 = h if ri == len(rows) - 1 else h - OV // 2
            cand = []
            for m in masks:
                seg = m["segmentation"]
                melhor = None
                for g, v in features.shapes(seg.astype(np.uint8), mask=seg):   # em pixel do tile
                    if v == 1:
                        s = shape(g)
                        if melhor is None or s.area > melhor.area:
                            melhor = s                                        # so' a maior parte da mascara
                if melhor is None:
                    continue
                cx, cy = melhor.centroid.x, melhor.centroid.y
                if not (mx0 <= cx < mx1 and my0 <= cy < my1):
                    continue
                if melhor.area * (T.a * T.a) / 1e4 < AREA_MIN_HA:
                    continue
                cand.append((melhor, float(m["predicted_iou"]), float(m["stability_score"])))
            # mascaras aninhadas: descarta a menor quando esta' quase toda dentro de uma maior
            cand.sort(key=lambda t: -t[0].area)
            aceitos = []
            for s, iou, est in cand:
                if any(s.intersection(g).area / s.area >= SOLAPAMENTO_MAX for g, _, _ in aceitos):
                    continue
                aceitos.append((s, iou, est))
            geoms, atrs = [], []
            for s, iou, est in aceitos:
                xs, ys = s.exterior.coords.xy
                X, Y = T * (np.asarray(xs), np.asarray(ys))
                from shapely.geometry import Polygon
                P = Polygon(zip(X, Y))
                geoms.append(P); atrs.append({"area_ha": P.area / 1e4, "iou": iou, "estab": est, "tile": k})
            gpd.GeoDataFrame(atrs or {"area_ha": [], "iou": [], "estab": [], "tile": []},
                             geometry=geoms, crs=crs).to_file(parte, layer="sam", driver="GPKG")
            feitos += 1
            if feitos % 10 == 0 or feitos == 1:
                dec = time.time() - t_ini
                print(f"[{k+1}/{total}] {len(masks)} masc -> {len(aceitos)} talhoes | {time.time()-t0:.1f}s | "
                      f"decorrido {dec/60:.1f} min, resta ~{dec/feitos*(total-feitos-pulados)/60:.0f} min", flush=True)

print("juntando partes...", flush=True)
partes = [gpd.read_file(p) for p in sorted(PARTES.glob("t_*.gpkg")) if p.stat().st_size > 0]
partes = [p for p in partes if len(p)]
tudo = gpd.GeoDataFrame(gpd.pd.concat(partes, ignore_index=True), crs=crs)
tudo["id"] = np.arange(1, len(tudo) + 1)
tudo.to_file(OUT / "sam_aoi.gpkg", layer="talhoes", driver="GPKG")
print(f"FIM: {len(tudo):,} talhoes | area mediana {tudo.area_ha.median():.1f} ha | "
      f"total {(time.time()-t_ini)/60:.0f} min -> {OUT / 'sam_aoi.gpkg'}", flush=True)
