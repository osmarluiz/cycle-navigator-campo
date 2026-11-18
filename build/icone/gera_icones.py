# -*- coding: utf-8 -*-
"""Gera os icones do Cycle Navigator a partir de icone.svg (a unica fonte).

    python build/icone/gera_icones.py

Escreve, ao lado deste arquivo:
    icone.icns         Mac (o .app); so' quando ha' `iconutil`, isto e', rodando num Mac
    icone.ico          Windows (o .exe): 16..256 px num arquivo so'
    previa.png         folha de conferencia: o icone de 512 a 16 px, lado a lado
e, dentro do pacote, src/cycle_navigator/_icones/app.png (256 px): o icone da janela e do Dock
quando se roda a partir do codigo (setWindowIcon em app.py).

⚠️ OS GERADOS VAO PARA O GIT. O build (local ou no Actions) so' le .icns/.ico prontos; assim ele nao
depende de renderizar SVG nem de `iconutil`, que so' existe no Mac. Mudou o SVG, rode este script
e commite os gerados junto.
"""
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

AQUI = pathlib.Path(__file__).resolve().parent
SVG = AQUI / "icone.svg"
PNG_JANELA = AQUI.parents[1] / "src" / "cycle_navigator" / "_icones" / "app.png"


def renderiza(r: QSvgRenderer, lado: int) -> QImage:
    img = QImage(lado, lado, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    r.render(p, QRectF(0, 0, lado, lado))
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def escreve_ico(r: QSvgRenderer, destino: pathlib.Path):
    # ⚠️ ICO com PNG dentro (aceito desde o Vista). O plugin de ICO do Qt grava um tamanho so';
    # o Explorer precisa de varios, senao escala um 256 para 16 px e o icone vira borrao.
    lados = [16, 24, 32, 48, 64, 128, 256]
    blobs = [png_bytes(renderiza(r, n)) for n in lados]
    cab = struct.pack("<HHH", 0, 1, len(lados))
    offset = 6 + 16 * len(lados)
    entradas = b""
    for n, b in zip(lados, blobs):
        entradas += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(b), offset)
        offset += len(b)
    destino.write_bytes(cab + entradas + b"".join(blobs))


def escreve_icns(r: QSvgRenderer, destino: pathlib.Path) -> bool:
    if not shutil.which("iconutil"):
        print("sem iconutil (nao e' Mac): icone.icns mantido como esta'")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        iconset = pathlib.Path(tmp) / "icone.iconset"
        iconset.mkdir()
        for n in (16, 32, 128, 256, 512):
            renderiza(r, n).save(str(iconset / f"icon_{n}x{n}.png"))
            renderiza(r, 2 * n).save(str(iconset / f"icon_{n}x{n}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(destino)], check=True)
    return True


def escreve_previa(r: QSvgRenderer, destino: pathlib.Path):
    # cada tamanho desenhado no tamanho real, sobre fundo claro e escuro: e' o que o Dock e a
    # barra de tarefas mostram. O de 16 px e' o que decide se o desenho funciona.
    lados = [512, 256, 128, 64, 32, 16]
    margem, w = 24, sum(lados) + 24 * (len(lados) + 1)
    h = 2 * (512 + 2 * margem)
    folha = QImage(w, h, QImage.Format.Format_ARGB32)
    p = QPainter(folha)
    for faixa, cor in enumerate(("#f2f2f0", "#1e1e1e")):
        y0 = faixa * (512 + 2 * margem)
        p.fillRect(0, y0, w, 512 + 2 * margem, QColor(cor))
        x = margem
        for n in lados:
            p.drawImage(x, y0 + margem + (512 - n), renderiza(r, n))
            x += n + margem
    p.end()
    folha.save(str(destino))


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841 (Qt exige)
    r = QSvgRenderer(str(SVG))
    if not r.isValid():
        sys.exit(f"SVG invalido: {SVG}")
    escreve_ico(r, AQUI / "icone.ico")
    escreve_icns(r, AQUI / "icone.icns")
    renderiza(r, 256).save(str(PNG_JANELA))
    escreve_previa(r, AQUI / "previa.png")
    for f in sorted(AQUI.iterdir()) + [PNG_JANELA]:
        if f.suffix in (".icns", ".ico", ".png"):
            print(f"{f.name:16s} {f.stat().st_size:>9,d} bytes")


if __name__ == "__main__":
    main()
