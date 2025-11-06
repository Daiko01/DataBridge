PDF → Excel (GUI)
=====================

Requisitos:
- Windows 10/11
- Python 3.10+ instalado con "Add to PATH"
- Conexión para instalar dependencias la primera vez

Instrucciones rápidas (crear EXE en dist\):
1) Doble clic en build_exe.bat
   - Crea .venv, instala requirements, ejecuta PyInstaller
2) Al finalizar, encontrarás el ejecutable en:
   dist\PDF2Excel.exe

Comando PyInstaller equivalente (por si prefieres manual):
  py -m PyInstaller --noconfirm --onefile --windowed --name "PDF2Excel" --icon "app.ico" --distpath "dist" gui.py

Uso de la app (GUI):
1) Presiona "Elegir PDF(s)" y selecciona uno o varios PDF
2) Elige la salida .xlsx (o deja el valor sugerido)
3) Clic en "Convertir a Excel"
4) Se generará un archivo Excel con hoja 'Datos' y columnas:
   Fecha, Maquina, Patente, Folio, Variante, Frec, Conductores, Ab, SD, CI, %, EV, TE

Toggle de tema:
- Botón ☀️/🌙 (arriba a la derecha) para alternar claro/oscuro

Notas:
- La app usa tu archivo extractors.py (función parse_pdf_any)
- El Excel se guarda SIN columna de índice (#)
