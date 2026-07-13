param(
    [string]$Root = $env:AUTO_ALIBABA_ROOT,
    [string]$CdpUrl = "http://127.0.0.1:9223",
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Get-Location).Path
}

function Write-Result {
    param(
        [bool]$Ok,
        [string]$Status,
        [hashtable]$Checks,
        [string]$Message,
        [int]$ExitCode
    )
    [ordered]@{
        ok = $Ok
        status = $Status
        model = $null
        checks = $Checks
        message = $Message
    } | ConvertTo-Json -Depth 6 -Compress
    exit $ExitCode
}

function Get-CdpVersion {
    try {
        return Invoke-RestMethod -Uri "$($CdpUrl.TrimEnd('/'))/json/version" -TimeoutSec 2
    }
    catch {
        return $null
    }
}

function Get-ListenerProcess {
    $connection = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort 9223 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) {
        $connection = Get-NetTCPConnection -LocalPort 9223 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    }
    if (-not $connection) {
        return $null
    }
    return Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
}

function Get-ChromeCandidates {
    @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        ForEach-Object { (Resolve-Path -LiteralPath $_).Path } |
        Select-Object -Unique
}

function Test-DedicatedChrome {
    param([object]$Version, [object]$Process, [string]$Profile)

    $candidates = @(Get-ChromeCandidates)
    $resolvedProfile = [System.IO.Path]::GetFullPath($Profile).TrimEnd('\')
    $executable = if ($Process) { [string]$Process.ExecutablePath } else { "" }
    $commandLine = if ($Process) { [string]$Process.CommandLine } else { "" }
    $executableOk = $candidates | Where-Object { $_.Equals($executable, [System.StringComparison]::OrdinalIgnoreCase) }
    $portOk = $commandLine -match '(?i)--remote-debugging-port(?:=|\s+)9223(?:\s|$)'
    $profilePattern = '(?i)--user-data-dir(?:=|\s+)["'']?' + [regex]::Escape($resolvedProfile) + '["'']?(?:\s|$)'
    $profileOk = $commandLine -match $profilePattern
    $browserOk = $Version -and ([string]$Version.Browser -match '^Chrome/') -and [bool]$Version.webSocketDebuggerUrl

    return [ordered]@{
        cdp_endpoint = [bool]$browserOk
        chrome_executable = [bool]$executableOk
        debugging_port = [bool]$portOk
        dedicated_profile = [bool]$profileOk
        process_id = if ($Process) { [int]$Process.ProcessId } else { $null }
        executable = $executable
    }
}

if ($CdpUrl -ne "http://127.0.0.1:9223") {
    Write-Result $false "BLOCKED" @{ cdp_url = $false } "Only local Google Chrome CDP 9223 is allowed." 2
}

$profile = Join-Path ([System.IO.Path]::GetFullPath($Root)) ".chrome-profile"
$version = Get-CdpVersion
$listener = Get-ListenerProcess

if ($version -or $listener) {
    $checks = Test-DedicatedChrome $version $listener $profile
    if ($checks.cdp_endpoint -and $checks.chrome_executable -and $checks.debugging_port -and $checks.dedicated_profile) {
        Write-Result $true "READY" $checks "Dedicated local Google Chrome CDP 9223 is ready." 0
    }
    Write-Result $false "BLOCKED" $checks "Port 9223 is occupied by an unexpected process or Chrome profile; it was not terminated." 3
}

$chrome = @(Get-ChromeCandidates) | Select-Object -First 1
if (-not $chrome) {
    Write-Result $false "BLOCKED" @{ chrome_found = $false } "Google Chrome was not found in a standard local installation path." 4
}

New-Item -ItemType Directory -Path $profile -Force | Out-Null
$arguments = @(
    "--remote-debugging-port=9223",
    "--user-data-dir=$profile",
    "https://work.1688.com"
)
Start-Process -FilePath $chrome -ArgumentList $arguments | Out-Null

$deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Milliseconds 250
    $version = Get-CdpVersion
    $listener = Get-ListenerProcess
    if ($version -and $listener) {
        $checks = Test-DedicatedChrome $version $listener $profile
        if ($checks.cdp_endpoint -and $checks.chrome_executable -and $checks.debugging_port -and $checks.dedicated_profile) {
            Write-Result $true "READY" $checks "Dedicated local Google Chrome CDP 9223 was started." 0
        }
    }
} while ([DateTime]::UtcNow -lt $deadline)

$finalChecks = Test-DedicatedChrome $version $listener $profile
Write-Result $false "BLOCKED" $finalChecks "Google Chrome did not expose the dedicated CDP endpoint within the timeout." 5
