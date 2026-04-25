@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================
echo   Gerando pacote limpo do DJE Monitor
echo ============================================
echo.

:: Pasta de saída
set "OUTPUT=DJE-Monitor"

:: Remove pacote antigo
if exist "%OUTPUT%" (
    echo Limpando pacote anterior...
    rmdir /s /q "%OUTPUT%"
)

:: Cria estrutura
mkdir "%OUTPUT%"
mkdir "%OUTPUT%\script"

:: Copia arquivos principais
echo Copiando arquivos principais...
copy "install.bat" "%OUTPUT%" >nul
copy "start.bat" "%OUTPUT%" >nul
copy "stop.bat" "%OUTPUT%" >nul
copy "leia-me.txt" "%OUTPUT%" >nul

:: Copia scripts
echo Copiando scripts...
copy "script\dje_monitor.py" "%OUTPUT%\script" >nul
copy "script\email_handler.py" "%OUTPUT%\script" >nul

:: Copia .env (se existir)
if exist "script\.env" (
    copy "script\.env" "%OUTPUT%\script" >nul
)

:: Copia .venv (com exclusões)
echo Copiando ambiente virtual (isso pode demorar)...

robocopy "script\.venv" "%OUTPUT%\script\.venv" /E /XD __pycache__ /XF *.log *.pem *accessKeys.csv >nul

echo.
echo ============================================
echo   Pacote gerado com sucesso!
echo ============================================
echo.
echo Pasta: %OUTPUT%
echo.
pause