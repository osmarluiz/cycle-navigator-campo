# -*- coding: utf-8 -*-
"""RECORTE NA HORA: o SAM 2.1 propoe o contorno a partir de um clique ou de uma caixa.

A camada de talhoes prontos (`sam/sam_aoi.gpkg`) foi recortada uma vez, em blocos, sem ninguem
conferir. Aqui o mesmo modelo responde a UMA pergunta -- "o que e' isto que eu apontei?" -- e
aceita correcao: mais um clique dizendo "isto tambem" ou "isto nao".

⚠️ OPCIONAL DE PONTA A PONTA. Precisa de `torch`, `sam2` e do arquivo do modelo (~900 MB) numa pasta
`modelos/` ao lado dos dados. Faltando qualquer um, `RecorteVivo.ok` e' False e o programa segue como
antes; nada aqui pode impedir a abertura.

⚠️⚠️ O MODELO VE^ O QUE ESTA' NA TELA (decisao do Osmar, 2026-11-20). Quem entrega a imagem e' um
`leitor(r0, c0, lado, n)` de fora (ver `montagem/recorte_vivo.py`): a mesma composicao e o mesmo
realce do mapa. Antes era sempre o NDVI-temporal do ano, e o modelo acertava ou errava uma borda que
a pessoa nem enxergava. Quem quiser separar vizinhos pelo calendario escolhe essa visao no mapa.

⚠️⚠️ O TAMANHO DA AREA IMPORTA MAIS QUE O MODELO (Remote SAMsing, arXiv 2605.00256). O SAM reamostra
tudo para 1024 x 1024: num bloco de 1024 px da grade (4,9 km) um talhao de 10 ha ocupa 65 px e a
borda sai grosseira; num bloco de 256 px ele ocupa 260. Por isso `lado` e' escolha de quem usa, o
bloco usado fica em `quadro` para ser desenhado no mapa, e `refina` roda uma segunda passada num
recorte justo em volta da mascara (caixa + cliques + mascara anterior como prompt, a ideia do
SAMRefiner, arXiv 2502.06756): o objeto passa a ocupar quase todo o 1024.

⚠️ A PARTE CARA E' A REGIAO, NAO O CLIQUE. Preparar um bloco custa ~0,7 s (M5, modelo grande); cada
clique dentro dele, ~10 ms. O bloco preparado fica guardado enquanto os cliques couberem nele e a
imagem da tela nao mudar (`versao`). Roda na thread da interface de proposito: menos de um segundo
nao paga o risco de mais uma thread para parar no fechamento (ver "armadilhas" no CLAUDE.md).
"""
import logging
import time
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

N = 1024                          # lado da imagem que o modelo recebe, sempre
LADOS = (256, 512, 1024, 2048)    # lado do bloco na grade, a' escolha
LADO_PADRAO = 1024
LADO_MAX = 4096                   # mascara que encosta na beirada: dobra o bloco ate' aqui
FOLGA = 1.2                       # segunda passada: recorte 20% maior que a mascara
FATOR_CAIXA = 4.0                 # bloco = caixa x isto. MEDIDO: com 1,5 o modelo erra (sem vizinhanca
                                  # nao ha' borda para ver); com 4 acerta, e a segunda passada afina
LADO_MIN_FINO = 96                # nem recorte menor que isto (ampliar 10x nao cria informacao)
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


def bloco_da_caixa(caixa):
    """Bloco quadrado centrado numa caixa (r0, c0, r1, c1), com a vizinhanca que o modelo precisa."""
    r0, c0, r1, c1 = caixa
    lado = int(max(256, round(max(r1 - r0, c1 - c0) * FATOR_CAIXA)))
    return (int(round((r0 + r1) / 2 - lado / 2)), int(round((c0 + c1) / 2 - lado / 2)), lado)


