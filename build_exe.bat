@echo off
setlocal
echo ============================================
echo   Construyendo ejecutable PDF -> Excel
echo ============================================

if not exist .venv (
  echo Creando entorno virtual...
  py -m venv .venv
)

call .venv\Scripts\activate

.\.venv\Scripts\python.exe -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

py -m PyInstaller --noconfirm --onefile --windowed ^
  --name "PDF2Excel" ^
  --icon "app.ico" ^
  --collect-all pdfplumber ^
  --collect-all pdfminer ^
  --collect-all openpyxl ^
  --collect-all customtkinter ^
  --collect-all charset_normalizer ^
  --distpath "dist" ^
  gui.py

echo.
echo ============================================
echo   ¡Listo! Revisa: dist\PDF2Excel.exe
echo ============================================
pause
