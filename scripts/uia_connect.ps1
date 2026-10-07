# For each Azahar window: bring to front, Multiplayer -> Direct Connect to Room -> Connect (fields prefilled from config).
# Only acts after confirming the Azahar window is the foreground window.
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Fg { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
 [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte sc, uint f, UIntPtr e);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, UIntPtr e); }
"@
$AE = [System.Windows.Automation.AutomationElement]
$Scope = [System.Windows.Automation.TreeScope]
function ByName($root, $name) { $root.FindFirst($Scope::Descendants, (New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $name))) }
function TopsOf($procId) { $AE::RootElement.FindAll($Scope::Children, (New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty, $procId))) }
function Click($el) {
  $r = $el.Current.BoundingRectangle
  [Fg]::SetCursorPos([int]($r.X + $r.Width / 2), [int]($r.Y + $r.Height / 2))
  [Fg]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero); [Fg]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
}
function Press($el) {
  $p = $null
  if ($el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$p)) { $p.Invoke(); return }
  $el.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$p) | Out-Null; $p.Expand()
}
foreach ($proc in Get-Process azahar | Sort-Object Path) {
  $who = if ($proc.Path -like '*\p1\*') { 'P1' } else { 'P2' }
  $h = $proc.MainWindowHandle
  $st = $AE::FromHandle($h).FindFirst($Scope::Descendants, (New-Object System.Windows.Automation.PropertyCondition($AE::AutomationIdProperty, 'QApplication.MainWindow.QStatusBar.ClickableLabel')))
  if ($st -and $st.Current.Name -like 'Connected*') { "$who : already connected"; continue }
  # Alt tap lets SetForegroundWindow succeed from a background process
  [Fg]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [Fg]::SetForegroundWindow($h) | Out-Null; [Fg]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 400
  if ([Fg]::GetForegroundWindow() -ne $h) { "$who : couldn't bring window to front, skipping"; continue }
  $win = $AE::FromHandle($h)
  [Fg]::keybd_event(0x1B, 0, 0, [UIntPtr]::Zero); [Fg]::keybd_event(0x1B, 0, 2, [UIntPtr]::Zero)  # close any open menu
  Start-Sleep -Milliseconds 300
  Click (ByName $win 'Multiplayer'); Start-Sleep -Milliseconds 800
  $item = $null
  foreach ($tw in TopsOf $proc.Id) { foreach ($n in 'Direct Connect to Room', 'Direct Connect to Room...', '&Direct Connect to Room') { if (-not $item) { $item = ByName $tw $n } } }
  if (-not $item) {
    "$who : menu item not found; menu contains:"
    foreach ($tw in TopsOf $proc.Id) { foreach ($d in $tw.FindAll($Scope::Descendants, (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, [System.Windows.Automation.ControlType]::MenuItem)))) { "   '$($d.Current.Name)'" } }
    continue
  }
  Press $item; Start-Sleep -Milliseconds 1200
  foreach ($tw in TopsOf $proc.Id) {
    foreach ($e in $tw.FindAll($Scope::Descendants, (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)))) {
      $vp = $null; $e.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$vp) | Out-Null
      "$who field [$($e.Current.AutomationId)] = '$($vp.Current.Value)'"
      if ($e.Current.AutomationId -like '*nickname*' -or $e.Current.AutomationId -like '*username*') { $vp.SetValue("Player" + $who.Substring(1)); "$who   -> set to Player$($who.Substring(1))" }
    }
  }
  $btn = $null
  foreach ($tw in TopsOf $proc.Id) { if (-not $btn) { $btn = ByName $tw 'Connect' } }
  if (-not $btn) { "$who : Connect button not found"; continue }
  Press $btn; Start-Sleep 2
  "$who : connect pressed"
}
Start-Sleep 2
foreach ($proc in Get-Process azahar | Sort-Object Path) {
  $lbl = $AE::FromHandle($proc.MainWindowHandle).FindFirst($Scope::Descendants, (New-Object System.Windows.Automation.PropertyCondition($AE::AutomationIdProperty, 'QApplication.MainWindow.QStatusBar.ClickableLabel')))
  "$(if ($proc.Path -like '*\p1\*') {'P1'} else {'P2'}) status: $($lbl.Current.Name)"
}
