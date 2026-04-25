@echo off
chcp 65001 >nul
setlocal

set "TASK_NAME=DJE Monitor"

echo.
echo ============================================
echo   Parando DJE Monitor
echo ============================================
echo.

:: ── 1. Verificar se a tarefa existe ────────────
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Tarefa "%TASK_NAME%" nao encontrada.
    echo.
    echo Verifique se o monitor foi instalado corretamente.
    pause
    exit /b 1
)

:: ── 2. Verificar se está rodando ───────────────
wmic process where "CommandLine like '%%dje_monitor.py%%'" get ProcessId 2>nul | findstr /r "[0-9]" >nul
if %errorlevel% neq 0 (
    echo [INFO] Monitor ja esta parado.
    goto :fim
)

:: ── 3. Parar tarefa ────────────────────────────
echo Encerrando tarefa...
schtasks /end /tn "%TASK_NAME%" >nul 2>&1

:: ── 4. Confirmar se parou ──────────────────────
timeout /t 2 /nobreak >nul
wmic process where "CommandLine like '%%dje_monitor.py%%'" get ProcessId 2>nul | findstr /r "[0-9]" >nul

if %errorlevel% neq 0 (
    echo [OK] Monitor parado com sucesso!
) else (
    echo [AVISO] Nao foi possivel confirmar o encerramento.
    echo         Tente fechar manualmente pelo Gerenciador de Tarefas.
)

:fim
echo.
echo ============================================
echo   Operacao concluida
echo ============================================
echo.
pause