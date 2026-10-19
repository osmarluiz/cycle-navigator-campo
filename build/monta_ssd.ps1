# Monta o pacote de campo num SSD externo: executavel + dados + config com caminho RELATIVO.
#
#   .\build\monta_ssd.ps1 -Destino "E:\CycleNavigator"            # Windows (usa build\dist)
#   .\build\monta_ssd.ps1 -Destino "E:\CycleNavigator" -SoDados   # so' os dados (p/ Mac, que tem o .app proprio)
#
# Layout no SSD:
#   CycleNavigator\
#     cycle-navigator.exe (+ DLLs)     <- build\dist\CycleNavigator (Windows)
#     CycleNavigator.app               <- artefato macOS do GitHub, copiado a' mao
#     cycle-navigator.toml             <- aoi = "dados"  (relativo: vale em qualquer letra de drive)
#     dados\cube, input, products, car, sam, pontos
#
# ⚠️ robocopy com /J (I/O sem buffer) e /MT: sao ~284 GB. Reexecutar so' copia o que mudou.
param(
    [Parameter(Mandatory = $true)][string]$Destino,
    [string]$Dados = "F:\sits_aoi_crop",
    [string]$Dist = "D:\NAVIGATOR\build\dist\CycleNavigator",
    [switch]$SoDados
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

if (-not $SoDados) {
    if (-not (Test-Path "$Dist\cycle-navigator.exe")) { throw "executavel nao encontrado em $Dist (rode o PyInstaller antes)" }
    Write-Output "== executavel (Windows) =="
    robocopy $Dist $Destino /E /J /MT:8 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy do executavel falhou ($LASTEXITCODE)" }
    # os .app do Mac (artefatos do GitHub, em .tar.gz) vao junto, para o mesmo SSD servir os dois.
    # No Mac: tar -xzf CycleNavigator-macos-arm64.tar.gz  (ou -x64 em Mac Intel)
    $art = Join-Path (Split-Path $Dist -Parent) "..\artefatos"
    if (Test-Path $art) {
        Write-Output "== .app do Mac (tar.gz) =="
        Get-ChildItem $art -Filter "*.tar.gz" | ForEach-Object {
            Copy-Item $_.FullName (Join-Path $Destino $_.Name) -Force
            Write-Output ("   {0}  {1:N0} MB" -f $_.Name, ($_.Length / 1MB))
        }
    }
}

Write-Output "== dados (pode levar uma hora num SSD USB 3) =="
foreach ($sub in @("cube", "input", "products", "car", "sam", "pontos")) {
    $o = Join-Path $Dados $sub
    if (-not (Test-Path $o)) { Write-Output "   (sem $sub, pulando)"; continue }
    # ⚠️ NAO leva os zips brutos do SICAR (907 MB), as partes do SAM nem o SAM bruto: so' o final
    robocopy $o (Join-Path $Destino "dados\$sub") /E /J /MT:8 /NFL /NDL /NJH /NJS /NP /XF *.zip *_bruto.gpkg /XD partes | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy de $sub falhou ($LASTEXITCODE)" }
    $gb = [math]::Round((Get-ChildItem (Join-Path $Destino "dados\$sub") -Recurse -File | Measure-Object Length -Sum).Sum / 1GB, 1)
    Write-Output ("   {0,-9} {1,7} GB" -f $sub, $gb)
}

# config com caminho relativo: o mesmo arquivo vale no Windows (E:\) e no Mac (/Volumes/...)
$toml = Get-Content "D:\NAVIGATOR\cycle-navigator.toml" -Raw
$toml = $toml -replace 'aoi\s*=\s*"[^"]*"', 'aoi = "dados"'
$toml = $toml -replace '(?m)^\s*car\s*=.*$', ''
[System.IO.File]::WriteAllText((Join-Path $Destino "cycle-navigator.toml"), $toml, (New-Object System.Text.UTF8Encoding $false))

$tot = [math]::Round((Get-ChildItem $Destino -Recurse -File | Measure-Object Length -Sum).Sum / 1GB, 1)
Write-Output "== pronto: $Destino ($tot GB) =="
Write-Output "   Windows: abra cycle-navigator.exe.  Mac: copie o CycleNavigator.app (artefato do GitHub) para esta pasta."
