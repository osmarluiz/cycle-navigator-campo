# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: `pyinstaller build/cycle-navigator.spec` na raiz do repositorio.
# ONEDIR, nao onefile: o programa tem ~300 MB de DLLs (GDAL/PROJ/Qt); onefile extrairia tudo para
# uma pasta temporaria a cada abertura, e num notebook de campo isso e' meio minuto de espera.
from importlib.metadata import version
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

# icones gerados de build/icone/icone.svg (build/icone/gera_icones.py); a versao vem do pacote
# instalado, isto e', do pyproject.toml -- uma fonte so', sem numero repetido aqui.
import os
ICO, ICNS = (os.path.join(SPECPATH, "icone", n) for n in ("icone.ico", "icone.icns"))
VERSAO = version("cycle-navigator")

datas, binaries, hidden = [], [], []
for pkg in ("rasterio", "pyproj", "shapely", "pyogrio", "geopandas", "pyqtgraph", "qtawesome",
            "pheno_engine", "ts_annotator", "cycle_navigator", "matplotlib"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h
hidden += collect_submodules("rasterio") + ["PyQt6.QtSvg", "PyQt6.sip", "PyQt6.QtPositioning"]

# ⚠️ RECORTE NA HORA (SAM 2) E' OPCIONAL: so' entra no pacote se torch e sam2 estiverem instalados
# no ambiente de build (extra `recorte` do pyproject). Sem eles o executavel sai como antes, ~1 GB
# menor, e o programa esconde o botao "Recortar". O sam2 monta o modelo com hydra, que le^ os .yaml
# de dentro do pacote: por isso collect_all nos tres, senao "config not found" so' em campo.
EXCLUI = ["tkinter", "PyQt5", "PySide6", "IPython", "notebook", "scipy.spatial.cKDTree"]
try:
    import sam2, torch          # noqa: F401
    # torchvision: sem collect_all a extensao C dele (_C.so) fica de fora e o modelo morre em
    # "operator torchvision::nms does not exist" -- so' no pacote, nunca rodando do codigo.
    for pkg in ("sam2", "hydra", "omegaconf", "torchvision"):
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    print("spec: recorte na hora (torch + sam2) INCLUIDO")
except ImportError:
    EXCLUI.append("torch")
    print("spec: recorte na hora fora do pacote (torch/sam2 nao instalados)")

a = Analysis(["launcher.py"], pathex=["../src"], binaries=binaries, datas=datas,
             hiddenimports=hidden, hookspath=[], runtime_hooks=[],
             excludes=EXCLUI,
             noarchive=False)
pyz = PYZ(a.pure)
# console=False: sem a janela preta de terminal atras do programa. O log vai para
# cycle-navigator.log ao lado do executavel (ver launcher.py) -- e' isso que se pede ao aluno
# quando algo der errado em campo.
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="cycle-navigator",
          debug=False, strip=False, upx=False, console=False, icon=ICO)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CycleNavigator")

# No Mac o resultado vira um .app de verdade (clicavel no Finder); no Windows/Linux fica a pasta.
import sys
if sys.platform == "darwin":
    app = BUNDLE(coll, name="CycleNavigator.app", bundle_identifier="br.unb.cyclenavigator",
                 icon=ICNS, version=VERSAO,
                 info_plist={"NSHighResolutionCapable": True, "CFBundleDisplayName": "Cycle Navigator",
                             "CFBundleVersion": VERSAO,
                             # sem esta chave o macOS nega a localizacao sem perguntar ("Onde estou")
                             "NSLocationWhenInUseUsageDescription":
                                 "Mostrar no mapa onde voce esta durante o levantamento de campo."})
    # ⚠️ pyproj e rasterio trazem cada um a sua libproj com o MESMO nome, e o PyInstaller so' guarda
    # uma: sem isto o pyproj nao importava no .app e a exportacao saia sem CRS. Ver o arquivo.
    sys.path.insert(0, SPECPATH)
    from corrige_dylibs_mac import corrige
    print(f"corrige_dylibs_mac: {corrige(Path(DISTPATH) / 'CycleNavigator.app')} binarios religados")
