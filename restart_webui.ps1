param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$logsDir = Join-Path $projectRoot "logs"
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$stdoutLog = Join-Path $logsDir "webui.stdout.log"
$stderrLog = Join-Path $logsDir "webui.stderr.log"

function Get-PythonLaunchConfig {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @{
            FilePath = $python.Source
            Arguments = @("webui.py", "--host", $BindHost, "--port", $Port)
        }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @{
            FilePath = $py.Source
            Arguments = @("-3", "webui.py", "--host", $BindHost, "--port", $Port)
        }
    }

    throw "Python was not found. Please install Python or add python to PATH."
}

function Stop-ExistingWebUi {
    $stoppedPids = New-Object System.Collections.Generic.List[int]
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe'"

    foreach ($process in $processes) {
        $commandLine = $process.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) {
            continue
        }

        if ($commandLine -like "*$projectRoot*" -and $commandLine -match "webui\.py") {
            Write-Host "Found existing Web UI process. Stopping PID $($process.ProcessId)..."
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
            $stoppedPids.Add([int]$process.ProcessId) | Out-Null
        }
    }

    Start-Sleep -Seconds 1

    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($listenerPid in $listeners) {
        if ($stoppedPids.Contains([int]$listenerPid)) {
            continue
        }

        Write-Host "Port $Port is still occupied by PID $listenerPid. Stopping it now..."
        Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        $stoppedPids.Add([int]$listenerPid) | Out-Null
    }

    if ($stoppedPids.Count -eq 0) {
        Write-Host "No existing Web UI process found. Starting a fresh instance..."
    } else {
        Write-Host "Stopped old process IDs: $($stoppedPids -join ', ')"
    }
}

$launchConfig = Get-PythonLaunchConfig
Stop-ExistingWebUi

if (Test-Path $stdoutLog) {
    Remove-Item $stdoutLog -Force -ErrorAction SilentlyContinue
}

if (Test-Path $stderrLog) {
    Remove-Item $stderrLog -Force -ErrorAction SilentlyContinue
}

$process = Start-Process `
    -FilePath $launchConfig.FilePath `
    -ArgumentList $launchConfig.Arguments `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 3

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) {
    Write-Host "Startup failed. Please check the log files below:" -ForegroundColor Red
    Write-Host "stdout: $stdoutLog"
    Write-Host "stderr: $stderrLog"

    if (Test-Path $stderrLog) {
        Get-Content -Path $stderrLog -Tail 40
    }

    exit 1
}

Write-Host ""
Write-Host "Web UI started successfully." -ForegroundColor Green
Write-Host "PID: $($process.Id)"
Write-Host "URL: http://localhost:$Port"
Write-Host "Logs: http://localhost:$Port/logs"
Write-Host "stdout: $stdoutLog"
Write-Host "stderr: $stderrLog"
