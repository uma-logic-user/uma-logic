@echo off
cd /d "C:\Users\sayaka\OneDrive\Desktop\uma-logic-new"

echo ========================================
echo   UMA-Logic PRO: Starting System...
echo ========================================

echo Backing up project files...
python scripts\backup_manager.py auto >nul 2>&1

:: 1. Check if Streamlit is installed in .venv, if not, install it
if exist ".venv\Scripts\python.exe" (
    echo Checking libraries in virtual environment...
    ".venv\Scripts\python.exe" -m pip install -U pip
    ".venv\Scripts\python.exe" -m pip install streamlit pandas numpy requests beautifulsoup4 scikit-learn lightgbm
    
    echo Launching App...
    ".venv\Scripts\python.exe" -m streamlit run app.py
) else (
    echo Virtual environment not found. Running with Global Python...
    python -m pip install -U pip
    python -m pip install streamlit pandas numpy requests beautifulsoup4 scikit-learn lightgbm
    python -m streamlit run app.py
)

pause
