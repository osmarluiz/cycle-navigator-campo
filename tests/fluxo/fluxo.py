# O fluxo REAL do programa, offscreen: ligar camadas, clicar, selecionar, adotar, modos, zoom.
# Roda num subprocesso: se o Qt abortar (0xc0000409), o codigo de saida denuncia. Cada etapa
# imprime ANTES de executar, para o log dizer onde morreu.
import os, sys, time, pathlib
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from unittest import mock
import numpy as np
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import QPointF, Qt

def etapa(t):
    print("  ->", t, flush=True)

app = QApplication(sys.argv[:1])
from cycle_navigator import estilo
estilo.aplica(app)
from cycle_navigator.config import carrega
from cycle_navigator.app import monta_app
from cycle_navigator.janela import IDENTIFICAR, DESENHAR, EDITAR
cfg = carrega(r"D:\NAVIGATOR\cycle-navigator.toml")
etapa("monta_app"); ctx = monta_app(cfg, app)
ctx.win.resize(1600, 980); ctx.win.show(); app.processEvents()
etapa("levantador"); ctx.p_pontos.ed_levantador.setText("teste")

def pixel_dentro(cam):
    i = cam.n // 2
    rp = cam.polys[i].representative_point()
    return int(rp.y), int(rp.x)

def clique(row, col, n=3):
    for _ in range(n):
        ctx.ao_clicar(row, col); app.processEvents()

r_car, c_car = pixel_dentro(ctx.cam_car)
r_sam, c_sam = pixel_dentro(ctx.cam_sam)
etapa("clique sem camadas (CAR/SAM desligados)"); clique(r_car, c_car); clique(r_sam, c_sam)
etapa("liga CAR"); ctx.win.barra.bt_car.setChecked(True); app.processEvents()
etapa("clique dentro do CAR -> seleciona"); clique(r_car, c_car)
etapa("liga SAM"); ctx.win.barra.bt_sam.setChecked(True); app.processEvents()
etapa("clique dentro do SAM -> seleciona"); clique(r_sam, c_sam)
etapa("clique fora de tudo"); clique(5, 5)
etapa("zoom no AOI inteiro com as duas camadas (LOD)"); ctx.view.vb.setRange(xRange=(0, 28813), yRange=(0, 30293), padding=0); app.processEvents()
for k in range(4):
    etapa(f"zoom aproximando {k}"); ctx.view.vb.setRange(xRange=(c_sam - 3000 // (k + 1), c_sam + 3000 // (k + 1)),
                                                        yRange=(r_sam - 3000 // (k + 1), r_sam + 3000 // (k + 1)), padding=0); app.processEvents()
etapa("Esc limpa"); ctx.cancela(); app.processEvents()
etapa("modo Editar + clique num talhao SAM -> adota (dialogo aceito)")
with mock.patch("cycle_navigator.app.DialogoFazenda.exec", return_value=QDialog.DialogCode.Accepted), \
     mock.patch("cycle_navigator.app.DialogoFazenda.dados", return_value={"nome": "Teste SAM", "proprietario": "x",
                                                                           "contato": "", "status": "visitado",
                                                                           "data_visita": "2026-10-19", "obs": ""}):
    ctx.usa_modo(EDITAR); app.processEvents()
    clique(r_sam, c_sam, 1)
    etapa("Enter confirma"); ctx.confirma(); app.processEvents()
etapa("fazendas apos adocao: %d" % len(ctx.cadastro))
etapa("modo Desenhar + clique dentro do CAR -> semeia")
ctx.usa_modo(DESENHAR); app.processEvents()
class Ev:
    def __init__(self, x, y):
        self._p = ctx.view.vb.mapViewToScene(QPointF(x, y))
    def scenePos(self): return self._p
    def button(self): return Qt.MouseButton.LeftButton
    def double(self): return False
ctx.no_clique(Ev(c_car, r_car)); app.processEvents()
etapa("Esc cancela o desenho"); ctx.cancela(); app.processEvents()
etapa("volta a Identificar e clica de novo nos dois"); clique(r_car, c_car); clique(r_sam, c_sam)
etapa("troca safra"); ctx.usa_safra(list(cfg.safras)[0]); app.processEvents(); clique(r_sam, c_sam)
etapa("troca camada/data"); ctx.usa_camada("NDVI do mês"); ctx.usa_data(cfg.meses_de(list(cfg.safras)[0])[3]); app.processEvents()
etapa("desliga as camadas"); ctx.win.barra.bt_sam.setChecked(False); ctx.win.barra.bt_car.setChecked(False); app.processEvents()
etapa("limpa a fazenda de teste")
for f in list(ctx.cadastro.fazendas):
    if f.get("nome") == "Teste SAM": ctx.cadastro.remove(f["id"])
etapa("fecha a janela"); ctx.win.close(); app.processEvents()
print("  pronto.", flush=True)
