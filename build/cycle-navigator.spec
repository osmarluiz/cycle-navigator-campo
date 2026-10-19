# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: `pyinstaller build/cycle-navigator.spec` na raiz do repositorio.
# ONEDIR, nao onefile: o programa tem ~300 MB de DLLs (GDAL/PROJ/Qt); onefile extrairia tudo para
# uma pasta temporaria a cada abertura, e num notebook de campo isso e' meio minuto de espera.
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hidden = [], [], []
for pkg in ("rasterio", "pyproj", "shapely", "pyogrio", "geopandas", "pyqtgraph", "qtawesome",
            "pheno_engine", "ts_annotator", "cycle_navigator", "matplotlib"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h
hidden += collect_submodules("rasterio") + ["PyQt6.QtSvg", "PyQt6.sip"]

a = Analysis(["launcher.py"], pathex=["../src"], binaries=binaries, datas=datas,
             hiddenimports=hidden, hookspath=[], runtime_hooks=[],
             excludes=["torch", "tkinter", "PyQt5", "PySide6", "IPython", "notebook", "scipy.spatial.cKDTree"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="cycle-navigator",
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CycleNavigator")

# No Mac o resultado vira um .app de verdade (clicavel no Finder); no Windows/Linux fica a pasta.
import sys
if sys.platform == "darwin":
    app = BUNDLE(coll, name="CycleNavigator.app", bundle_identifier="br.unb.cyclenavigator",
                 info_plist={"NSHighResolutionCapable": True, "CFBundleDisplayName": "Cycle Navigator"})
