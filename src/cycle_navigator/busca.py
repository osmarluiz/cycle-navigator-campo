# -*- coding: utf-8 -*-
"""IR ATE' UM LUGAR: municipio, codigo do CAR, nome de fazenda ou coordenada.

O recorte tem 137 x 145 km. Achar a fazenda do produtor arrastando o mapa custava minutos de cada
visita; quem esta' em campo sabe o MUNICIPIO, tem o codigo do CAR no papel, ou tem a coordenada no
celular. Qualquer um dos tres leva la'.

⚠️ SEM ACENTO E SEM CAIXA. "brasilia", "Brasília" e "BRASILIA" sao a mesma busca; o CAR grava os
municipios sem padrao nenhum.

⚠️ COORDENADA NA ORDEM QUE VIER. O celular entrega "lat, lon"; planilha as vezes traz "lon, lat".
Quem chama testa as duas ordens e fica com a que cai dentro do recorte (ver `app.py`).
"""
import re
import unicodedata


def normaliza(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


_NUM = r"-?\d+(?:[.,]\d+)?"
_GMS = re.compile(rf"({_NUM})\s*[°º]\s*(?:({_NUM})\s*['’′]\s*)?(?:({_NUM})\s*(?:\"|”|″|'')\s*)?\s*([NSEWOL])?",
                  re.I)


def _f(n):
    return float(n.replace(",", "."))


def _utm_23s(x, y):
    """⚠️ UTM sem zona escrita: vale a das imagens (23 Sul, EPSG:32723)."""
    try:
        from pyproj import Transformer
        lon, lat = Transformer.from_crs(32723, 4326, always_xy=True).transform(x, y)
        return lat, lon
    except Exception:
        return None


def coordenada(txt):
    """O que as pessoas colam: '-15.79, -47.88' | '-15,79 -47,88' | '15.79S 47.88W' |
    15°47'38"S 47°52'58"W | '15 47 38 S 47 52 58 W' | 'lat -15.79 lon -47.88' | UTM '219578 8178548'.
    -> (a, b) em graus (a ordem lat/lon quem resolve e' quem usa), ou None."""
    t = re.sub(r"(?i)\b(latitude|longitude|lat|long|lon|lng)\b\.?\s*[:=]?", " ", str(txt or "")).strip()
    if not t or re.search(r"[A-Za-z]{2,}", t):
        return None
    sinal = lambda letra: -1 if (letra or "").upper() in ("S", "W", "O") else 1
    gms = _GMS.findall(t)
    if len(gms) == 2:
        out = []
        for g, m, s, h in gms:
            v = abs(_f(g)) + (_f(m) / 60 if m else 0) + (_f(s) / 3600 if s else 0)
            out.append(v * (-1 if g.startswith("-") else sinal(h)))
        return tuple(out) if all(abs(v) <= 180 for v in out) else None
    letras = re.findall(r"(?<![A-Za-z])[NSEWOLnsewol](?![A-Za-z])", t)
    # ⚠️ a virgula tanto separa ("-15,-47") quanto e' decimal ("-15,79"): tenta o numero inteiro
    # com decimal, depois so' os decimais, depois so' os inteiros -- fica a primeira leitura com 2
    for padrao in (_NUM, r"-?\d+[.,]\d+", r"-?\d+"):
        nums = [_f(n) for n in re.findall(padrao, t)]
        if len(nums) in (4, 6) and len(letras) == 2:          # graus minutos (segundos) sem simbolo
            k = len(nums) // 2
            nums = [abs(p[0]) + p[1] / 60 + (p[2] / 3600 if k == 3 else 0)
                    for p in (nums[:k], nums[k:])]
        if len(nums) == 2:
            a, b = nums
            if len(letras) == 2:
                a, b = abs(a) * sinal(letras[0]), abs(b) * sinal(letras[1])
            if abs(a) <= 180 and abs(b) <= 180:
                return a, b
            x, y = sorted((abs(a), abs(b)))
            if 1e5 <= x <= 9e5 and 1e6 <= y <= 1e7:           # metros: UTM
                return _utm_23s(x, y)
            return None
    return None


class Indice:
    """O que da' para procurar: municipios e codigos do CAR, nomes e donos das fazendas."""

    def __init__(self, cam_car=None, cadastro=None):
        self.cam_car = cam_car
        self.cadastro = cadastro
        self.municipios = {}        # normalizado -> (nome, [indices])
        self.codigos = {}           # normalizado -> indice
        if cam_car is not None:
            for i, a in enumerate(cam_car.attr):
                m = str(a.get("municipio") or "").strip()
                if m:
                    self.municipios.setdefault(normaliza(m), (m.title(), []))[1].append(i)
                c = str(a.get("cod_imovel") or "").strip()
                if c:
                    self.codigos[normaliza(c)] = i

    def sugestoes(self):
        nomes = sorted(n for n, _ in self.municipios.values())
        if self.cadastro is not None:
            for f in self.cadastro.fazendas:
                for k in ("nome", "proprietario"):
                    if f.get(k):
                        nomes.append(str(f[k]))
        return sorted(set(nomes), key=normaliza)

    def procura(self, txt):
        """-> ("coord", a, b) | ("fazenda", id) | ("municipio", nome, indices) | ("car", i) | None"""
        c = coordenada(txt)
        if c:
            return ("coord",) + c
        q = normaliza(txt)
        if not q:
            return None
        if self.cadastro is not None:
            for exato in (True, False):
                for f in self.cadastro.fazendas:
                    for k in ("nome", "proprietario"):
                        v = normaliza(f.get(k))
                        if v and (v == q if exato else q in v):
                            return ("fazenda", f["id"])
        if q in self.municipios:
            return ("municipio",) + self.municipios[q]
        if q in self.codigos:
            return ("car", self.codigos[q])
        for k, v in self.municipios.items():
            if q in k:
                return ("municipio",) + v
        if len(q) >= 6:                       # pedaco do codigo do CAR (os ultimos digitos do papel)
            for k, i in self.codigos.items():
                if q in k:
                    return ("car", i)
        return None
