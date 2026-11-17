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
# ⚠️ Sao ~287 GB. Reexecutar so' copia o que mudou (robocopy pula arquivo igual).
# NAO usar /J nem /MT aqui: num HD USB em exFAT, 8 threads com I/O sem buffer travaram na
# finalizacao dos arquivos (ficaram com tamanho arredondado ao setor) e o robocopy ficou preso em
# tentativas infinitas, em silencio. Copia sequencial com buffer, 3 tentativas, log em build\.
param(
    [Parameter(Mandatory = $true)][string]$Destino,
    [string]$Dados = "F:\sits_aoi_crop",
    [string]$Dist = "D:\NAVIGATOR\build\dist\CycleNavigator",
    [switch]$SoDados,
    # Pacote reduzido: so' os meses destas safras ("2023/24" = out/2023..set/2024). Uma safra sao
    # ~75 GB em vez de 287 -- cabe no disco interno de um MacBook Air. Vazio = todos os meses.
    [string[]]$Safras = @()
)

function MesesDaSafra([string]$s) {
    $a = [int]$s.Substring(0, 4)
    @(10, 11, 12 | ForEach-Object { $a * 100 + $_ }) + @(1..9 | ForEach-Object { ($a + 1) * 100 + $_ })
}
$mesesSel = @(); foreach ($s in $Safras) { $mesesSel += MesesDaSafra $s }
$mesesSel = $mesesSel | Sort-Object -Unique
$ErrorActionPreference = "Stop"
$RoboLog = Join-Path $PSScriptRoot "monta_ssd_robocopy.log"
if (Test-Path $RoboLog) { Remove-Item $RoboLog -Force }
# so' erros e resumo no log: /NFL /NDL tiram a lista de arquivos, /NP a porcentagem
$Robo = @("/R:3", "/W:5", "/NFL", "/NDL", "/NJH", "/NP", "/LOG+:$RoboLog")
function Falhou([string]$oque) {
    if ($LASTEXITCODE -ge 8) { throw "robocopy de $oque falhou (codigo $LASTEXITCODE); veja $RoboLog" }
}
# ⚠️ O SSD tem de estar em exFAT para servir Windows E Mac. Em NTFS o Mac so' LE: o programa abre,
# mas nao consegue gravar os pontos nem o log. Formatar (apaga o disco!): no Windows, botao direito
# no drive -> Formatar -> exFAT; ou `Format-Volume -DriveLetter E -FileSystem exFAT`.
$letra = ($Destino -split ":")[0]
if ($letra.Length -eq 1) {
    $vol = Get-Volume -DriveLetter $letra -ErrorAction SilentlyContinue
    if ($vol -and $vol.FileSystem -ne "exFAT") {
        Write-Warning ("o drive {0}: esta' em {1}. Para usar tambem num Mac, formate em exFAT ANTES de copiar " +
                       "(num Mac, {1} e' somente-leitura e o programa nao grava os pontos)." -f $letra, $vol.FileSystem)
        $resp = Read-Host "Continuar mesmo assim? (s/N)"
        if ($resp -notmatch "^[sS]") { throw "interrompido: formate o SSD em exFAT e rode de novo" }
    }
}
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

