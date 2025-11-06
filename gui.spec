# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# --- INICIO DE LA CORRECCIÓN DE PDFMINER (para Excel en blanco) ---
try:
    import pdfminer
except ImportError:
    print("ERROR: Necesitas 'pdfminer.six' en tu venv.")
    print("Ejecuta: pip install pdfminer.six")
    sys.exit(1)

pdfminer_path = os.path.dirname(pdfminer.__file__)
pdfminer_cmap_path = os.path.join(pdfminer_path, 'cmap')
# (source, destination_relative_to_exe_root)
pdfminer_datas = (pdfminer_cmap_path, 'pdfminer/cmap')
# --- FIN DE LA CORRECCIÓN DE PDFMINER ---


# --- INICIO DE LA CONFIGURACIÓN DEL ICONO ---
app_icon_path = 'assets\\app.ico'
app_icon_datas = ('assets', 'assets') # Empaqueta toda la carpeta 'assets'
# --- FIN DE LA CONFIGURACIÓN DEL ICONO ---


# --- Configuración principal ---
block_cipher = None

a = Analysis(
    ['gui.py'],  # Tu script principal
    pathex=['C:\\Proyectos\\PDF2Excel'], # Ruta a tu proyecto
    binaries=[],
    
    datas=[
        pdfminer_datas,  # <--- CORRECCIÓN 1 (Incluye los archivos)
        app_icon_datas
    ],
    
    hiddenimports=[
        'pdfminer.six', 'pdfminer.pdfparser', 'pdfminer.pdfinterp',
        'pdfminer.pdfdevice', 'pdfminer.pdfpage', 'pdfminer.converter',
        'pdfminer.layout', 'pdfminer.cmapdb',
    ],
    
    # --- CORRECCIÓN 2: EXCLUIR IMPORTACIONES PROBLEMÁTICAS ---
    excludes=[
        'tabula', 'tabula-py', 'pytesseract', 'pdf2image'
    ],
    
    hookspath=[],
    hooksconfig={},
    
    # --- ¡¡AQUÍ ESTÁ LA LÍNEA MÁGICA!! ---
    # Esto ejecuta runtime_hook.py ANTES que gui.py
    runtime_hooks=['runtime_hook.py'],
    # --- FIN DE LA LÍNEA MÁGICA ---
    
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DataBridge', # El nombre de tu .exe
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # False = --windowed (Sin consola)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon_path, # Asigna el icono al .exe
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PDF2ExcelExtractor',
)