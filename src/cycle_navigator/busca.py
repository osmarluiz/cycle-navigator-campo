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


def coordenada(txt):
    """'-15.79, -47.88' | '-15,79 -47,88' | '-15 -47' -> (a, b) em graus, ou None."""
    t = str(txt or "").strip()
    if not t or re.search(r"[A-Za-z]{2,}", t):
        return None
    for padrao in (r"-?\d+[.,]\d+", r"-?\d+"):
        nums = re.findall(padrao, t)
        if len(nums) == 2:
            a, b = (float(n.replace(",", ".")) for n in nums)
            if abs(a) <= 180 and abs(b) <= 180:
                return a, b
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
