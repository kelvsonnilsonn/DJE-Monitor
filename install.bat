@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

cd /d "%~dp0"

set "PYTHON=%CD%\.venv\Scripts\pythonw.exe"
set "SCRIPT=%CD%\dje_monitor.py"
set "TASK_NAME=DJE Monitor"

echo.
echo ============================================
echo   DJE Monitor - Instalador
echo ============================================
echo.

:: ── 1. Verificar se pythonw.exe existe ───────────────────────────
if not exist "%PYTHON%" (
    echo [ERRO] pythonw.exe nao encontrado em:
    echo        %PYTHON%
    echo.
    echo Verifique se o virtualenv foi criado corretamente.
    pause
    exit /b 1
)

:: ── 2. Verificar se o script existe ──────────────────────────────
if not exist "%SCRIPT%" (
    echo [ERRO] dje_monitor.py nao encontrado em:
    echo        %SCRIPT%
    pause
    exit /b 1
)

:: ── 3. Verificar se já existe tarefa registrada ───────────────────
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% == 0 (
    echo [INFO] Tarefa "%TASK_NAME%" ja existe no Agendador.
    echo.
    choice /c SN /m "Deseja recriar a tarefa (S) ou apenas iniciar (N)?"
    if !errorlevel! == 2 goto :iniciar
    echo.
    echo Removendo tarefa existente...
    schtasks /delete /tn "%TASK_NAME%" /f >nul
)

:: ── 4. Registrar no Agendador de Tarefas via PowerShell ──────────
echo Registrando tarefa no Agendador de Tarefas...
echo (sera necessario permissao de administrador)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$action   = New-ScheduledTaskAction -Execute '%PYTHON%' -Argument '%SCRIPT%' -WorkingDirectory '%CD%';" ^
    "$trigger  = New-ScheduledTaskTrigger -AtLogon;" ^
    "$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2) -StartWhenAvailable;" ^
    "Register-ScheduledTask -TaskName '%TASK_NAME%' -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force -Description 'Monitora o DJE-PE e alerta quando o advogado é encontrado' | Out-Null;" ^
    "Write-Host 'Tarefa registrada com sucesso.'"

if %errorlevel% neq 0 (
    echo.
    echo [AVISO] Falha ao registrar via PowerShell.
    echo         Tente executar este .bat como Administrador.
    pause
    exit /b 1
)

echo.
echo [OK] Tarefa configurada: inicia automaticamente em todo login.
echo.

:: ── 5. Iniciar agora sem precisar reiniciar ───────────────────────
:iniciar
echo Verificando se o monitor ja esta rodando...

:: Checa se já há um pythonw rodando dje_monitor.py
wmic process where "CommandLine like '%%dje_monitor.py%%'" get ProcessId 2>nul | findstr /r "[0-9]" >nul
if %errorlevel% == 0 (
    echo [INFO] Monitor ja esta em execucao. Nenhuma acao necessaria.
    goto :fim
)

echo Iniciando DJE Monitor em segundo plano...
schtasks /run /tn "%TASK_NAME%" >nul

:: Aguarda 2 segundos e confirma que subiu
timeout /t 2 /nobreak >nul
wmic process where "CommandLine like '%%dje_monitor.py%%'" get ProcessId 2>nul | findstr /r "[0-9]" >nul
if %errorlevel% == 0 (
    echo [OK] Monitor iniciado com sucesso!
) else (
    echo [AVISO] Nao foi possivel confirmar o inicio do processo.
    echo         Verifique o arquivo dje_monitor.log para mais detalhes.
)

:: ── 6. Resumo final ───────────────────────────────────────────────
:fim
echo.
echo ============================================
echo   Configuracao concluida
echo ============================================
echo.
echo   Tarefa : %TASK_NAME%
echo   Script : %SCRIPT%
echo   Log    : %CD%\dje_monitor.log
echo.
echo   Para ver o log ao vivo, abra o PowerShell e execute:
echo   Get-Content "%CD%\dje_monitor.log" -Wait
echo.
echo   Para parar o monitor manualmente:
echo   schtasks /end /tn "%TASK_NAME%"
echo.
pause
