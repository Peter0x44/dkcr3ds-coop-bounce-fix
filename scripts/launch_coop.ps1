# Start room server (if needed), keyboard->pad bridge (if needed), both Azahar instances with the game, tiled side by side.
# Expects portable Azahar copies in tools\azahar\p1 and tools\azahar\p2 (see PROCESS.md section 5).
param([string]$Rom)
$root = Split-Path -Parent $PSScriptRoot
$az = "$root\tools\azahar"
# default: the USA dump if present, else the first .cci in work\
if (-not $Rom) { $Rom = (Get-ChildItem "$root\work\*.cci" | Sort-Object { $_.Name -notlike '*(USA)*' } | Select-Object -First 1).FullName }
$rom = $Rom
if (-not (Get-Process azahar-room -ErrorAction SilentlyContinue)) {
  Start-Process "$az\p1\azahar-room.exe" -ArgumentList '--room-name','DKCR-test','--port','24872','--max_members','4','--preferred-app','DKCR3D','--preferred-app-id','00040000000CCE00' -WindowStyle Minimized
}
if (-not (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like '*kb2pads*' })) {
  Start-Process python -ArgumentList "$root\scripts\kb2pads.py" -WindowStyle Minimized
  Start-Sleep 2
}
$procs = @()
foreach ($n in 'p1','p2') {
  if (-not (Get-Process azahar -ErrorAction SilentlyContinue | ? { $_.Path -like "*\$n\*" })) {
    Start-Process "$az\$n\azahar.exe" -ArgumentList "`"$rom`""; Start-Sleep 2
  }
}
Start-Sleep 5
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Mv { [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool r); }
"@
Add-Type -AssemblyName System.Windows.Forms
$wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea; $half = [int]($wa.Width / 2)
foreach ($p in Get-Process azahar) {
  $x = if ($p.Path -like '*\p1\*') { $wa.X } else { $wa.X + $half }
  [Mv]::MoveWindow($p.MainWindowHandle, $x, $wa.Y, $half, $wa.Height, $true) | Out-Null
  "$($p.Id) $($p.Path)"
}
