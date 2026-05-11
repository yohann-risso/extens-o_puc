@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ===============================================
echo  Organizacao Financeira na Pratica
echo ===============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado.
    echo Instale o Python em https://www.python.org/downloads/
    echo Durante a instalacao, marque a opcao "Add Python to PATH".
    pause
    exit /b 1
)

echo Instalando ou conferindo dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Nao foi possivel instalar as dependencias.
    pause
    exit /b 1
)

set "LOCAL_IP="
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /C:"IPv4"') do (
    if not defined LOCAL_IP (
        set "LOCAL_IP=%%A"
        set "LOCAL_IP=!LOCAL_IP: =!"
    )
)

echo.
echo App iniciado.
echo.
echo No computador, acesse:
echo http://localhost:8501
echo.
if defined LOCAL_IP (
    echo No celular, conectado ao mesmo Wi-Fi, acesse:
    echo http://!LOCAL_IP!:8501
    echo.
)
echo Para encerrar, feche esta janela ou pressione CTRL+C.
echo.

python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501

pause
