# -*- coding: utf-8 -*-
"""RECORTE NA HORA: o SAM 2.1 propoe o contorno do talhao a partir do clique.

A camada de talhoes prontos (`sam/sam_aoi.gpkg`) foi recortada uma vez, em blocos, sem ninguem
conferir: ha' talhao cortado na emenda dos blocos, talhao pequeno engolido pelo vizinho, lugar sem
talhao nenhum. Aqui o mesmo modelo responde a UMA pergunta -- "o que e' isto que eu cliquei?" -- e
aceita correcao: mais um clique dizendo "isto tambem" ou "isto nao".

⚠️ OPCIONAL DE PONTA A PONTA. Precisa de `torch`, `sam2` e do arquivo do modelo (~900 MB) numa pasta
`modelos/` ao lado dos dados. Faltando qualquer um, `RecorteVivo.ok` e' False e o programa segue como
antes; nada aqui pode impedir a abertura.

⚠️ MESMA IMAGEM DA CAMADA PRONTA: o composto NDVI-temporal do ano, onde cada talhao tem a cor do seu
calendario. Na imagem de um mes so', dois talhoes vizinhos com a mesma cultura viram um.

⚠️ A PARTE CARA E' A REGIAO, NAO O CLIQUE. Preparar um bloco de 1024 px custa ~0,7 s (M5, modelo
grande); cada clique dentro dele, ~10 ms. Por isso o bloco preparado fica guardado enquanto os cliques
couberem nele. Roda na thread da interface de proposito: menos de um segundo nao paga o risco de mais
uma thread para parar no fechamento (ver "armadilhas" no CLAUDE.md).
"""
import logging
import time
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

N = 1024                 # lado do bloco que o modelo ve^
MARGEM = 96              # clique mais perto da beirada que isto: prepara outro bloco
ESCALAS = (1, 2, 4)      # talhao que encosta na beirada do bloco: tenta de novo mais afastado
MODELOS = (("sam2.1_hiera_large.pt", "configs/sam2.1/sam2.1_hiera_l.yaml"),
           ("sam2.1_hiera_base_plus.pt", "configs/sam2.1/sam2.1_hiera_b+.yaml"),
           ("sam2.1_hiera_small.pt", "configs/sam2.1/sam2.1_hiera_s.yaml"),
           ("sam2.1_hiera_tiny.pt", "configs/sam2.1/sam2.1_hiera_t.yaml"))


def acha_modelo(pastas):
    """(arquivo, config) do melhor modelo presente, ou None."""
    for pasta in pastas:
        for nome, cfg in MODELOS:
            p = Path(pasta) / nome
            if p.exists():
                return p, cfg
    return None


