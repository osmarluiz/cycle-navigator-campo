# -*- coding: utf-8 -*-
"""Ponto de entrada do executavel (PyInstaller). O `cycle-navigator.toml` e' procurado AO LADO do
executavel antes dos lugares de sempre: no notebook de campo e' la' que ele vai estar."""
import os
import sys
from pathlib import Path


def main():
    base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else None
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    toml = exe_dir / "cycle-navigator.toml"
    argv = sys.argv[1:]
    if "--config" not in argv and toml.exists():
        argv = ["--config", str(toml)] + argv
    os.chdir(exe_dir)
    from cycle_navigator.app import main as app_main
    return app_main(argv)


if __name__ == "__main__":
    sys.exit(main())
