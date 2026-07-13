param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$Root = $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()

function Add-Check {
    param([bool]$Ok, [string]$Message)
    if ($Ok) {
        Write-Host "[OK] $Message"
    }
    else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
        $Failures.Add($Message)
    }
}

$Python = Get-Command python -ErrorAction SilentlyContinue
Add-Check ($null -ne $Python) "Python command is available"
if ($null -ne $Python) {
    & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
    Add-Check ($LASTEXITCODE -eq 0) "Python is version 3.12 or newer"
}

$ChromeCandidates = @(
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
Add-Check (($ChromeCandidates | Where-Object { Test-Path -LiteralPath $_ }).Count -gt 0) "Google Chrome is installed"

foreach ($RelativePath in @(
    "pyproject.toml",
    "app\cli.py",
    "plugins\auto-alibaba\.codex-plugin\plugin.json",
    ".agents\plugins\marketplace.json"
)) {
    Add-Check (Test-Path -LiteralPath (Join-Path $Root $RelativePath)) "$RelativePath exists"
}

if ($Failures.Count -gt 0) {
    throw "Environment check failed: $($Failures -join '; ')"
}

if ($CheckOnly) {
    Write-Host "Portable project checks passed."
    exit 0
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    & python -m venv (Join-Path $Root ".venv")
}
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -e "$($Root)[dev]"
Write-Host "Setup complete. Restart Codex, install the auto-alibaba plugin, and run doctor."
