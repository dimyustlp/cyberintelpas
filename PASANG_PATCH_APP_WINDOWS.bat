@echo off
setlocal
echo.
echo CYBER-INTELPAS V6.0 - PATCH APP.PY
echo.
set /p PROJECT_DIR=Tempel alamat folder proyek CYBER-INTELPAS aktif lalu tekan Enter: 
if "%PROJECT_DIR%"=="" (
  echo Folder proyek belum diisi.
  pause
  exit /b 1
)
py "%~dp0scripts\apply_v6_patch.py" "%PROJECT_DIR%"
if errorlevel 1 (
  echo.
  echo Patch gagal. Buka docs\PATCH_APP_PY.md dan lakukan secara manual.
  pause
  exit /b 1
)
echo.
echo Patch selesai. Lanjutkan instalasi requirements dan jalankan aplikasi lokal.
pause
