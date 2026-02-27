@echo off
chcp 65001 >nul
cd /d "%~dp0"
title UMA-Logic PRO 起動ツール

echo ==========================================
echo  UMA-Logic PRO を起動しています...
echo  この黒い画面は閉じないでください。
echo ==========================================

:: 仮想環境がある場合は有効化する（.venvの部分はご自身の環境に合わせてください）
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

:: Streamlitを起動
streamlit run app.py

pause