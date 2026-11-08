$dir = Join-Path $env:LOCALAPPDATA 'XFanGrowth'
$pyScript = Join-Path $dir 'fan_ball.py'
$log = Join-Path $dir 'fan_ball_run.log'
# kill old
Get-Process python,py -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cmd = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_.Id)).CommandLine
    if ($cmd -and $cmd -like '*fan_ball.py*') {
      Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
  } catch {}
}
Start-Sleep -Milliseconds 500
& py -3 -m pip install pillow -q
if (Test-Path $log) { Remove-Item $log -Force }
$argsList = @('-3', $pyScript)
if ($env:XFAN_DEMO_PANEL -eq '1') { $argsList += '--demo-panel' }
$p = Start-Process -FilePath 'py' -ArgumentList $argsList -WorkingDirectory $dir -RedirectStandardError $log -RedirectStandardOutput (Join-Path $dir 'fan_ball_out.log') -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3
Write-Output ("pid=" + $p.Id + " exit=" + $p.HasExited)
if (Test-Path $log) { Write-Output '---stderr---'; Get-Content $log -Raw }
$out = Join-Path $dir 'fan_ball_out.log'
if (Test-Path $out) { Write-Output '---stdout---'; Get-Content $out -Raw }
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*fan_ball.py*' } | Select-Object ProcessId, Name, CommandLine | Format-List
