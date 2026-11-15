# ==============================================================================
# 104 Management Internship - Daily Auto Sync Script
# Runs 104 crawler, analyzes pending jobs with Gemini, and pushes updates to GitHub.
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$LogsDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$Today = Get-Date -Format "yyyyMMdd"
$LogFile = Join-Path $LogsDir "daily_sync_$Today.log"

function Log-Message {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $Line = "[$Timestamp] $Message"
    Write-Host $Line
    Add-Content -Path $LogFile -Value $Line -Encoding utf8
}

Log-Message "=== Starting Daily Internship Pipeline ==="

# Resolve Python Executable
$PythonExe = $null
if (Test-Path "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe") {
    $PythonExe = "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"
} else {
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source } else { $PythonExe = "python" }
}
Log-Message "Using Python: $PythonExe"

# Resolve Git Executable
$GitExe = $null
if (Test-Path "C:\Program Files\Git\cmd\git.exe") {
    $GitExe = "C:\Program Files\Git\cmd\git.exe"
} else {
    $cmd = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($cmd) { $GitExe = $cmd.Source } else { $GitExe = "git" }
}
Log-Message "Using Git: $GitExe"

# Step 1: Run Crawler
Log-Message "Step 1: Running 104 crawler (scripts/crawler.py)..."
try {
    & $PythonExe (Join-Path $ScriptDir "scripts\crawler.py") *>> $LogFile
    Log-Message "Step 1 completed successfully."
} catch {
    Log-Message "Step 1 ERROR: $_"
}

# Step 2: Run Analyzer
Log-Message "Step 2: Running LLM analyzer (scripts/analyzer.py)..."
try {
    & $PythonExe (Join-Path $ScriptDir "scripts\analyzer.py") *>> $LogFile
    Log-Message "Step 2 completed successfully."
} catch {
    Log-Message "Step 2 ERROR: $_"
}

# Step 3: Git Commit & Push
Log-Message "Step 3: Checking Git changes..."
try {
    & $GitExe add -A (Join-Path $ScriptDir "data")
    $gitStatus = & $GitExe status --porcelain
    if ($gitStatus) {
        Log-Message "Changes detected in data, committing and pushing..."
        & $GitExe commit -am "chore(data): daily auto sync" *>> $LogFile
        & $GitExe push origin main *>> $LogFile
        Log-Message "Step 3: Successfully committed and pushed to origin/main."
    } else {
        Log-Message "Step 3: No new data changes detected. Git push skipped."
    }
} catch {
    Log-Message "Step 3 ERROR: $_"
}

Log-Message "=== Daily Internship Pipeline Finished ==="
