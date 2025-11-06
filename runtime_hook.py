# runtime_hook.py
import os
import sys

"""
Este script se ejecuta ANTES que tu gui.py.
Su única misión es decirle a la librería pdfminer dónde están
sus archivos 'cmap' (mapas de caracteres) cuando el programa
está empaquetado en un .exe.
"""

if getattr(sys, 'frozen', False):
    # Estamos ejecutando en el .exe (empaquetado)
    try:
        # sys._MEIPASS es la carpeta temporal donde PyInstaller
        # descomprime todo.
        base_path = sys._MEIPASS
        
        # Nuestros 'datas' en el .spec pusieron los cmaps en 'pdfminer/cmap'
        cmap_path = os.path.join(base_path, 'pdfminer', 'cmap')
        
        # Establecemos la variable de entorno que pdfminer busca
        os.environ['PDFMINER_cmapdb'] = cmap_path
        
        # print(f"Hook: PDFMINER_cmapdb seteado a {cmap_path}")
        
    except Exception as e:
        print(f"Error en runtime_hook: {e}")