if (-not $SoDados) {
    if (-not (Test-Path "$Dist\cycle-navigator.exe")) { throw "executavel nao encontrado em $Dist (rode o PyInstaller antes)" }
    Write-Output "== executavel (Windows) =="
    robocopy $Dist $Destino /E @Robo | Out-Null
    Falhou "executavel"
    # os .app do Mac (artefatos do GitHub, em .tar.gz) vao junto, para o mesmo SSD servir os dois.
    # No Mac: tar -xzf CycleNavigator-macos-arm64.tar.gz  (ou -x64 em Mac Intel)
    $art = Join-Path (Split-Path $Dist -Parent) "..\artefatos"
    if (Test-Path $art) {
        Write-Output "== .app do Mac (tar.gz) =="
        # o gh run download poe cada artefato numa subpasta com o nome dele: por isso -Recurse
        # so' os nossos: dentro do artefato do Windows ha' um dateutil-zoneinfo.tar.gz que nao e' app
        Get-ChildItem $art -Recurse -Filter "CycleNavigator-*.tar.gz" | ForEach-Object {
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
    if ($sub -eq "cube" -and $mesesSel.Count -gt 0) {
        # pacote reduzido: so' os meses das safras pedidas
        $arqs = $mesesSel | ForEach-Object { "ride_${_}_aoi.tif" }
        robocopy $o (Join-Path $Destino "dados\cube") @arqs @Robo | Out-Null
    } else {
        robocopy $o (Join-Path $Destino "dados\$sub") /E @Robo /XF *.zip *_bruto.gpkg /XD partes | Out-Null
    }
    Falhou $sub
    $gb = [math]::Round((Get-ChildItem (Join-Path $Destino "dados\$sub") -Recurse -File | Measure-Object Length -Sum).Sum / 1GB, 1)
    Write-Output ("   {0,-9} {1,7} GB" -f $sub, $gb)
}

# config com caminho relativo: o mesmo arquivo vale no Windows (E:\) e no Mac (/Volumes/...)
$toml = Get-Content "D:\NAVIGATOR\cycle-navigator.toml" -Raw
$toml = $toml -replace 'aoi\s*=\s*"[^"]*"', 'aoi = "dados"'
$toml = $toml -replace '(?m)^\s*car\s*=.*$', ''
if ($mesesSel.Count -gt 0) {
    # o config confere que TODO mes listado existe: num pacote reduzido a lista tem de encolher junto
    $lista = "meses = [" + (($mesesSel | ForEach-Object { "$_" }) -join ", ") + "]"
    $toml = [regex]::Replace($toml, '(?s)meses\s*=\s*\[.*?\]', $lista)
}
[System.IO.File]::WriteAllText((Join-Path $Destino "cycle-navigator.toml"), $toml, (New-Object System.Text.UTF8Encoding $false))

# instrucoes para quem abrir o SSD num Mac (sem acento no nome do arquivo: exFAT + Finder)
$leiaMac = @"
CYCLE NAVIGATOR NO MAC

1. Descubra o chip:  menu Apple > Sobre este Mac.
   "Chip Apple M1/M2/M3/M4"  -> use CycleNavigator-macos-arm64.tar.gz
   "Processador Intel"        -> use CycleNavigator-macos-x64.tar.gz
   Precisa de macOS 12 (Monterey) ou mais novo.

2. Extraia o .tar.gz AQUI MESMO, nesta pasta do SSD (duplo clique no Finder, ou no Terminal):
      cd /Volumes/<nome do SSD>/CycleNavigator
      tar -xzf CycleNavigator-macos-arm64.tar.gz
   Vai aparecer CycleNavigator.app ao lado de cycle-navigator.toml e da pasta dados.
   O programa procura o .toml e a pasta dados AO LADO do .app: nao mova o .app para outro lugar
   sem levar os dois junto.

3. Primeira abertura: o macOS bloqueia apps sem assinatura da Apple.
   - macOS 14 ou anterior: botao direito (Control+clique) no CycleNavigator.app > Abrir > Abrir.
   - macOS 15 (Sequoia) ou mais novo: o botao direito ja' nao basta. Tente abrir uma vez (vai
     bloquear), depois va' em Ajustes do Sistema > Privacidade e Seguranca, role ate' o fim e
     clique em "Abrir Mesmo Assim". So' na primeira vez.
   - Alternativa em qualquer versao, no Terminal (tira a marca de quarentena):
      xattr -dr com.apple.quarantine "/Volumes/<nome do SSD>/CycleNavigator/CycleNavigator.app"

4. Demora cerca de 1 minuto para abrir (carrega 4 safras, CAR e SAM). Se algo der errado,
   o arquivo cycle-navigator.log aparece nesta pasta: mande ele.

5. Os pontos e fazendas que voce gravar ficam em dados/pontos/. E' isso que volta para o
   projeto. Faca copia dessa pasta ao fim de cada dia de campo.

6. OPCIONAL, RECOMENDADO se o Mac tiver espaco (a pasta toda tem ~290 GB): copie a pasta
   CycleNavigator inteira do SSD para a pasta pessoal do Mac (arraste no Finder) e use a
   copia. Fica muito mais rapido e nao depende do SSD estar espetado. O .toml usa caminho
   relativo: nada precisa ser editado. O cycle-navigator.exe e a pasta _internal sao do
   Windows e podem ser apagados da copia. O SSD vira o backup.
"@
[System.IO.File]::WriteAllText((Join-Path $Destino "LEIA-ME_MAC.txt"), $leiaMac, (New-Object System.Text.UTF8Encoding $false))

# conferencia: tamanho de cada tif igual ao da origem (pega copia interrompida ou nao finalizada)
$dif = Get-ChildItem (Join-Path $Destino "dados\cube") -Filter *.tif | Where-Object {
    $orig = Join-Path $Dados "cube\$($_.Name)"; -not (Test-Path $orig) -or (Get-Item $orig).Length -ne $_.Length }
if ($dif) { Write-Warning ("tamanho diferente da origem: " + (($dif | ForEach-Object Name) -join ", ") + " -- rode de novo") }
else { Write-Output "   cube: todos os tifs com o tamanho da origem" }
$tot = [math]::Round((Get-ChildItem $Destino -Recurse -File | Measure-Object Length -Sum).Sum / 1GB, 1)
Write-Output "== pronto: $Destino ($tot GB) =="
Write-Output "   Windows: abra cycle-navigator.exe.  Mac: copie o CycleNavigator.app (artefato do GitHub) para esta pasta."
