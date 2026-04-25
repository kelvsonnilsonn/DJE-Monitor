@echo off
cd /d "%~dp0"

set PYTHON=%CD%\.venv\Scripts\pythonw.exe
set SCRIPT=%CD%\dje_monitor.py
set LOG=%CD%\dje_monitor.log

echo Verificando se o DJE Monitor ja esta rodando...

REM Procura processo com pythonw.exe executando seu script
for /f "tokens=*" %%i in ('wmic process where "CommandLine like '%%dje_monitor.py%%'" get ProcessId ^| findstr [0-9]') do (
    echo DJE Monitor ja esta em execucao. PID: %%i
    exit /b
)

echo Iniciando DJE Monitor...

start "" "%PYTHON%" "%SCRIPT%" >> "%LOG%" 2>&1

echo DJE Monitor iniciado com sucesso.
exit