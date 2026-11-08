$p = Join-Path $env:LOCALAPPDATA 'XFanGrowth\state.json'
$raw = Get-Content $p -Raw -Encoding UTF8
$j = $raw | ConvertFrom-Json
if ($j.PSObject.Properties.Name -contains 'last_new_name') {
  $j.PSObject.Properties.Remove('last_new_name')
}
$j.new_followers = @()
$j.toast_queue = @()
$json = $j | ConvertTo-Json -Depth 30
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($p, $json, $utf8NoBom)
Write-Output 'cleared'
