<#
    shots63.ps1 - capturas del juego en modo replay (Etapa 6.3) en WinUAE
    (cycle-exact): DIR\F\game.adf (armado con -DREPLAY -DSTOPF=F-5145 por
    tools/game_build.sh) -> DIR\F.png. La espera cubre el arranque de KS 1.2
    (~15 s), la carga (~350 KB) y los frames del replay hasta F, con margen
    por si algun frame se pasa (el replay se para en STOPF: esperar de mas
    no cambia la captura).

        .\tools\shots63.ps1 -Dir work\g63 -Fs 6000,7000
#>
param(
    [Parameter(Mandatory = $true)][string]$Dir,
    [int[]]$Fs = @(6000, 7000, 8000, 9000, 10000, 11000),
    [int]$First = 5145,
    [int]$Extra = 0
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($f in $Fs) {
    $png = Join-Path $Dir "$f.png"
    $wait = 45 + [int](($f - $First) / 50 * 1.5) + $Extra
    for ($t = 0; $t -lt 3; $t++) {
        $start = Get-Date
        & (Join-Path $here 'shot.ps1') -Adf (Join-Path $Dir "$f\game.adf") -Out $png -Wait $wait -Exact | Out-Null
        if ((Test-Path $png) -and ((Get-Item $png).LastWriteTime -gt $start)) {
            Write-Host "f=$f -> $png"
            break
        }
        Write-Host "f=${f}: sin captura, reintento"
    }
}
