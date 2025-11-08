# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# --- INICIO DE RUTAS ROBUSTAS ---
# project_root será la carpeta donde está este archivo .spec (ej: C:\Proyectos\DataBridge)
project_root = os.getcwd()
src_dir = os.path.join(project_root, 'src')
# --- FIN DE RUTAS ROBUSTAS ---


# --- INICIO DE LA CORRECCIÓN DE PDFMINER (para Excel en blanco) ---
try:
    import pdfminer
except ImportError:
    print("ERROR: Necesitas 'pdfminer.six' en tu venv.")
    print("Ejecuta: pip install pdfminer.six")
    sys.exit(1)

pdfminer_path = os.path.dirname(pdfminer.__file__)
pdfminer_cmap_path = os.path.join(pdfminer_path, 'cmap')
pdfminer_datas = (pdfminer_cmap_path, 'pdfminer/cmap')
# --- FIN DE LA CORRECCIÓN DE PDFMINER ---


# --- INICIO DE LA CONFIGURACIÓN DEL ICONO ---
# Usamos las rutas robustas
app_icon_path = os.path.join(project_root, 'assets', 'app.ico')
app_icon_datas = (os.path.join(project_root, 'assets'), 'assets') # Empaqueta toda la carpeta 'assets'
# --- FIN DE LA CONFIGURACIÓN DEL ICONO ---


# --- Configuración principal ---
block_cipher = None

a = Analysis(
  
    [os.path.join(src_dir, 'gui.py')],  # <-- MODIFICADO: Apunta al script dentro de src/
  
    pathex=[
        project_root, # <-- MODIFICADO: Añadimos el root (para el hook)
        src_dir       # <-- MODIFICADO: Añadimos src/ (para los imports)
    ],
  
    binaries=[],
    
    datas=[
        pdfminer_datas, 
        app_icon_datas    # <-- MODIFICADO: Usa la variable robusta
    ],
    
    hiddenimports=[
        'pdfminer.six', 'pdfminer.pdfparser', 'pdfminer.pdfinterp',
        'pdfminer.pdfdevice', 'pdfminer.pdfpage', 'pdfminer.converter',
        'pdfminer.layout', 'pdfminer.cmapdb',
        'requests',
        'packaging', 'packaging.version' # <-- ¡AÑADIDO! Para el auto-updater moderno
    ],
    
    # --- EXCLUIR IMPORTACIONES PROBLEMÁTICAS ---
    excludes=[
        'tabula', 'tabula-py', 'pytesseract', 'pdf2image'
    ],
    
    hookspath=[],
    hooksconfig={},
    
    # <-- MODIFICADO: Usa la ruta robusta para el hook
    runtime_hooks=[os.path.join(project_root, 'runtime_hook.py')],
    
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
  
    icon=app_icon_path, # <-- MODIFICADO: Usa la variable robusta
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DataBridge',
)