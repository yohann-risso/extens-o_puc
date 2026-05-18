@echo off
setlocal

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

echo.
echo App iniciado.
echo.
echo No computador, acesse:
echo http://localhost:8501
echo.
echo Para encerrar, feche esta janela ou pressione CTRL+C.
echo.

python -m streamlit run app.py --server.address localhost --server.port 8501

pause
