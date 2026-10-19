# Estresse do fluxo real: trocas RAPIDAS de data/camada (set_source) com zoom e camadas ligadas.
import os, sys, time, pathlib
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv[:1])
from cycle_navigator import estilo; estilo.aplica(app)
from cycle_navigator.config import carrega
from cycle_navigator.app import monta_app, CAMADAS_MES, CAMADAS_ANO

def etapa(t): print("  ->", t, flush=True)
cfg = carrega(r"D:\NAVIGATOR\cycle-navigator.toml")
etapa("monta_app"); ctx = monta_app(cfg, app); ctx.win.resize(1600, 980); ctx.win.show(); app.processEvents()
b = ctx.win.barra
i = ctx.cam_sam.n // 2; rp = ctx.cam_sam.polys[i].representative_point(); cx, cy = rp.x, rp.y
ctx.view.vb.setRange(xRange=(cx - 1200, cx + 1200), yRange=(cy - 1200, cy + 1200), padding=0); app.processEvents()
b.bt_car.setChecked(True); b.bt_sam.setChecked(True); app.processEvents()

etapa("36 passos de mes com as setas, sem esperar os tiles")
for k in range(36):
    b.passo(+1)
    if k % 6 == 0: app.processEvents()
etapa("36 passos processando eventos a cada passo")
for k in range(36):
    b.passo(-1); app.processEvents()
etapa("alterna camadas mensais e do ano, rapido")
for k in range(3):
    for cam in CAMADAS_MES + CAMADAS_ANO:
        b.cb_camada.setCurrentText(cam)
        if k == 2: app.processEvents()
etapa("zoom in/out repetido com camadas ligadas")
for k in range(10):
    z = 300 + 2500 * (k % 2)
    ctx.view.vb.setRange(xRange=(cx - z, cx + z), yRange=(cy - z, cy + z), padding=0); app.processEvents()
etapa("troca de safra 4x com clique entre elas")
for s in list(cfg.safras) * 1:
    ctx.usa_safra(s); app.processEvents(); ctx.ao_clicar(int(cy), int(cx)); app.processEvents()
etapa("deixa os tiles terminarem (2 s)")
t0 = time.time()
while time.time() - t0 < 2: app.processEvents()
etapa("fecha"); ctx.win.close(); app.processEvents()
print("  pronto.", flush=True)
