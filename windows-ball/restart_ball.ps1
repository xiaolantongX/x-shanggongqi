$dir = Join-Path $env:LOCALAPPDATA 'XFanGrowth'
# stop old float
Get-Process python,py -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cmd = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_.Id)).CommandLine
    if ($cmd -and $cmd -like '*fan_ball.py*') {
      Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
  } catch {}
}
Start-Sleep -Milliseconds 400
$pc = Join-Path $dir '__pycache__'
if (Test-Path $pc) { Remove-Item $pc -Recurse -Force }
# ensure pillow
& py -3 -m pip install pillow -q
Start-Sleep -Milliseconds 200
Start-Process -FilePath 'wscript.exe' -ArgumentList ('"' + $dir + '\start_fan_ball.vbs"') -WindowStyle Hidden
Start-Sleep -Seconds 2
Get-Process python,py -ErrorAction SilentlyContinue | Select-Object ProcessName,Id | Format-Table -AutoSize
