import subprocess
import tempfile
import os

script = r"""
Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*language_server*' } | ForEach-Object {
    Write-Output "PID: $($_.ProcessId)"
    Write-Output "CMD: $($_.CommandLine)"
    Write-Output "---"
}
"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, dir=tempfile.gettempdir()) as f:
    f.write(script)
    tmppath = f.name

try:
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', tmppath],
        capture_output=True, text=True, timeout=15
    )
    print(result.stdout[:5000])
    if result.stderr:
        print('STDERR:', result.stderr[:500])
finally:
    os.unlink(tmppath)
