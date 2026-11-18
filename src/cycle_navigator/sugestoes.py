# -*- coding: utf-8 -*-
"""SUGESTOES: quem usa escreve o que quer mudar, na hora, de dentro do programa.

Padrao trazido do iRest (Ricco): a melhoria nao vai por WhatsApp nem fica "pra lembrar depois". A
pessoa escreve no programa; a sugestao sai CARIMBADA com a tela que ela estava vendo (foto da janela)
e o contexto (safra, mes, camada, talhao aberto, versao); o dev -- uma sessao do Claude Code neste
computador -- le^ a fila, passa pelo crivo do Osmar, implementa e RESPONDE AQUI. Quem pediu ve^ o
status e a resposta na mesma janela.

A fila e' uma pasta: `<dados>/sugestoes/<id>.json` + `<id>.png`. Sem servidor: o programa roda em
campo, sem rede. O lado do dev e' `tools/sugestoes.py` (fila / ver / responder) e a skill
`.claude/skills/responder-sugestoes`.

⚠️ `Caixa` e' pura (pasta -> dicionarios), sem Qt: e' ela que os testes e o dev usam.
⚠️ Escrita ATOMICA (tmp + replace): o programa e o dev mexem na mesma pasta.
"""
import json
import os
from datetime import datetime
from pathlib import Path

STATUS = {"aberta": "aberta", "em_desenvolvimento": "em andamento", "implementada": "feita",
          "descartada": "não vai entrar", "aguardando_resposta": "aguardando você"}
COR = {"aberta": "#a9ac9c", "em_desenvolvimento": "#e0a23a", "implementada": "#8fc452",
       "descartada": "#767a6c", "aguardando_resposta": "#7fe7ff"}


def _agora():
    return datetime.now().isoformat(timespec="seconds")


class Caixa:
    def __init__(self, pasta):
        self.pasta = Path(pasta)

    def _grava(self, s):
        self.pasta.mkdir(parents=True, exist_ok=True)
        dest = self.pasta / f"{s['id']}.json"
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, dest)
        return s

    def nova(self, texto, quem="", contexto=None, foto=None):
        """`foto`: um QPixmap/QImage (ou qualquer coisa com .save(caminho)) da janela, ou None."""
        base = datetime.now().strftime("%Y%m%d-%H%M%S")
        sid, k = base, 1
        while (self.pasta / f"{sid}.json").exists():
            k += 1; sid = f"{base}-{k}"
        s = {"id": sid, "quando": _agora(), "quem": quem or "?", "texto": texto.strip(),
             "contexto": contexto or {}, "foto": None, "status": "aberta",
             "mensagens": [{"autor": "equipe", "quem": quem or "?", "texto": texto.strip(),
                            "quando": _agora()}], "visto_pela_equipe": True}
        if foto is not None:
            self.pasta.mkdir(parents=True, exist_ok=True)
            try:
                if foto.save(str(self.pasta / f"{sid}.png")):
                    s["foto"] = f"{sid}.png"
            except Exception:
                pass
        return self._grava(s)

    def lista(self, status=None):
        """Mais recentes primeiro. `status`: um nome ou uma colecao deles."""
        if not self.pasta.exists():
            return []
        quais = None if status is None else ({status} if isinstance(status, str) else set(status))
        out = []
        for p in sorted(self.pasta.glob("*.json"), reverse=True):
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if quais is None or s.get("status") in quais:
                out.append(s)
        return out

    def pega(self, sid):
        """Aceita o id inteiro ou so' o comeco dele."""
        for s in self.lista():
            if s["id"] == sid or s["id"].startswith(str(sid)):
                return s
        return None

    def mensagem(self, sid, texto, autor="equipe", quem="", status=None):
        """Mais uma mensagem na conversa. Do dev: acende o aviso para a equipe. Da equipe em cima de
        uma sugestao ja' respondida: ela REABRE (volta para a fila do dev)."""
        s = self.pega(sid)
        if s is None:
            raise KeyError(sid)
        if texto and texto.strip():
            s["mensagens"].append({"autor": autor, "quem": quem or autor, "texto": texto.strip(),
                                   "quando": _agora()})
        if autor == "dev":
            s["visto_pela_equipe"] = False
            if status:
                if status not in STATUS:
                    raise ValueError(f"status desconhecido: {status}")
                s["status"] = status
        else:
            s["visto_pela_equipe"] = True
            if s["status"] in ("implementada", "descartada", "aguardando_resposta"):
                s["status"] = "aberta"
                s["reaberta"] = True
        return self._grava(s)

    def marca_vistas(self):
        n = 0
        for s in self.lista():
            if not s.get("visto_pela_equipe", True):
                s["visto_pela_equipe"] = True
                self._grava(s); n += 1
        return n

    def novidades(self):
        """Quantas respostas do dev a equipe ainda nao viu."""
        return sum(1 for s in self.lista() if not s.get("visto_pela_equipe", True))
