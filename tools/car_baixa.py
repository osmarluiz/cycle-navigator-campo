# Baixa a base estadual do CAR (perimetro dos imoveis = Polygon.AREA_PROPERTY) via SICAR.
# Uso: python baixa_car.py DF [GO MG ...]
# O captcha e' resolvido por OCR (Tesseract); o pacote tenta varias vezes sozinho.
import inspect, pathlib, sys, time

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from SICAR import Polygon, Sicar, State
from SICAR.drivers import Tesseract

DEST = pathlib.Path(r"F:\sits_aoi_crop\car")
DEST.mkdir(parents=True, exist_ok=True)

car = Sicar(driver=Tesseract)
try:
    datas = car.get_release_dates()
    print("datas das bases:", {k.value: v for k, v in datas.items() if k.value in ("DF", "GO", "MG")},
          flush=True)
except Exception as e:
    print("get_release_dates falhou:", type(e).__name__, e, flush=True)

sig = inspect.signature(car.download_state)
kw = {}
for nome in ("folder", "output", "path", "dest"):
    if nome in sig.parameters:
        kw[nome] = str(DEST)
        break
print("assinatura:", sig, "| usando:", kw, flush=True)

for uf in sys.argv[1:]:
    t0 = time.time()
    print(f"=== {uf}: inicio {time.strftime('%H:%M:%S')} ===", flush=True)
    try:
        r = car.download_state(State[uf], Polygon.AREA_PROPERTY, **kw)
        print(f"  {uf} OK em {(time.time()-t0)/60:.1f} min -> {r}", flush=True)
    except Exception as e:
        print(f"  {uf} FALHOU apos {(time.time()-t0)/60:.1f} min: {type(e).__name__}: {e}", flush=True)
print("conteudo de", DEST, flush=True)
for p in sorted(DEST.rglob("*")):
    if p.is_file():
        print(f"  {p.stat().st_size/1e6:8.1f} MB  {p.relative_to(DEST)}", flush=True)
