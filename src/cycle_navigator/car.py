# -*- coding: utf-8 -*-
"""O CAR COMO REFERENCIA: os perimetros dos imoveis rurais, prontos para serem adotados.

A base publica do CAR (SICAR) entrega o contorno de cada imovel, o codigo, o municipio e a area
declarada -- e NAO entrega nome de proprietario nem contato. Entao o CAR substitui o DESENHO da
fazenda (o contorno ja' vem feito; o aluno adota e ajusta), nao a conversa: "de quem e'" continua
sendo preenchido no cadastro, com o produtor.

⚠️⚠️ FERRAMENTA DE CONTORNO, NAO CAMADA PERMANENTE. Os perimetros so' aparecem enquanto se esta'
desenhando uma fazenda -- e' quando a pessoa precisa ver onde clicar para partir de um imovel pronto.
No resto do tempo somem: por cima do mapa o tempo todo eles so' atrapalham a leitura dos talhoes.

⚠️ SO' O QUE ESTA' NA VISTA, COM ORCAMENTO DE VERTICES. Sao dezenas de milhares de poligonos.
A camada consulta a arvore espacial pelo retangulo da vista e desenha se o total de vertices couber
num orcamento; se nao couber, avisa (`escondida`) em vez de travar o mapa ou virar uma mancha.

⚠️ IMOVEIS SE SOBREPOEM. O CAR e' autodeclarado: um mesmo pedaco de terra pode ter dois ou tres
cadastros. No clique, quando ha' mais de um, vale o MENOR -- e' o mais provavel de ser o talhao que
a pessoa esta' apontando, e o maior (a fazenda-mae) continua la' para ser adotado de proposito.

⚠️ OPCIONAL DE PONTA A PONTA. Depende de geopandas/shapely (o extra `pivots`) e de um arquivo que
pode nao existir no computador de campo. Sem qualquer um dos dois a camada simplesmente nao aparece,
com um aviso no log -- nunca um erro que impeca a ferramenta de abrir.
"""
import logging

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPolygonF
from PyQt6.QtWidgets import QGraphicsPolygonItem, QLabel

log = logging.getLogger(__name__)

VERTICES_MAX = 400_000     # acima disto a vista tem poligonos demais para desenhar sem travar
LOD_TOL_PX = 12            # tolerancia da versao simplificada (~57 m): vale para a escala larga
COR = "#e0b84a"


