# -*- coding: utf-8 -*-
"""O lado do DEV da fila de sugestoes (ver src/cycle_navigator/sugestoes.py e a skill
.claude/skills/responder-sugestoes).

    python tools/sugestoes.py                       fila aberta (reabertas primeiro)
    python tools/sugestoes.py todas                 tudo, com status
    python tools/sugestoes.py ver <id>              conversa + contexto + caminho da foto (abrir com Read)
    python tools/sugestoes.py responder <id> <status> <resposta.txt | "texto">
                                                    status: em_desenvolvimento | implementada |
                                                            descartada | aguardando_resposta

A pasta vem de --pasta, de CN_SUGESTOES, ou do .toml (CN_CONFIG / ~/CycleNavigator/cycle-navigator.toml).
"""
import argparse
import json
import os
import sys
from pathlib import Path

from cycle_navigator.sugestoes import STATUS, Caixa


def _pasta(arg):
    if arg:
        return Path(arg)
    if os.environ.get("CN_SUGESTOES"):
        return Path(os.environ["CN_SUGESTOES"])
    from cycle_navigator.config import carrega
    cfg = carrega(os.environ.get("CN_CONFIG") or str(Path.home() / "CycleNavigator" / "cycle-navigator.toml"))
    return cfg.aoi / "sugestoes"


def _linha(s):
    marca = "REABERTA " if s.get("reaberta") and s["status"] == "aberta" else ""
    c = s.get("contexto") or {}
    return (f"[{s['id']}] {marca}{s['status']} · {s.get('quem')} · safra {c.get('safra')} "
            f"{c.get('mes_rotulo', '')} · {c.get('camada', '')} · msgs {len(s.get('mensagens', []))}\n"
            f"    {s.get('texto', '')[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta")
    ap.add_argument("cmd", nargs="?", default="fila")
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    cx = Caixa(_pasta(a.pasta))
    if a.cmd in ("fila", "todas"):
        itens = cx.lista() if a.cmd == "todas" else cx.lista(("aberta", "em_desenvolvimento"))
        itens.sort(key=lambda s: (not s.get("reaberta"), s["id"]))
        print(f"{len(itens)} sugestao(oes) em {cx.pasta}")
        for s in itens:
            print(_linha(s))
    elif a.cmd == "ver":
        s = cx.pega(a.args[0])
        if s is None:
            sys.exit("nao achei essa sugestao")
        print(_linha(s))
        print("contexto:", json.dumps(s.get("contexto"), ensure_ascii=False, indent=1))
        if s.get("foto"):
            print("foto da tela:", cx.pasta / s["foto"])
        for m in s.get("mensagens", []):
            print(f"\n--- {m['autor']} ({m.get('quem')}) {m['quando']}\n{m['texto']}")
    elif a.cmd == "responder":
        sid, status, resto = a.args[0], a.args[1], " ".join(a.args[2:])
        if status not in STATUS:
            sys.exit(f"status deve ser um de: {', '.join(STATUS)}")
        texto = Path(resto).read_text(encoding="utf-8") if resto and Path(resto).is_file() else resto
        s = cx.mensagem(sid, texto, autor="dev", quem="Claude", status=status)
        print("respondida:", _linha(s))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
