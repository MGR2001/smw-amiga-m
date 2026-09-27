<#
    shots6.ps1 - capturas de scroll.s en WinUAE (cycle-exact) en las x de
    regress.py, desde ADFs ya armados: DIR\scrollX.adf -> DIR\sX.png.
    Reintenta si WinUAE no dio ventana (P: a veces sale de 199 x 34).
    La espera cubre el arranque de KS 1.2 en WinUAE (~15 s) y el scroll a
    2 px por frame; el scroll se para en STOPX, asi que esperar de mas no
    cambia la captura.

        .\tools\shots6.ps1 -Dir work\w1
        .\tools\shots6.ps1 -Dir work\w1 -Xs 1000,4500
#>
param(
    [Parameter(Mandatory = $true)][string]$Dir,
    [int[]]$Xs = @(500, 1000, 1700, 2500, 3500, 4500)
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($x in $Xs) {
    $png = Join-Path $Dir "s$x.png"
    $wait = 25 + [int]($x / 100)
    for ($t = 0; $t -lt 3; $t++) {
        $start = Get-Date
        & (Join-Path $here 'shot.ps1') -Adf (Join-Path $Dir "scroll$x.adf") -Out $png -Wait $wait -Exact | Out-Null
        if ((Test-Path $png) -and ((Get-Item $png).LastWriteTime -gt $start)) {
            Write-Host "x=$x -> $png"
            break
        }
        Write-Host "x=${x}: sin captura, reintento"
    }
}
