@echo off
setlocal
cd /d "%~dp0\.."

set "PY=python"


set "VFS_FILE=%cd%\vfs_deep.json"
set "SCRIPT_FILE=%cd%\scripts\start_4.txt"

echo Using VFS:   %VFS_FILE%
echo Using script:%SCRIPT_FILE%
"%PY%" ".\KonfigManagment_12VAR.py" --vfs-json "%VFS_FILE%" --script "%SCRIPT_FILE%"
pause
