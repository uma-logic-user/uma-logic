@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   🏇 UMA Logic PRO 起動 (軽量復旧版)
echo ========================================

:: 1. 仮想環境を有効化 (OneDriveパス対策)
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

:: 2. Streamlitを確実に起動 (ポートは標準の8501に戻します)
echo 🚀 システムを立ち上げています...
python -m streamlit run app.py --server.port 8501

pause