class CamadaCAR:
    """Camada de poligonos de referencia. Nasceu para o CAR; o SAM usa a mesma classe com outra
    cor, outro cartao e outros campos herdados pela fazenda (`html` e `dados`)."""

    def __init__(self, view, caminho, transform, crs, cor=None, cor_sel="#ffd166",
                 titulo="Imóvel do CAR", html=None, dados=None):
        self.view = view
        self.cor = cor or COR
        self.titulo = titulo
        self._html_fn = html            # (atributos, area_medida) -> html; None = cartao do CAR
        self.dados = dados or dados_do_car   # atributos -> campos que a fazenda guarda
        self.ok = False
        self.n = 0
        self._visivel = False
        self.escondida = False     # True quando nem a versao simplificada cabe no orcamento
        self.simplificada = False  # True quando a vista esta' usando o nivel de detalhe reduzido
        self.em_vista = 0
        self._linha = pg.PlotDataItem(pen=pg.mkPen(self.cor, width=1.4,
                                                style=pg.QtCore.Qt.PenStyle.DashLine))
        self._linha.setZValue(12)
        view.vb.addItem(self._linha)
        # ⚠️ SELECAO = contorno grosso + preenchimento + cartao. Inspecionar um imovel nao pode exigir
        # mudar de modo nem adota-lo: a pessoa so' quer saber o que o CAR diz daquele pedaco.
        self._sel = QGraphicsPolygonItem()
        self._sel.setPen(pg.mkPen(cor_sel, width=3))
        c = pg.mkColor(cor_sel); c.setAlpha(55)
        self._sel.setBrush(pg.mkBrush(c))
        self._sel.setZValue(14)
        self._sel.hide()
        view.vb.addItem(self._sel)
        self.selecionado = None
        self.card = QLabel(view)
        self.card.setObjectName("card")
        self.card.setWordWrap(True)
        self.card.setMaximumWidth(380)
        self.card.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.card.move(16, 16)
        self.card.hide()
        self.px_ha = abs(transform.a * transform.e) / 1e4 if transform is not None else None
        try:
            self._carrega(caminho, transform, crs)
        except Exception as e:
            log.warning("camada CAR indisponivel (%s): %s", type(e).__name__, e)

    def _carrega(self, caminho, transform, crs):
        import geopandas as gpd
        from shapely import STRtree
        from shapely.geometry import Polygon

        gdf = gpd.read_file(str(caminho))
        if crs is not None and gdf.crs is not None and str(gdf.crs) != str(crs):
            gdf = gdf.to_crs(crs)
        inv = ~transform
        self.polys = []            # shapely em PIXEL (col, row)
        self.aneis = []            # (cols, rows) do anel externo, para desenhar e adotar
        # ⚠️ NIVEL DE DETALHE. Na escala do AOI inteiro sao ~1 milhao de vertices; a primeira versao
        # simplesmente ESCONDIA a camada e avisava na barra -- e o aviso ficava cortado, e quem
        # abria o modo Desenhar nao via nada. Uma copia simplificada (tolerancia LOD_TOL_PX) cabe no
        # orcamento em qualquer zoom; de perto, desenha-se a completa.
        self.aneis_lod = []
        self.attr = []
        cols_attr = [c for c in gdf.columns if c != "geometry"]
        for row in gdf.itertuples(index=False):
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            partes = geom.geoms if geom.geom_type.startswith("Multi") else [geom]
            d = {c: getattr(row, c) for c in cols_attr}
            for p in partes:
                ext = getattr(p, "exterior", None)
                if ext is None:
                    continue
                xs, ys = np.asarray(ext.coords.xy[0]), np.asarray(ext.coords.xy[1])
                c, r = inv * (xs, ys)
                c = np.asarray(c); r = np.asarray(r)
                self.aneis.append((c, r))
                poly = Polygon(zip(c, r))
                self.polys.append(poly)
                lod = poly.simplify(LOD_TOL_PX, preserve_topology=False)
                if lod.geom_type == "Polygon" and not lod.is_empty and len(lod.exterior.coords) >= 4:
                    lc, lr = lod.exterior.coords.xy
                    self.aneis_lod.append((np.asarray(lc), np.asarray(lr)))
                else:                      # simplificacao degenerou: decima os vertices
                    self.aneis_lod.append((c[::4], r[::4]))
                self.attr.append(d)
        self.tree = STRtree(self.polys)
        self.n = len(self.polys)
        self.ok = self.n > 0
        log.info("%s: %d poligonos carregados de %s", self.titulo, self.n, caminho)

    # ---------- desenho ----------
    def visivel(self, on):
        self._visivel = bool(on)
        if not self._visivel:
            self.limpa_selecao()
        self.redesenha()

    # ---------- selecao ----------
    def seleciona(self, i):
        """Destaca o imovel i e mostra o cartao com o que o CAR sabe dele."""
        if not self.ok or not (0 <= i < self.n):
            return
        c, r = self.aneis[i]
        self._sel.setPolygon(QPolygonF([QPointF(float(x), float(y)) for x, y in zip(c, r)]))
        self._sel.show()
        self.selecionado = i
        self.card.setText(self._html(self.attr[i], self.polys[i].area * self.px_ha
                                     if self.px_ha else None))
        self.card.adjustSize()
        self.card.show()
        self.card.raise_()

    def limpa_selecao(self):
        self._sel.hide()
        self.card.hide()
        self.selecionado = None

    def _html(self, a, area_medida):
        if self._html_fn is not None:
            return self._html_fn(a, area_medida)
        d = dados_do_car(a)
        linhas = [f"<div style='font-size:13px;font-weight:600;margin-bottom:4px'>{self.titulo}</div>",
                  f"<div style='color:#a9ac9c;font-size:11px;margin-bottom:6px'>{d['car']}</div>"]

        def row(k, v):
            linhas.append(f"<div><span style='color:#a9ac9c'>{k}</span>&nbsp; {v}</div>")

        row("Município", d["car_municipio"] or "—")
        decl = d["car_area_ha"]
        if decl is not None and area_medida is not None:
            dif = (area_medida - decl) / decl * 100 if decl else 0
            aviso = f" <span style='color:#e8a33d'>({dif:+.0f}%)</span>" if abs(dif) > 15 else ""
            row("Área", f"declarada <b>{decl:,.1f}</b> ha · medida <b>{area_medida:,.1f}</b> ha{aviso}"
                .replace(",", "."))
        elif decl is not None:
            row("Área declarada", f"<b>{decl:,.1f}</b> ha".replace(",", "."))
        if d["car_mod_fiscal"] is not None:
            mf = d["car_mod_fiscal"]
            classe = "pequena (≤4 MF)" if mf <= 4 else "média (4–15 MF)" if mf <= 15 else "grande (>15 MF)"
            row("Módulos fiscais", f"<b>{mf:,.2f}</b> · {classe}".replace(",", "."))
        row("Situação", d["car_status"] or "—")
        row("Tipo", d["car_tipo"] or "—")
        if d["car_condicao"]:
            row("Condição", d["car_condicao"])
        if d["car_atualizado"]:
            row("Atualizado", d["car_atualizado"])
        linhas.append("<div style='color:#767a6c;font-size:11px;margin-top:6px'>Editar fazenda → "
                      "clique nele para adotar · Esc limpa</div>")
        return "".join(linhas)

    def redesenha(self, *_):
        self.escondida = False
        self.em_vista = 0
        if not (self.ok and self._visivel):
            self._linha.clear()
            return
        r = self.view.vb.viewRect()
        from shapely.geometry import box
        idx = self.tree.query(box(r.x(), r.y(), r.x() + r.width(), r.y() + r.height()))
        self.em_vista = len(idx)
        if len(idx) == 0:
            self._linha.clear()
            return
        fonte = self.aneis
        self.simplificada = False
        if sum(len(fonte[i][0]) for i in idx) > VERTICES_MAX:
            fonte = self.aneis_lod
            self.simplificada = True
            if sum(len(fonte[i][0]) for i in idx) > VERTICES_MAX:
                self.escondida = True          # nem a simplificada cabe: so' em vistas absurdas
                self._linha.clear()
                return
        nan = np.array([np.nan])
        xs, ys = [], []
        for i in idx:
            c, rr = fonte[i]
            xs += [c, nan]; ys += [rr, nan]
        self._linha.setData(np.concatenate(xs), np.concatenate(ys))

    # ---------- consulta ----------
    def em_idx(self, row, col):
        """Indice do imovel sob o pixel (o MENOR, se houver varios), ou None."""
        if not self.ok:
            return None
        from shapely.geometry import Point
        # ⚠️ "within", nao "contains": no shapely 2 o predicado e' predicado(entrada, arvore).
        # Com "contains" a pergunta vira "o ponto contem o poligono?" -- sempre falso, em silencio.
        idx = self.tree.query(Point(col, row), predicate="within")
        if len(idx) == 0:
            return None
        return int(min(idx, key=lambda k: self.polys[k].area))

    def em(self, row, col):
        """O imovel sob o pixel: (atributos, anel_em_pixel) ou (None, None)."""
        i = self.em_idx(row, col)
        if i is None:
            return None, None
        return self.attr[i], self.aneis[i]


