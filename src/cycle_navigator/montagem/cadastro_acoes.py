# -*- coding: utf-8 -*-
"""MONTAGEM · cadastro_acoes: exportar, preencher e excluir fazendas.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QMessageBox
from .. import exporta
from ..fazendas import DialogoFazenda


def instala(ctx):
    cadastro = ctx.cadastro
    cam_faz = ctx.cam_faz
    cfg = ctx.cfg
    estado = ctx.estado
    p_pontos = ctx.p_pontos
    tabs = ctx.tabs
    win = ctx.win

    def poligono_do_ponto(pt):
        """O talhao que deu a curva deste ponto, em coordenadas do mapa (UTM): o contorno recortado
        na hora, ou o talhao pronto. Ponto de um pixel so' nao tem poligono."""
        from shapely.affinity import affine_transform
        from shapely.geometry import Polygon
        poli = None
        if pt.get("contorno") and len(pt["contorno"]) >= 3:
            poli = Polygon(pt["contorno"])
        elif pt.get("fonte_curva") == "talhao" and ctx.cam_sam is not None:
            i = ctx.cam_sam.em_idx(pt["row"], pt["col"])
            if i is not None:
                poli = ctx.cam_sam.polys[i]
        if poli is None:
            return None
        t = ctx.classe.transform               # pixel (coluna, linha) -> metros
        return affine_transform(poli, [t.a, t.b, t.d, t.e, t.c, t.f])

    def exporta_camada(qual):
        sug = str(cfg.pasta_pontos / (f"{qual}.gpkg" if qual == "fazendas"
                                      else f"pontos_{estado['safra'].replace('/', '_')}.gpkg"))
        dest, _ = QFileDialog.getSaveFileName(
            tabs, f"Exportar {qual}", sug,
            "GeoPackage (*.gpkg);;Shapefile (*.shp);;CSV (*.csv)")
        if not dest:
            return
        try:
            if dest.lower().endswith(".csv"):
                if qual != "pontos":
                    raise RuntimeError("CSV so' para os pontos; fazendas tem geometria")
                p_pontos.exporta_para(dest)
                n = sum(len(x.get("ciclos") or []) for x in p_pontos.store.points)
            elif qual == "fazendas":
                n, dest = exporta.fazendas(cadastro, dest)
            else:
                n, dest = exporta.pontos(p_pontos.store, dest, poligono_de=poligono_do_ponto)
        except Exception as e:
            QMessageBox.warning(tabs, "Exportar", str(e))
            return
        QMessageBox.information(tabs, "Exportar", f"{n} feição(ões) em\n{dest}")

    def _qual(fid):
        """⚠️ Botao da tabela sem linha escolhida nao fazia nada, calado. Com uma fazenda so' nao ha'
        duvida de qual e'; com varias, pede a linha."""
        if fid is None and len(cadastro.fazendas) == 1:
            fid = cadastro.fazendas[0]["id"]
        if fid is None:
            QMessageBox.information(tabs, "Fazendas", "Clique primeiro na linha da fazenda.")
        return fid

    def preenche(fid):
        fid = _qual(fid)
        f = cadastro.por_id(fid) if fid is not None else None
        if f is None:
            return
        dlg = DialogoFazenda(f, win)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cadastro.salva(fid, None, dlg.dados())
            cam_faz.redesenha()
            tabs.fazendas.lista(cadastro, selecionar=fid)

    def exclui(fid):
        fid = _qual(fid)
        if fid is None:
            return
        if cam_faz.oculto == fid:               # e' a que esta' com o contorno aberto para redesenho
            ctx.usa_modo("identificar")
        f = cadastro.por_id(fid)
        if QMessageBox.question(tabs, "Excluir",
                                f"Excluir a fazenda '{(f or {}).get('nome') or fid}'?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        cadastro.remove(fid)
        cam_faz.redesenha()
        tabs.fazendas.lista(cadastro)

    # o que esta peca deixa para as outras
    ctx.exclui = exclui
    ctx.exporta_camada = exporta_camada
    ctx.preenche = preenche
    ctx.qual_fazenda = _qual
