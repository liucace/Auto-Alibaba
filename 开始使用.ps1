$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Guide = Join-Path $Root "START-HERE.md"

Start-Process -FilePath "explorer.exe" -ArgumentList $Root
Start-Process -FilePath "notepad.exe" -ArgumentList $Guide
