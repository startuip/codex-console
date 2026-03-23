from pathlib import Path


def test_restart_batch_script_exists_and_calls_powershell():
    script = Path("restart_webui.bat").read_text(encoding="utf-8")

    assert 'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart_webui.ps1" %*' in script
    assert 'cd /d "%~dp0"' in script


def test_restart_powershell_script_handles_stop_and_restart():
    script = Path("restart_webui.ps1").read_text(encoding="utf-8")

    assert 'function Stop-ExistingWebUi' in script
    assert 'Get-NetTCPConnection -LocalPort $Port -State Listen' in script
    assert 'Stop-Process -Id $process.ProcessId -Force' in script
    assert 'Start-Process' in script
    assert 'webui.py", "--host", $BindHost, "--port", $Port' in script
