# -*- coding: utf-8 -*-
"""VIGIA DAS SUGESTOES: fica olhando a fila e TERMINA quando cai sugestao nova ou reaberta.

Padrao do iRest (Ricco): roda em segundo plano dentro de uma sessao do Claude Code; ao terminar, a
sessao e' acordada com o que chegou e segue a skill `responder-sugestoes` (crivo do Osmar antes de
qualquer codigo). Depois de tratar, a sessao liga o vigia de novo.

    python tools/vigia_sugestoes.py [--pasta P] [--horas 10] [--cada 5]

⚠️ INSTANCIA UNICA (aprendizado da Ricco): dois vigias disputam o arquivo de vistas, um marca a
novidade e o outro diz "nada novo" -- o aviso se perde. A trava garante um so'.
⚠️ As "vistas" ficam em `<pasta>/.vistas` (id:numero de mensagens): resposta nova da equipe em cima de
uma sugestao ja' vista muda a chave e acorda de novo.
"""
import argparse
import fcntl
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sugestoes import _pasta          # noqa: E402
from cycle_navigator.sugestoes import Caixa   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta"); ap.add_argument("--horas", type=float, default=10)
    ap.add_argument("--cada", type=float, default=5)
    a = ap.parse_args()
    cx = Caixa(_pasta(a.pasta))
    cx.pasta.mkdir(parents=True, exist_ok=True)
    trava = open(cx.pasta / ".vigia.lock", "w")
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("vigia ja' rodando em outra instancia — saindo")
        return 0
    arq = cx.pasta / ".vistas"
    vistas = set(arq.read_text().split()) if arq.exists() else set()
    fim = time.time() + a.horas * 3600
    print(f"vigia ligado em {cx.pasta} ({len(vistas)} ja' vistas)", flush=True)
    while time.time() < fim:
        novas = []
        for s in cx.lista(("aberta", "em_desenvolvimento")):
            msgs = s.get("mensagens") or []
            chave = f"{s['id']}:{len(msgs)}"
            if chave not in vistas and msgs and msgs[-1].get("autor") != "dev":
                novas.append((chave, s))
        if novas:
            with open(arq, "a") as f:
                for chave, _s in novas:
                    f.write(chave + "\n")
            print("SUGESTAO NOVA — usar a skill responder-sugestoes:")
            for _chave, s in novas:
                c = s.get("contexto") or {}
                print(f"{'REABERTA' if s.get('reaberta') else 'NOVA'} [{s['id']}] {s.get('quem')} · "
                      f"safra {c.get('safra')} {c.get('mes_rotulo', '')} · {c.get('camada', '')} · "
                      f"{c.get('talhao', 'sem talhão aberto')}\n    {s['mensagens'][-1]['texto'][:400]}"
                      + (f"\n    foto: {cx.pasta / s['foto']}" if s.get("foto") else ""))
            return 0
        time.sleep(a.cada)
    print("vigia: tempo esgotado sem novidade — religar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
