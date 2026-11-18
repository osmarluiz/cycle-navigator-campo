# -*- coding: utf-8 -*-
"""Mac: cada pacote volta a carregar as SUAS bibliotecas nativas dentro do .app.

    python build/corrige_dylibs_mac.py build/dist/CycleNavigator.app     (o spec ja' chama sozinho)

⚠️ O PROBLEMA. As wheels de Mac trazem as bibliotecas nativas em <pacote>/.dylibs/, e varias trazem
uma com o MESMO NOME: pyproj e rasterio tem cada um a sua libproj.25.9.8.1.dylib, e PIL/pyproj/
rasterio repetem libtiff, liblzma, libjpeg, libzstd... No venv cada extensao acha a do seu pacote
(rpath @loader_path/.dylibs). O PyInstaller, porem, poe UM link por nome em Contents/Frameworks/ e
reescreve o rpath das extensoes para la' -- quem chegou primeiro ganha. Com a libproj ganhou a do
rasterio, que tem os simbolos do PROJ renomeados, e o pyproj morria no import com
"Symbol not found: _proj_context_create". O geopandas engolia o erro ("Cannot set the CRS, falling
back to None"): o programa abria, o CAR carregava, e a exportacao saia sem sistema de coordenadas.

⚠️ A CORRECAO. Depois do BUNDLE, para cada .so/.dylib dentro de Contents/Frameworks/<pacote>/,
toda dependencia @rpath/X que exista em <pacote>/__dot__dylibs/ (o nome que o PyInstaller da' a
.dylibs) passa a apontar para ela por @loader_path. Depois, reassinatura ad hoc (o Apple Silicon
nao executa binario com assinatura invalida, e install_name_tool invalida a assinatura).
No Windows nada disto existe: o delvewheel ja' poe um hash no nome de cada DLL.

⚠️ O CAMINHO NOVO NAO PODE SER MAIS COMPRIDO QUE O DA WHEEL. O cabecalho Mach-O tem espaco contado:
a wheel vinha com "@loader_path/.dylibs/X" e "@loader_path/__dot__dylibs/X" tem 6 letras a mais.
Nas wheels arm64 sobrava folga; nas x86_64 nao, e o install_name_tool recusava ("load commands do
not fit") -- o build de Mac Intel quebrou assim em 18/11/2026. Por isso cada pacote ganha um link
curto `dl -> __dot__dylibs` e o caminho gravado e' "@loader_path/dl/X", sempre menor que o original.
"""
import os
import pathlib
import subprocess
import sys

DYLIBS = "__dot__dylibs"
CURTO = "dl"            # link <pacote>/dl -> __dot__dylibs (ver o aviso do cabecalho)


def _deps(binario: pathlib.Path) -> list[str]:
    saida = subprocess.run(["otool", "-L", str(binario)], capture_output=True, text=True).stdout
    return [linha.split()[0] for linha in saida.splitlines()[1:] if linha.strip()]


def _macho(p: pathlib.Path) -> bool:
    if p.is_symlink() or not p.is_file():
        return False
    with open(p, "rb") as f:
        return f.read(4) in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")


def corrige(app: pathlib.Path) -> int:
    frameworks = app / "Contents" / "Frameworks"
    mudados = []
    for pacote in sorted(p for p in frameworks.iterdir() if p.is_dir() and (p / DYLIBS).is_dir()):
        proprias = {f.name for f in (pacote / DYLIBS).iterdir()}
        curto = pacote / CURTO
        if not curto.exists():
            curto.symlink_to(DYLIBS)
        for binario in pacote.rglob("*"):
            if not _macho(binario):
                continue
            trocas = []
            for dep in _deps(binario):
                nome = dep.removeprefix("@rpath/")
                if dep.startswith("@rpath/") and nome in proprias:
                    # vale tambem para as libs DENTRO da .dylibs (libproj -> libtiff do mesmo pacote)
                    # as de dentro da .dylibs se acham lado a lado; as outras passam pelo link curto
                    de_dentro = binario.parent == pacote / DYLIBS
                    rel = nome if de_dentro else os.path.relpath(curto / nome, binario.parent)
                    trocas += ["-change", dep, f"@loader_path/{rel}"]
            if trocas:
                r = subprocess.run(["install_name_tool", *trocas, str(binario)],
                                   capture_output=True, text=True)
                if r.returncode:        # o motivo tem de aparecer no log do build, nao so' "status 1"
                    raise RuntimeError(f"install_name_tool em {binario}: {r.stderr.strip()}")
                mudados.append(binario)
    for binario in mudados:
        subprocess.run(["codesign", "--force", "--sign", "-", str(binario)], check=True,
                       capture_output=True)
    if mudados:
        subprocess.run(["codesign", "--force", "--sign", "-", str(app)], check=True,
                       capture_output=True)
    return len(mudados)


if __name__ == "__main__":
    n = corrige(pathlib.Path(sys.argv[1]).resolve())
    print(f"{n} binarios passaram a usar as bibliotecas do proprio pacote")
