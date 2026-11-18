# -*- coding: utf-8 -*-
"""MONTAGEM · canal_sugestoes: a janela de sugestoes e o aviso de resposta.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
from ..janela_sugestoes import JanelaSugestoes
from ..sugestoes import Caixa


def instala(ctx):
    analise = ctx.analise
    cfg = ctx.cfg
    estado = ctx.estado
    latlon = ctx.latlon
    p_ciclo = ctx.p_ciclo
    p_pontos = ctx.p_pontos
    tabs = ctx.tabs
    win = ctx.win

    # ---------------- sugestoes ----------------
    caixa = Caixa(cfg.aoi / "sugestoes")
    j_sug = JanelaSugestoes(caixa)

    def abre_sugestoes():
        # ⚠️ a foto e' tirada ANTES de a janela de sugestoes abrir: e' a tela de que a pessoa esta'
        # falando. So' a janela do programa, nunca a tela inteira.
        from importlib.metadata import version
        from ..ciclos import rotulo_mes
        ctxo = {"safra": estado["safra"], "mes": estado["mes"],
                "mes_rotulo": rotulo_mes(estado["mes"]) if estado["mes"] else "",
                "camada": estado["camada"], "modo": estado["modo"], "fonte": estado["fonte"],
                "talhoes_levantados": len(p_pontos.store) if p_pontos.store is not None else 0}
        try:
            ctxo["versao"] = version("cycle-navigator")
        except Exception:
            pass
        if p_ciclo.rc is not None:
            import re
            ctxo["row"], ctxo["col"] = int(p_ciclo.rc[0]), int(p_ciclo.rc[1])
            ctxo["latlon"] = latlon(*p_ciclo.rc)
            limpa = lambda t: re.sub(r"<[^>]+>", "", t).replace("&nbsp;", " ").strip()
            ctxo["talhao"] = limpa(p_ciclo.titulo.text())
            ctxo["talhao_detalhe"] = limpa(p_ciclo.subtitulo.text())
            ctxo["faixas"] = p_ciclo.segmentos()
        j_sug.abre(win.grab(), ctxo, p_pontos.levantador)

    def aviso_de_resposta():
        n = caixa.novidades()
        if n:
            win.avisa(f"{n} resposta(s) nova(s) nas suas sugestões — clique na lâmpada", "info", 6000)
    win.barra.abrirSugestoes.connect(abre_sugestoes)
    j_sug.enviada.connect(lambda _t: win.avisa("Sugestão enviada", "ok"))
    win.filhas = (tabs, analise, j_sug)

    # o que esta peca deixa para as outras
    ctx.abre_sugestoes = abre_sugestoes
    ctx.aviso_de_resposta = aviso_de_resposta
    ctx.caixa = caixa
    ctx.j_sug = j_sug
