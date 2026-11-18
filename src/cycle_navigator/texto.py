# -*- coding: utf-8 -*-
"""Como o programa escreve numero e data para gente ler: em portugues, sem "(s)" nem ISO.

⚠️ "8 talhão(ões)" e "2026-11-18T18:21:27" sao texto de programador. Custam pouco para quem escreve
e passam, para quem le^, a impressao de coisa inacabada -- na frente do produtor.
"""


def plural(n, um, varios):
    """plural(1, "ponto", "pontos") -> "1 ponto"; plural(8, ...) -> "8 pontos"."""
    return f"{n} {um if n == 1 else varios}"


def data_br(iso, hora=True):
    """'2026-11-18T18:21:27' -> '18/11/2026 18:21'. O que nao for data ISO volta como veio."""
    s = str(iso or "")
    if len(s) < 10 or s[4] != "-" or s[7] != "-":
        return s
    dia = f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return f"{dia} {s[11:16]}" if hora and len(s) >= 16 else dia