class RecorteVivo:
    def __init__(self, leitor, pastas, versao=None):
        """`leitor(r0, c0, lado, n)` -> RGB uint8 (n, n, 3) do bloco, reamostrado; `versao()` muda
        quando a imagem da tela muda (outra composicao, outro mes)."""
        self.leitor = leitor
        self.versao = versao or (lambda: 0)
        self.lado = LADO_PADRAO
        self.refina = True
        self.quadro = None            # (r0, c0, lado) do bloco da ultima resposta
        self._v_quadro = None
        self.fino = None              # idem, do recorte da segunda passada (ou None)
        self.motivo = ""
        self._modelo = acha_modelo(pastas)
        self._pred = None
        self._bloco = None            # (r0, c0, lado, versao) preparado no modelo
        self._guardados = {}          # idem -> o que o modelo calculou, dos ultimos blocos
        self.ok = False
        if self._modelo is None:
            self.motivo = "sem o arquivo do modelo (pasta modelos/)"
            return
        try:
            import sam2            # noqa: F401
            import torch           # noqa: F401
        except Exception as e:
            self.motivo = f"sem torch/sam2 ({type(e).__name__})"
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

    def _prepara(self, r0, c0, lado):
        chave = (r0, c0, lado, self.versao())
        if self._bloco == chave:
            return
        import torch
        pr = self._pred
        # ⚠️ a segunda passada prepara OUTRO bloco (o fino) por cima do primeiro: sem guardar o que
        # o modelo ja' calculou, cada correcao pagava as duas preparacoes de novo (~1,5 s)
        if self._bloco is not None:
            self._guardados[self._bloco] = (pr._features, pr._orig_hw)
            while len(self._guardados) > 3:
                self._guardados.pop(next(iter(self._guardados)))
        if chave in self._guardados:
            pr._features, pr._orig_hw = self._guardados.pop(chave)
            pr._is_image_set, pr._is_batch = True, False
            self._bloco = chave
            return
        img = self.leitor(r0, c0, lado, N)
        t0 = time.time()
        with torch.inference_mode():
            pr.set_image(np.ascontiguousarray(img))
        self._bloco = chave
        log.info("recorte: bloco (%d,%d) de %d px preparado em %.2f s", r0, c0, lado,
                 time.time() - t0)

    # ---------- pergunta ----------
    def bloco_para(self, row, col):
        """O bloco que um clique em (row, col) usaria: para mostrar a area antes de clicar."""
        return (int(row) - self.lado // 2, int(col) - self.lado // 2, self.lado)

    def contorno(self, pontos, caixa=None):
        """`pontos`: [(row, col, 1 = e' isto | 0 = isto nao)]; `caixa`: (r0, c0, r1, c1) ou None.
        Devolve (poligono shapely em pixels da grade, nota 0..1) ou (None, 0)."""
        if not self.ok or not (pontos or caixa):
            return None, 0.0
        try:
            self._carrega()
            self.fino = None
            bloco = self._bloco_inicial(pontos, caixa)
            miudo = None
            while True:
                mk, nota, logit = self._pergunta(bloco, pontos, caixa)
                self.quadro, self._v_quadro = bloco, self.versao()
                if mk is None:
                    return None, 0.0
                encosta = bool(mk[0].any() or mk[-1].any() or mk[:, 0].any() or mk[:, -1].any())
                # ⚠️ MEDIDO: com o bloco menor que o objeto (pivo de 144 ha num bloco de 512 px) o
                # modelo nao ve^ borda nenhuma e devolve uma mancha de 0,1 ha no centro, sem encostar
                # na beirada. Resposta miuda num bloco pequeno: confere tambem com o dobro.
                if (not encosta and caixa is None and miudo is None and bloco[2] < 1024
                        and mk.mean() < 0.004):
                    miudo = (mk, nota, logit, bloco)
                elif not encosta or bloco[2] * 2 > LADO_MAX:
                    break
                r0, c0, lado = bloco            # o objeto nao coube: mesma area central, o dobro
                bloco = (r0 - lado // 2, c0 - lado // 2, lado * 2)
            if miudo is not None and miudo[1] > nota + 0.05:
                mk, nota, logit, bloco = miudo  # de longe ficou pior: era mesmo coisa pequena
                self.quadro = bloco
            if self.refina:
                fino = self._bloco_fino(mk, bloco)
                if fino is not None:
                    mk2, nota2, _ = self._pergunta(fino, pontos, self._caixa_de(mk, bloco),
                                                   anterior=(logit, bloco))
                    # ⚠️ a segunda passada so' vale se confirmar a primeira: se ela trocar de
                    # objeto (IoU baixo entre as duas), fica a primeira
                    if mk2 is not None and self._concorda(mk, bloco, mk2, fino):
                        mk, nota, bloco, self.fino = mk2, nota2, fino, fino
            return self._poligono(mk, bloco, pontos), nota
        except Exception as e:
            log.warning("recorte falhou: %s: %s", type(e).__name__, e)
            self._bloco = None
            self._guardados.clear()
            return None, 0.0

    def _bloco_inicial(self, pontos, caixa):
        if caixa is not None:
            return bloco_da_caixa(caixa)
        if self.quadro is not None and self._v_quadro == self.versao():
            r0, c0, lado = self.quadro
            m = lado * 3 // 32
            if lado == self.lado and all(r0 + m <= p[0] < r0 + lado - m and
                                         c0 + m <= p[1] < c0 + lado - m for p in pontos):
                return (r0, c0, lado)           # os cliques cabem no bloco ja' preparado
        return self.bloco_para(pontos[0][0], pontos[0][1])

    def _pergunta(self, bloco, pontos, caixa, anterior=None):
        """Uma chamada ao modelo num bloco -> (mascara bool N x N, nota, logits N x N)."""
        import torch
        r0, c0, lado = bloco
        e = lado / N
        self._prepara(r0, c0, lado)
        arg = {}
        if pontos:
            arg["point_coords"] = np.array([[(p[1] + 0.5 - c0) / e, (p[0] + 0.5 - r0) / e]
                                            for p in pontos])
            arg["point_labels"] = np.array([int(p[2]) for p in pontos])
        if caixa is not None:
            arg["box"] = np.array([(caixa[1] - c0) / e, (caixa[0] - r0) / e,
                                   (caixa[3] - c0) / e, (caixa[2] - r0) / e])
        if anterior is not None:
            arg["mask_input"] = self._mascara_previa(anterior[0], anterior[1], bloco)
        # um clique so' e' ambiguo (o talhao? o pivo dentro dele?): o modelo da' 3 respostas e fica
        # a de maior nota. Com caixa, correcoes ou mascara previa ja' nao ha' ambiguidade.
        varias = caixa is None and anterior is None and len(pontos) == 1
        with torch.inference_mode():
            mascaras, notas, _ = self._pred.predict(multimask_output=varias, return_logits=True,
                                                    **arg)
        k = int(np.argmax(notas))
        logit = np.asarray(mascaras[k], np.float32)
        mk = logit > 0
        if not mk.any():
            return None, 0.0, None
        return mk, float(notas[k]), logit

    @staticmethod
    def _mascara_previa(logit, de, para):
        """Os logits da primeira passada, recortados e reamostrados para o bloco fino (1 x 256 x 256)."""
        import torch
        import torch.nn.functional as F
        e = de[2] / N
        y0 = int(round((para[0] - de[0]) / e)); x0 = int(round((para[1] - de[1]) / e))
        t = max(1, int(round(para[2] / e)))
        cheio = np.full((t, t), -12.0, np.float32)          # fora do bloco antigo: "nao e' isto"
        ya, xa = max(0, y0), max(0, x0)
        yb, xb = min(N, y0 + t), min(N, x0 + t)
        if yb > ya and xb > xa:
            cheio[ya - y0:yb - y0, xa - x0:xb - x0] = logit[ya:yb, xa:xb]
        pequeno = F.interpolate(torch.from_numpy(cheio)[None, None], size=(256, 256),
                                mode="bilinear", align_corners=False)
        return np.clip(pequeno[0].numpy(), -12, 12)

    @staticmethod
    def _limites(mk, bloco):
        """(r0, c0, r1, c1) da mascara, em pixels da grade."""
        e = bloco[2] / N
        ys, xs = np.nonzero(mk)
        return (bloco[0] + ys.min() * e, bloco[1] + xs.min() * e,
                bloco[0] + (ys.max() + 1) * e, bloco[1] + (xs.max() + 1) * e)

    _caixa_de = _limites

    def _bloco_fino(self, mk, bloco):
        """Recorte quadrado 20% maior que a mascara; None se nao ampliaria o bastante."""
        r0, c0, r1, c1 = self._limites(mk, bloco)
        lado = int(np.ceil(max(r1 - r0, c1 - c0) * FOLGA))
        lado = max(lado, LADO_MIN_FINO)
        if lado > bloco[2] * 0.7:
            return None
        return (int(round((r0 + r1) / 2 - lado / 2)), int(round((c0 + c1) / 2 - lado / 2)), lado)

    @staticmethod
    def _concorda(mk, bloco, mk2, fino, minimo=0.6):
        """IoU entre as duas passadas, medido na grade do bloco fino."""
        e1, e2 = bloco[2] / N, fino[2] / N
        ys = np.clip(((fino[0] + (np.arange(N) + 0.5) * e2 - bloco[0]) / e1).astype(int), 0, N - 1)
        xs = np.clip(((fino[1] + (np.arange(N) + 0.5) * e2 - bloco[1]) / e1).astype(int), 0, N - 1)
        a = mk[np.ix_(ys, xs)]
        uniao = (a | mk2).sum()
        # a parte da primeira mascara que ficou fora do recorte fino conta contra
        fora = mk.sum() * e1 * e1 - a.sum() * e2 * e2
        return bool(uniao > 0 and (a & mk2).sum() / (uniao + max(0.0, fora) / (e2 * e2)) >= minimo)

    @staticmethod
    def _poligono(mk, bloco, pontos):
        from rasterio import features
        from shapely import affinity
        from shapely.geometry import Point, Polygon, shape
        r0, c0, lado = bloco
        e = lado / N
        partes = [shape(g) for g, v in features.shapes(mk.astype(np.uint8), mask=mk) if v == 1]
        dentro = []
        if pontos:
            alvo = Point((pontos[0][1] + 0.5 - c0) / e, (pontos[0][0] + 0.5 - r0) / e)
            dentro = [p for p in partes if p.contains(alvo)]
        p = max(dentro or partes, key=lambda q: q.area)
        # so' o contorno de fora (buraco de arvore no meio do talhao nao e' divisa), levado para a
        # grade e alisado de leve: a mascara vem em degraus
        p = affinity.translate(affinity.scale(Polygon(p.exterior), e, e, origin=(0, 0)), c0, r0)
        p = p.simplify(0.6)
        if p.is_empty or p.area < 4:
            return None
        return p
