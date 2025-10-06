Set-Location -LiteralPath $PSScriptRoot\..
$py = "python"
$vf = Join-Path (Get-Location) "vfs_deep.json"
$sc = Join-Path (Get-Location) "scripts\start_4.txt"
Write-Host "Using VFS: $vf"
Write-Host "Script  : $sc"
& $py ".\KonfigManagment_12VAR.py" --vfs-json "$vf" --script "$sc"
