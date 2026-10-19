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
    # Sem console (ver o .spec), o log precisa de um lugar: um arquivo ao lado do executavel,
    # reescrito a cada abertura. E' o que se pede ao aluno quando algo der errado em campo.
    import logging
    try:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                            filename=str(exe_dir / "cycle-navigator.log"), filemode="w",
                            encoding="utf-8")
    except OSError:
        logging.basicConfig(level=logging.INFO)     # pasta somente-leitura: segue sem arquivo
    try:
        from cycle_navigator.app import main as app_main
        return app_main(argv)
    except Exception:
        logging.exception("o programa fechou com erro")
        raise


if __name__ == "__main__":
    sys.exit(main())
