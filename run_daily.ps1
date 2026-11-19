# Local fallback for the daily internship pipeline.

$ErrorActionPreference = "Stop"
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
$LogsDir = Join-Path $ScriptDir "logs"
New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
$LogFile = Join-Path $LogsDir ("daily_sync_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Log-Message {
    param([string]$Message)
    $Line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $Line
    Add-Content -LiteralPath $LogFile -Value $Line -Encoding UTF8
}

function Invoke-PythonStep {
    param([string]$Label, [string[]]$Arguments)
    Log-Message "Starting $Label"
    & $PythonExe @Arguments *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
    Log-Message "Completed $Label"
}

$LockHandle = $null
$ExitCode = 0
try {
    $LockPath = Join-Path $LogsDir "daily_sync.lock"
    $LockHandle = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    Log-Message "Starting daily internship pipeline"

    $PythonExe = (Get-Command python.exe -ErrorAction Stop).Source
    & $PythonExe --version *>> $LogFile
    if ($LASTEXITCODE -ne 0) { throw "Python is unavailable" }
    $GitExe = (Get-Command git.exe -ErrorAction Stop).Source

    $Branch = (& $GitExe branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or $Branch -ne "main") {
        throw "Local sync requires the main branch"
    }
    $Ahead = & $GitExe rev-list --count origin/main..HEAD
    if ($LASTEXITCODE -ne 0 -or [int]$Ahead -ne 0) {
        throw "Local branch contains commits that need review before data sync"
    }
    $Preexisting = & $GitExe status --porcelain -- data/ backup/
    if ($LASTEXITCODE -ne 0 -or $Preexisting) {
        throw "Data or backup files already have unreviewed local changes"
    }

    Invoke-PythonStep -Label "pipeline tests" -Arguments @("-m", "unittest", "discover", "-s", "tests", "-v")
    Invoke-PythonStep -Label "published baseline quality gate" -Arguments @("scripts/quality_gate.py")
    Invoke-PythonStep -Label "104 crawler" -Arguments @("scripts/crawler.py")
    Invoke-PythonStep -Label "Gemini analyzer" -Arguments @("scripts/analyzer.py")
    Invoke-PythonStep -Label "data quality gate" -Arguments @("scripts/quality_gate.py")
    Invoke-PythonStep -Label "data backup" -Arguments @("scripts/pipeline.py", "--backup")
    Invoke-PythonStep -Label "backup quality gate" -Arguments @("scripts/quality_gate.py")

    & $GitExe add -A -- data/ backup/
    if ($LASTEXITCODE -ne 0) { throw "Git staging failed" }
    $Changed = & $GitExe diff --cached --name-only -- data/ backup/
    if ($LASTEXITCODE -ne 0) { throw "Git diff failed" }
    if ($Changed) {
        & $GitExe commit --only -m "chore(data): daily auto sync" -- data/ backup/ *>> $LogFile
        if ($LASTEXITCODE -ne 0) { throw "Git commit failed" }
        & $GitExe push origin main *>> $LogFile
        if ($LASTEXITCODE -ne 0) { throw "Git push failed" }
        Log-Message "Committed and pushed validated data"
    } else {
        Log-Message "No data changes to publish"
    }
    Invoke-PythonStep -Label "Google Sheets sync" -Arguments @("scripts/sync_to_sheets.py")
    Log-Message "Daily internship pipeline finished"
} catch {
    $ExitCode = 1
    Log-Message "Daily internship pipeline failed: $_"
} finally {
    if ($LockHandle) { $LockHandle.Dispose() }
}
exit $ExitCode
