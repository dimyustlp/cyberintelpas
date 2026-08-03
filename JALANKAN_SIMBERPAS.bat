@echo off
title SIMBERPAS V5.3 Internal Pusat
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python -m streamlit run app.py
) else (
  py -m streamlit run app.py
)
pause