class RecorteVivo:
    def __init__(self, imagem, pastas, forma=None):
        """`imagem`: GeoTIFF RGB uint8 na grade de referencia; `forma`: (linhas, colunas) dela."""
        self.imagem = Path(imagem)
        self.motivo = ""
        self._modelo = acha_modelo(pastas)
        self._pred = None
        self._ds = None
        self._bloco = None            # (escala, r0, c0) do bloco preparado
        self.ok = False
        if self._modelo is None:
            self.motivo = "sem o arquivo do modelo (pasta modelos/)"
            return
        if not self.imagem.exists():
            self.motivo = f"sem {self.imagem.name}"
            return
        try:
            import sam2            # noqa: F401
            import torch           # noqa: F401
        except Exception as e:
            self.motivo = f"sem torch/sam2 ({type(e).__name__})"
            return
        try:
            import rasterio
            self._ds = rasterio.open(self.imagem)
            if forma is not None and (self._ds.height, self._ds.width) != tuple(forma):
                self.motivo = "a imagem do recorte nao esta' na grade de referencia"
                return
        except Exception as e:
            self.motivo = f"{self.imagem.name} nao abriu ({e})"
            return
        self.ok = True

    # ---------- modelo ----------
    def _carrega(self):
        if self._pred is not None:
            return
        import os
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        disp = ("mps" if torch.backends.mps.is_available() else
                "cuda" if torch.cuda.is_available() else "cpu")
        t0 = time.time()
        arq, cfg = self._modelo
        self._pred = SAM2ImagePredictor(build_sam2(cfg, str(arq), device=disp))
        log.info("recorte: %s em %s, carregado em %.1f s", arq.name, disp, time.time() - t0)

    def _prepara(self, escala, r0, c0):
        if self._bloco == (escala, r0, c0):
            return
        import torch
        from rasterio.windows import Window
        lado = N * escala
        img = self._ds.read([1, 2, 3], window=Window(c0, r0, lado, lado), boundless=True,
                            out_shape=(3, N, N))
        t0 = time.time()
        with torch.inference_mode():
            self._pred.set_image(np.ascontiguousarray(np.transpose(img, (1, 2, 0))))
        self._bloco = (escala, r0, c0)
        log.info("recorte: bloco (%d,%d) x%d preparado em %.2f s", r0, c0, escala, time.time() - t0)

    # ---------- pergunta ----------
    def contorno(self, pontos):
        """`pontos`: [(row, col, 1 = e' isto | 0 = isto nao)], o primeiro e' o clique que abriu.
        Devolve (poligono shapely em pixels da grade, nota 0..1) ou (None, 0)."""
        if not self.ok or not pontos:
            return None, 0.0
        try:
            self._carrega()
            for escala in ESCALAS:
                poli, nota, encosta = self._tenta(pontos, escala)
                if poli is None or not encosta:
                    return poli, nota
            return poli, nota
        except Exception as e:
            log.warning("recorte falhou: %s: %s", type(e).__name__, e)
            self._bloco = None
            return None, 0.0

    def _tenta(self, pontos, escala):
        import torch
        from rasterio import features
        from shapely.geometry import Point, Polygon, shape
        lado = N * escala
        rs = [p[0] for p in pontos]; cs = [p[1] for p in pontos]
        cabe = False
        if self._bloco is not None and self._bloco[0] == escala:
            _, r0, c0 = self._bloco
            m = MARGEM * escala
            cabe = all(r0 + m <= r < r0 + lado - m and c0 + m <= c < c0 + lado - m
                       for r, c in zip(rs, cs))
        if not cabe:
            r0 = int(pontos[0][0]) - lado // 2
            c0 = int(pontos[0][1]) - lado // 2
        self._prepara(escala, r0, c0)
        xy = np.array([[(c + 0.5 - c0) / escala, (r + 0.5 - r0) / escala] for r, c in zip(rs, cs)])
        rot = np.array([int(p[2]) for p in pontos])
        with torch.inference_mode():
            # um clique so' e' ambiguo (o talhao? o pivo dentro dele?): o modelo da' 3 respostas e
            # fica a de maior nota. Com correcoes ja' nao ha' ambiguidade: uma resposta.
            mascaras, notas, _ = self._pred.predict(point_coords=xy, point_labels=rot,
                                                    multimask_output=len(pontos) == 1)
        k = int(np.argmax(notas))
        mk = mascaras[k].astype(bool)
        if not mk.any():
            return None, 0.0, False
        encosta = bool(mk[0].any() or mk[-1].any() or mk[:, 0].any() or mk[:, -1].any())
        partes = [shape(g) for g, v in features.shapes(mk.astype(np.uint8), mask=mk) if v == 1]
        alvo = Point(xy[0])
        dentro = [p for p in partes if p.contains(alvo)]
        p = max(dentro or partes, key=lambda q: q.area)
        # so' o contorno de fora (buraco de arvore no meio do talhao nao e' divisa), alisado de leve:
        # a mascara vem em degraus de pixel
        p = Polygon(p.exterior).simplify(0.8)
        from shapely import affinity
        p = affinity.translate(affinity.scale(p, escala, escala, origin=(0, 0)), c0, r0)
        if p.is_empty or p.area < 4:
            return None, 0.0, False
        return p, float(notas[k]), encosta
