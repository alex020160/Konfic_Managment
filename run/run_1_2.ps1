Set-Location -LiteralPath $PSScriptRoot\..
$py = "python"
$vf = Join-Path (Get-Location) "vfs_min.json"
$sc = Join-Path (Get-Location) "scripts\start_1_2.txt"
Write-Host "Using VFS: $vf"
Write-Host "Script  : $sc"
& $py ".\KonfigManagment_12VAR.py" --vfs-json "$vf" --script "$sc"
