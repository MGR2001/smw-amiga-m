<#
    shot.ps1 - arranca un ADF en WinUAE, captura la ventana y cierra.

        .\tools\shot.ps1 -Adf work\smw.adf -Out work\shot.png -Wait 25
        .\tools\shot.ps1 -Adf work\smw.adf -Out work\t.png -Wait 40 -Every 5
        .\tools\shot.ps1 -Exact -Wait 60     # temporizacion de A500 real

    Este script NO invoca ningun ejecutable de linea de comandos salvo
    WinUAE: solo escribe el .uae, lanza el emulador y captura con
    PrintWindow. Todo lo que hace queda en work\shot.log.

    La captura es de la VENTANA de WinUAE, no de la pantalla: PrintWindow
    pide a la ventana que se dibuje sola en un bitmap, asi que no importa
    que haya otra cosa encima y nunca se captura otra aplicacion.
#>
[CmdletBinding()]
param(
    [string]$Adf    = 'work\smw.adf',
    [string]$Out    = 'work\shot.png',
    [int]$Wait      = 25,
    [int]$Every     = 0,
    [string]$WinUAE = 'C:\Program Files\WinUAE\winuae64.exe',
    [string]$Rom    = 'C:\Users\JC\Downloads\amivideo\kick12.rom',
    # Sin -Exact el emulador va lo mas rapido posible (blits instantaneos): la
    # IMAGEN es correcta pero cualquier medida de tiempo es falsa.  Con -Exact
    # se usa la temporizacion de a500.uae (cycle-exact): es la unica config
    # valida para medir rendimiento (AGENTS.md §11).
    [switch]$Exact
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$work = Join-Path $root 'work'
if (-not (Test-Path $work)) { New-Item -ItemType Directory $work | Out-Null }
$script:LogPath = Join-Path $work 'shot.log'
Set-Content -Path $script:LogPath -Value ("shot.ps1  " + (Get-Date)) -Encoding utf8

function Log {
    param([string]$Text = '')
    Write-Host $Text
    Add-Content -Path $script:LogPath -Value $Text -Encoding utf8
}

if (-not [System.IO.Path]::IsPathRooted($Adf)) { $Adf = Join-Path $root $Adf }
if (-not [System.IO.Path]::IsPathRooted($Out)) { $Out = Join-Path $root $Out }

Log "ADF : $Adf"
Log "ROM : $Rom"
Log "OUT : $Out"

if (-not (Test-Path $Adf))    { Log "FALLO: no existe $Adf"; exit 2 }
if (-not (Test-Path $Rom))    { Log "FALLO: no existe $Rom"; exit 2 }
if (-not (Test-Path $WinUAE)) { Log "FALLO: no existe $WinUAE"; exit 2 }

# --- config: A500 PAL, OCS, 512K chip + 512K slow (A501), KS 1.2 ---------
$cfg = Join-Path $work 'shot.uae'
$lines = @(
    'config_description=SMW port-demo - A500 PAL 512K+512K A501 KS1.2'
    'chipset=ocs'
    'chipset_compatible=A500'
    'ntsc=false'
    'cpu_type=68000'
    'cpu_model=68000'
    'chipmem_size=1'
    'bogomem_size=2'
    'fastmem_size=0'
    'z3mem_size=0'
    "kickstart_rom_file=$Rom"
    "floppy0=$Adf"
    'floppy0type=0'
    'floppy0wp=false'
    'nr_floppies=1'
    'floppy_speed=100'
    # 720x568 es la ventana que da escala EXACTAMENTE 2x sobre la pantalla
    # PAL 320x256 (comprobado con autocorrelacion: paso de tile = 16 px de
    # pantalla para 8 px Amiga).  Con esta config, la captura recortada en
    # (67,70) + 640x512 coincide PIXEL A PIXEL con el oraculo del PC
    # (render_dat.py --scale 2): 100.00% de pixeles identicos.
    # No cambiar estos valores sin volver a medir el offset del recorte.
    'gfx_width=720'
    'gfx_height=568'
    'gfx_lores=true'
    'gfx_linemode=double'
    'gfx_framerate=10'
    'win32.start_not_captured=true'
    'win32.nonotificationicon=true'
    'use_gui=no'
)
# Temporizacion: rapida (solo imagen) o la de a500.uae (para medir).
if ($Exact) {
    $lines += @('cpu_compatible=true', 'cpu_speed=real', 'cycle_exact=true',
                'cpu_cycle_exact=true', 'cpu_memory_cycle_exact=true',
                'blitter_cycle_exact=true', 'immediate_blits=false', 'cachesize=0')
    Log "TIEMPO : cycle-exact (valido para medir)"
} else {
    $lines += @('cpu_compatible=false', 'cpu_speed=max', 'cycle_exact=false',
                'blitter_cycle_exact=false', 'immediate_blits=true')
    Log "TIEMPO : rapido (la imagen vale, los tiempos NO)"
}
Set-Content -Path $cfg -Value $lines -Encoding ascii
Log "CFG : $cfg"

# --- captura -------------------------------------------------------------
Add-Type -AssemblyName System.Drawing
if (-not ('A5Shot' -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class A5Shot {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
"@
}
[A5Shot]::SetProcessDPIAware() | Out-Null

function Save-Shot {
    param($Process, [string]$Path)
    $h = [IntPtr]::Zero
    for ($i = 0; $i -lt 30; $i++) {
        $Process.Refresh()
        $h = $Process.MainWindowHandle
        if ($h -ne [IntPtr]::Zero) { break }
        Start-Sleep -Milliseconds 500
    }
    if ($h -eq [IntPtr]::Zero) { Log "FALLO: WinUAE no tiene ventana"; return $false }
    # La ventana puede existir sin area de cliente todavia (se vio una
    # captura de 199x34: solo la barra de titulo).  Esperar a que tenga al
    # menos el tamano de la pantalla escalada (640x512) antes de capturar.
    $r = New-Object A5Shot+RECT
    for ($i = 0; $i -lt 20; $i++) {
        $Process.Refresh()
        $h = $Process.MainWindowHandle
        [A5Shot]::GetWindowRect($h, [ref]$r) | Out-Null
        if (($r.R - $r.L) -ge 640 -and ($r.B - $r.T) -ge 512) { break }
        Start-Sleep -Milliseconds 1000
    }
    $w = $r.R - $r.L
    $ht = $r.B - $r.T
    if ($w -lt 640 -or $ht -lt 512) { Log "FALLO: ventana de tamano $w x $ht (sin contenido)"; return $false }
    $bmp = New-Object System.Drawing.Bitmap $w, $ht
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    $ok = [A5Shot]::PrintWindow($h, $hdc, 2)   # 2 = PW_RENDERFULLCONTENT
    $g.ReleaseHdc($hdc)
    $g.Dispose()
    if (-not $ok) { $bmp.Dispose(); Log "FALLO: PrintWindow"; return $false }
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Log ("captura -> $Path  ($w x $ht)")
    return $true
}

Log "lanzando WinUAE..."
$proc = Start-Process -FilePath $WinUAE -ArgumentList @('-f', "`"$cfg`"") -PassThru
Log "pid $($proc.Id)"

if ($Every -gt 0) {
    $base = [System.IO.Path]::ChangeExtension($Out, $null).TrimEnd('.')
    $t0 = Get-Date
    for ($t = $Every; $t -le $Wait; $t += $Every) {
        $left = $t - ((Get-Date) - $t0).TotalSeconds
        if ($left -gt 0) { Start-Sleep -Milliseconds ([int]($left * 1000)) }
        Save-Shot $proc ('{0}_{1:d3}s.png' -f $base, $t) | Out-Null
    }
} else {
    # Borrar la captura anterior: si esta falla, verify_shot.py no puede
    # comparar (y aprobar) una imagen vieja.
    if (Test-Path $Out) { Remove-Item $Out -Force }
    Log "esperando $Wait s..."
    Start-Sleep -Seconds $Wait
    $script:shotOk = Save-Shot $proc $Out
}

if (-not $proc.HasExited) {
    $proc.CloseMainWindow() | Out-Null
    if (-not $proc.WaitForExit(6000)) { $proc.Kill(); $proc.WaitForExit(4000) | Out-Null }
}
Log "fin"
if ($Every -eq 0 -and -not $script:shotOk) { exit 1 }
