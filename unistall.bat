@echo off
chcp 65001 >nul
setlocal

set "TASK_NAME=DJE Monitor"

echo Removendo DJE Monitor...

schtasks /end /tn "%TASK_NAME%" >nul 2>&1
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

echo [OK] Monitor removido do sistema.
pause