CAMPOS = [("car", "CAR"), ("car_municipio", "Município (CAR)"),
          ("car_area_ha", "Área declarada (ha)"), ("car_mod_fiscal", "Módulos fiscais"),
          ("car_status", "Situação"), ("car_tipo", "Tipo"), ("car_condicao", "Condição"),
          ("car_atualizado", "Atualizado em")]
STATUS = {"AT": "ativo", "PE": "pendente", "CA": "cancelado", "SU": "suspenso"}
TIPO = {"IRU": "imóvel rural", "AST": "assentamento", "PCT": "povos e comunidades tradicionais"}


def dados_do_car(a):
    """Os atributos publicos do imovel, nos nomes que a fazenda guarda. Nada de dono/contato: a
    base publica nao tem; isso continua vindo da conversa."""
    if not a:
        return {}

    def num(v):
        try:
            return round(float(v), 2)
        except (TypeError, ValueError):
            return None

    return {"car": str(a.get("cod_imovel") or ""),
            "car_municipio": str(a.get("municipio") or ""),
            "car_area_ha": num(a.get("num_area")),
            "car_mod_fiscal": num(a.get("mod_fiscal")),
            "car_status": STATUS.get(a.get("ind_status"), str(a.get("ind_status") or "")),
            "car_tipo": TIPO.get(a.get("ind_tipo"), str(a.get("ind_tipo") or "")),
            "car_condicao": str(a.get("des_condic") or ""),
            "car_atualizado": str(a.get("dat_atuali") or "")[:10]}


def resumo(a):
    """Texto curto para a barra: codigo, municipio, area declarada."""
    if not a:
        return ""
    partes = [str(a.get("cod_imovel", ""))]
    if a.get("municipio"):
        partes.append(str(a["municipio"]))
    if a.get("num_area") is not None:
        try:
            partes.append(f"{float(a['num_area']):,.0f} ha".replace(",", "."))
        except (TypeError, ValueError):
            pass
    return " · ".join(p for p in partes if p)


# ==================================================================== SAM
COR_SAM = "#7fd3ff"


def dados_do_sam(a):
    """O que a fazenda guarda quando o contorno veio do SAM: o id do talhao e a confianca do modelo."""
    if not a:
        return {}
    return {"sam_id": int(a.get("id") or 0),
            "sam_iou": round(float(a.get("iou") or 0), 3),
            "sam_estab": round(float(a.get("estab") or 0), 3)}


def html_sam(a, area_medida):
    d = dados_do_sam(a)
    area = f"{(area_medida or float(a.get('area_ha') or 0)):,.1f}".replace(",", ".")
    return ("<div style='font-size:13px;font-weight:600;margin-bottom:4px'>Talhão (SAM)</div>"
            f"<div style='color:#a9ac9c;font-size:11px;margin-bottom:6px'>segmento #{d['sam_id']}</div>"
            f"<div><span style='color:#a9ac9c'>Área</span>&nbsp; <b>{area}</b> ha</div>"
            f"<div><span style='color:#a9ac9c'>Confiança do modelo</span>&nbsp; IoU {d['sam_iou']:.2f} · "
            f"estabilidade {d['sam_estab']:.2f}</div>"
            "<div style='color:#767a6c;font-size:11px;margin-top:6px'>contorno automático: confira as "
            "bordas antes de adotar · Editar fazenda → clique nele · Esc limpa</div>")
