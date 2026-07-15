param(
    [string]$Model,
    [switch]$Open
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$Root = $PSScriptRoot

function Write-SetupState {
    param([string]$Check, [string]$Action)
    [ordered]@{
        ok = $false
        status = "NEEDS_SETUP"
        model = if ([string]::IsNullOrWhiteSpace($Model)) { $null } else { $Model }
        checks = [ordered]@{ failed = $Check }
        paths = [ordered]@{ project_root = $Root }
        next_action = $Action
        message = $Action
    } | ConvertTo-Json -Compress -Depth 5
    exit 0
}

foreach ($RelativePath in @("pyproject.toml", "app\cli.py")) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $RelativePath))) {
        Write-SetupState "project_file" "项目文件 $RelativePath 缺失；请重新完整拉取项目。"
    }
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    $Python = $VenvPython
}
else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        Write-SetupState "python" "请先安装 Python 3.12 或更高版本，安装后告诉我'已安装'。"
    }
    $Python = $PythonCommand.Source
}

& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-SetupState "python_version" "当前 Python 版本低于 3.12；请安装 Python 3.12 或更高版本。"
}

$ChromeCandidates = @(
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
if (($ChromeCandidates | Where-Object { Test-Path -LiteralPath $_ }).Count -eq 0) {
    Write-SetupState "chrome" "请先安装 Google Chrome，安装后告诉我'已安装'。"
}

$PreviousLocation = Get-Location
Set-Location $Root
try {
    & $Python -c "import app.cli"
    $ImportExitCode = $LASTEXITCODE
}
finally {
    Set-Location $PreviousLocation
}
if ($ImportExitCode -ne 0) {
    Write-SetupState "dependencies" "项目依赖尚未安装；请让智能体运行根目录 setup.ps1。"
}

$Arguments = @("-m", "app.cli", "onboard", "--root", $Root)
if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $Arguments += @("--model", $Model)
}
if ($Open) {
    $Arguments += "--open"
}

Push-Location $Root
try {
    & $Python @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
