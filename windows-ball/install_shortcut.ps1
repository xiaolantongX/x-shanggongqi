$dir = Join-Path $env:LOCALAPPDATA 'XFanGrowth'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$desk = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desk 'X-Fan-Ball.lnk'
$w = New-Object -ComObject WScript.Shell
$l = $w.CreateShortcut($lnkPath)
$l.TargetPath = 'wscript.exe'
$l.Arguments = '"' + $dir + '\start_fan_ball.vbs"'
$l.WorkingDirectory = $dir
$l.WindowStyle = 7
$l.Description = 'X fan growth floating ball'
$l.Save()
Write-Output ("shortcut=" + $lnkPath)
Get-ChildItem $dir | ForEach-Object { $_.Name + ' ' + $_.Length }
