<#
    build.ps1 - construccion y prueba del port-demo SMW -> Amiga 500.

        .\build.ps1 build          ensambla el bootblock y el programa, y arma el ADF
        .\build.ps1 shot           build + arranca en WinUAE y saca una captura PNG
        .\build.ps1 shot -Every 5 -Wait 30   varias capturas (linea de tiempo)
        .\build.ps1 run            build + WinUAE interactivo, lo cerras vos
        .\build.ps1 clean          borra work\

    Objetivo: Amiga 500 PAL, OCS, 512K chip + 512K slow (A501), Kickstart 1.2.
    Sin AmigaDOS y sin hunks: el bootblock lee sectores crudos, asi que
    funciona igual en KS 1.2 que en 1.3.
#>
[CmdletBinding()]
param(
    [ValidateSet('build', 'shot', 'run', 'clean')]
    [string]$Task = 'build',

    [string]$Vasm   = 'C:\Users\JC\vbcc\bin\vasmm68k_mot.exe',
    [string]$WinUAE = 'C:\Program Files\WinUAE\winuae64.exe',
    [string]$Rom    = 'C:\Users\JC\Downloads\amivideo\kick12.rom',
    [string]$Py     = 'C:\Users\JC\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe',

    [int]$Wait      = 25,
    [int]$Every     = 0,
    [string]$Out    = '',

    # parametros del demo (los usa mkdemo.py)
    [string]$Gfx    = 'chr',
    # --pal: cgram:N | mario | luigi | mariofire | luigifire | raw:NAME
    [string]$Pal    = 'mario',
    # header de 5 bytes del nivel en hex; define fg/bg/spr pal y color de fondo
    [string]$Level  = '3340088027',
    [int]$Cols      = 40,
    [int]$Rows      = 32,
    [int]$Planes    = 4
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $root 'work'
$tools = Join-Path $root 'tools'
$player = Join-Path $root 'player'
$script:LogPath = Join-Path $work 'build.log'

# OJO: nada de $ErrorActionPreference = 'Stop'. vasm escribe su banner a
# stderr, y con 'Stop' PowerShell convierte esa salida en un error
# terminante y aborta el script en la primera invocacion.
$ErrorActionPreference = 'Continue'

if (-not (Test-Path $work)) { New-Item -ItemType Directory $work | Out-Null }
Set-Content -Path $script:LogPath -Value ("build.ps1 -Task $Task  " + (Get-Date)) -Encoding utf8

function Log {
    param([string]$Text = '')
    Write-Host $Text
    Add-Content -Path $script:LogPath -Value $Text -Encoding utf8
}

function Invoke-Tool {
    param([string]$Exe, [string[]]$Arguments)
    Log "+ $Exe $($Arguments -join ' ')"
    $out = & $Exe @Arguments 2>&1
    $code = $LASTEXITCODE
    foreach ($line in $out) { Log "  $line" }
    if ($code -ne 0) { throw "fallo: $Exe (codigo $code)" }
}

function Build-All {
    if (-not (Test-Path $Vasm)) { throw "No encuentro vasm en '$Vasm'." }
    if (-not (Test-Path $Py))   { throw "No encuentro python en '$Py'." }
    if (-not (Test-Path $work)) { New-Item -ItemType Directory $work | Out-Null }

    Invoke-Tool $Vasm @('-Fbin', '-m68000', '-no-opt', '-I', $player,
                        '-o', (Join-Path $work 'boot.bin'),
                        (Join-Path $player 'boot.s'))

    Invoke-Tool $Vasm @('-Fbin', '-m68000', '-no-opt', '-I', $player,
                        '-o', (Join-Path $work 'demo.bin'),
                        (Join-Path $player 'demo.s'))

    Invoke-Tool $Py @((Join-Path $tools 'mkdemo.py'),
                      '--gfx', $Gfx, '--pal', $Pal, '--level', $Level,
                      '--cols', "$Cols", '--rows', "$Rows", '--planes', "$Planes",
                      '--out', (Join-Path $work 'demo.dat'))

    Invoke-Tool $Py @((Join-Path $tools 'mkadf.py'),
                      '--boot',   (Join-Path $work 'boot.bin'),
                      '--stage2', (Join-Path $work 'demo.bin'),
                      '--data',   (Join-Path $work 'demo.dat'),
                      '--out',    (Join-Path $work 'smw.adf'))
}

# Genera el .uae en work\ y lanza WinUAE. Config probada: A500 PAL, OCS,
# 512K chip + 512K slow, KS 1.2, sin fast RAM.
function Start-Emulator {
    param([string]$AdfPath = '')

    if (-not (Test-Path $WinUAE)) { throw "No encuentro WinUAE en '$WinUAE'." }
    if (-not (Test-Path $Rom))    { throw "No encuentro la ROM en '$Rom'. Pasa -Rom <ruta>." }

    $adf = if ($AdfPath) { $AdfPath } else { Join-Path $work 'smw.adf' }
    if (-not (Test-Path $adf)) { throw "No hay ADF en '$adf'; corre '.\build.ps1' primero." }

    $cfg = Join-Path $work 'smw.uae'
    $lines = @(
        'config_description=SMW port-demo - A500 PAL 512K+512K A501 KS1.2'
        'chipset=ocs'
        'chipset_compatible=A500'
        'ntsc=false'
        'cpu_type=68000'
        'cpu_model=68000'
        'cpu_compatible=false'
        'cpu_speed=max'
        'cycle_exact=false'
        'blitter_cycle_exact=false'
        'immediate_blits=true'
        'chipmem_size=1'
        'bogomem_size=2'
        'fastmem_size=0'
        'z3mem_size=0'
        "kickstart_rom_file=$Rom"
        "floppy0=$adf"
        'floppy0type=0'
        'floppy0wp=false'
        'nr_floppies=1'
        'floppy_speed=100'
        'gfx_width=720'
        'gfx_height=568'
        'gfx_lores=true'
        'gfx_linemode=double'
        'gfx_framerate=10'
        'win32.start_not_captured=true'
        'win32.nonotificationicon=true'
    )
    Set-Content -Path $cfg -Value $lines -Encoding ascii

    Log "ROM : $Rom"
    Log "ADF : $adf"
    Log "CFG : $cfg"
    $proc = Start-Process -FilePath $WinUAE -ArgumentList @('-f', "`"$cfg`"") -PassThru
    return @{ Process = $proc; Adf = $adf; Cfg = $cfg }
}

#---------------------------------------------------------------------------
switch ($Task) {
    'clean' {
        if (Test-Path $work) { Remove-Item $work -Recurse -Force }
        Log "work\ borrado"
    }

    'build' { Build-All }

    'run' {
        Build-All
        $r = Start-Emulator
        Log "WinUAE lanzado. Cerralo vos cuando termines de mirar."
    }

    'shot' {
        # Una sola implementacion de la captura: tools\shot.ps1 (config del
        # emulador, espera a que la ventana tenga contenido, borra la captura
        # vieja y sale con 1 si falla).
        Build-All
        if (-not $Out) { $Out = Join-Path $work 'shot.png' }
        & (Join-Path $tools 'shot.ps1') -Adf (Join-Path $work 'smw.adf') -Out $Out `
            -Wait $Wait -Every $Every -WinUAE $WinUAE -Rom $Rom
        if ($LASTEXITCODE -ne 0) { throw "la captura fallo (ver work\shot.log)" }
        Log "listo"
    }
}
