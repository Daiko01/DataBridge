# gui.py (v3.2.1 - Release Pública Estable)
import os
import sys
import traceback
import importlib.util  # Para la carga forzada

# --- INICIO: ARREGLO DE SYS.PATH (HOTFIX v3.4.4) ---
# Mantenemos esto, ya que tu entorno sys.path está roto.
def get_base_path():
    """ Obtiene la ruta base (para .exe o script) """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

APP_ROOT = get_base_path()

def _candidate_site_packages(root: str):
    cands = []
    if sys.platform == "win32":
        cands.append(os.path.join(root, ".venv", "Lib", "site-packages"))
        cands.append(os.path.join(root, ".venv", "lib", "site-packages"))
    else:
        pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        cands.append(os.path.join(root, ".venv", "lib", pyver, "site-packages"))
        cands.append(os.path.join(root, ".venv", "lib", "site-packages"))

    return cands

for _p in _candidate_site_packages(APP_ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
# --- FIN: ARREGLO DE SYS.PATH ---


import tkinter.filedialog as fd
import tkinter.messagebox as mb
from typing import List
import threading
import queue
import json
import requests     # Para el auto-updater
import subprocess   # Para el auto-updater
from packaging.version import Version # Reemplazo moderno de distutils

try:
    import customtkinter as ctk
    _ = ctk.CTkToplevel 
except (ImportError, AttributeError) as e:
    mb.showerror("Error Crítico de ImportACIÓN", 
                 f"No se pudo cargar 'customtkinter' correctamente.\n\n"
                 f"Error: {e}\n\n"
                 f"Por favor, asegÚrate de que esté instalado (pip install customtkinter>=5.2.0)")
    sys.exit(1)
    
import pandas as pd

APP_NAME = "DataBridge"
DEFAULT_OUT = "Tablas_Extraidas.xlsx"

# --- Lógica de Versión y Actualización ---
# CORREGIDO: Alineado con la release pública de GitHub
APP_CURRENT_VERSION = "v3.2.1" 
GITHUB_REPO_API = "https://api.github.com/repos/daiko01/DataBridge/releases/latest"
# --- FIN ---

# --- LÓGICA DE RUTAS ROBUSTA (Usada por el icono y logs) ---
ICON_PATH = os.path.join(APP_ROOT, "assets", "app.ico")
# --- FIN: LÓGICA DE RUTAS ---


# --- Lógica de Configuración ---
try:
    APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
except TypeError:
    APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".DataBridge")
    
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')

def _load_config() -> dict:
    """Carga el config.json si existe."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def _save_config(config_data: dict):
    """Guarda el diccionario de config en el config.json."""
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Advertencia: No se pudo guardar la configuración: {e}")
# --- FIN LÓGICA DE CONFIGURACIÓN ---


# ===== Log de errores (Útil para producción) =====
def _log_error(e, tb_text):
    """Guarda el traceback en un archivo para depurar el .exe"""
    log_filename = "CONVERSION_ERROR.log"
    try:
        log_path = os.path.join(APP_ROOT, log_filename)
        
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Ha ocurrido un error durante la conversión:\n\n")
            f.write(f"Error: {e}\n\n")
            f.write("="*50 + "\n")
            f.write("Traceback:\n")
            f.write(tb_text)
        
        if "No se pudo guardar el archivo" not in tb_text and "No se pudo leer el archivo" not in tb_text:
            mb.showerror(
                "Error", 
                f"Ocurrió un problema:\n{e}\n\n"
                f"Se guardó un log detallado en:\n{log_path}"
            )
    except Exception as log_e:
        mb.showerror(
            "Error Crítico", 
            f"Ocurrió un error:\n{e}\n\n"
            f"Además, no se pudo escribir el archivo de log por:\n{log_e}"
        )

# ===== Importar Extractor =====
try:
    import extractors
    from extractors import ExtractedRow
    _import_err = None
except Exception as e:
    extractors = None
    ExtractedRow = None
    _import_err = e

# Columnas objetivo (mantener)
TARGET_COLS = [
    "Fecha", "Maquina", "Patente", "Folio", "Variante", "Frec",
    "Conductores", "Ab", "SD", "CI", "%", "EV", "TE"
]

# ===== Lógica de Extracción y Cálculo =====
def _normalize_percent(v):
    if v is None or v == "":
        return None
    s = str(v).replace(",", ".").strip()
    if s.endswith("%"):
        return s
    try:
        float(s)
        return s + "%"
    except:
        return s

def _rows_to_df(rows: list[ExtractedRow]) -> pd.DataFrame:
    """Crea el DataFrame y se asegura de que sea 100% TEXTO."""
    mapped = []
    for r in rows:
        mapped.append({
            "Fecha": r.get("Fecha"),
            "Maquina": r.get("Máquina"),
            "Patente": r.get("Patente"),
            "Folio": r.get("Folio"),
            "Variante": r.get("Variante"),
            "Frec": r.get("Frecuencia"),
            "Conductores": r.get("Conductor"),
            "Ab": r.get("AB"),
            "SD": r.get("SD"),
            "CI": r.get("CI"),
            "%": _normalize_percent(r.get("%")),
            "EV": r.get("EV"),
            "TE": r.get("TE"),
        })
    df = pd.DataFrame(mapped, columns=TARGET_COLS)
    
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace(r"\.0$", "", regex=True)
        df[col] = df[col].str.replace(r"\s+", " ", regex=True).str.strip()
        df[col] = df[col].replace({"None": "", "nan": ""})
            
    return df

def _calculate_vueltas(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula el resumen de vueltas."""
    if df.empty:
        return pd.DataFrame(columns=["Patente", "Maquina", "Total Vueltas"])

    try:
        resumen = df.groupby(['Patente', 'Maquina'])['Folio'].count()
        resumen_df = resumen.reset_index(name='Total Vueltas')
        resumen_df = resumen_df.sort_values(by='Total Vueltas', ascending=False)
        return resumen_df
        
    except Exception as e:
        print(f"Error al calcular resumen: {e}")
        return pd.DataFrame(columns=["Patente", "Maquina", "Total Vueltas"])

def run_extraction(pdf_paths: list[str], out_path: str, progress_callback, is_append_mode: bool) -> tuple[int, int]:
    """Ejecuta la extracción y cálculos (Optimizado en Memoria)."""
    if not extractors:
        raise RuntimeError(f"No se pudo importar 'extractors.py': {_import_err}")
    
    df_final = pd.DataFrame(columns=TARGET_COLS)
    len_inicial = 0

    if is_append_mode:
        if not os.path.exists(out_path):
            raise FileNotFoundError(f"No se encontró el archivo '{os.path.basename(out_path)}' para añadir datos.")
        
        progress_callback(0.0, f"Leyendo {os.path.basename(out_path)}...")
        try:
            df_final = pd.read_excel(out_path, sheet_name="Datos", dtype=str)
            
            for col in df_final.columns:
                df[col] = df_final[col].astype(str).str.replace(r"\.0$", "", regex=True)
                df[col] = df_final[col].str.replace(r"\s+", " ", regex=True).str.strip()
                df[col] = df[col].replace({"None": "", "nan": ""})

        except Exception as e:
            if "Permission denied" in str(e):
                 raise PermissionError(f"No se pudo leer el archivo. ¿Está '{os.path.basename(out_path)}' abierto?")
            raise ValueError(f"No se pudo leer la hoja 'Datos' del Excel. ¿Es el archivo correcto?\nError: {e}")
        
        df_final = df_final.reindex(columns=TARGET_COLS)
        len_inicial = len(df_final)

    total_files = len(pdf_paths)
    for i, p in enumerate(pdf_paths):
        progress_val = (i + 1) / max(1, total_files) * 0.8
        progress_callback(progress_val, f"Procesando {os.path.basename(p)} ({i+1}/{total_files})...")
        
        rows, by_page, method = extractors.parse_pdf_any(p, use_ocr=False)
        if not rows:
            continue
        
        df_current_pdf = _rows_to_df(rows) 
        
        if not df_current_pdf.empty:
            df_final = pd.concat([df_final, df_current_pdf], ignore_index=True)

    if df_final.empty:
        return 0, 0 

    progress_callback(0.85, "Combinando datos y eliminando duplicados...")
    df_final.drop_duplicates(inplace=True)
    
    len_final = len(df_final)
    filas_netas_añadidas = len_final - len_inicial
    filas_totales = len_final
    
    if filas_totales == 0:
        return 0, 0

    progress_callback(0.9, "Calculando resumen de vueltas...")
    df_resumen = _calculate_vueltas(df_final) 

    progress_callback(0.95, "Guardando archivo Excel...")
    try:
        with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
            df_final.to_excel(writer, sheet_name='Datos', index=False)
            df_resumen.to_excel(writer, sheet_name='Resumen Vueltas', index=False)
    except PermissionError:
        raise PermissionError(f"No se pudo guardar el archivo. ¿Está '{os.path.basename(out_path)}' abierto?")
    except Exception as e:
        raise e

    return filas_netas_añadidas, filas_totales

# --- DIÁLOGO DE ÉXITO (basado en CTkToplevel, tu fix) ---
class SuccessDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, msg_summary, file_path, folder_path):
        super().__init__(parent)
        self.title(title)
        self.folder_path = folder_path
        self.geometry("550x220")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        try:
            if os.path.isfile(ICON_PATH):
                self.iconbitmap(ICON_PATH)
        except Exception:
            pass

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        msg_label = ctk.CTkLabel(
            main_frame, text=msg_summary,
            font=ctk.CTkFont(size=16),
            wraplength=500, justify="left", anchor="w"
        )
        msg_label.pack(pady=(0, 10), fill="x")

        path_label = ctk.CTkLabel(
            main_frame, text="Archivo guardado en:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        path_label.pack(pady=(10, 0), fill="x")

        path_entry = ctk.CTkEntry(main_frame)
        path_entry.insert(0, file_path)
        path_entry.configure(state="readonly")
        path_entry.pack(pady=(5, 20), fill="x")

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x")

        close_btn = ctk.CTkButton(
            button_frame, text="Cerrar",
            command=self._close,
            fg_color=("gray75", "gray25"),
            text_color=("gray10", "gray90"),
            hover_color=("gray85", "gray35")
        )
        close_btn.pack(side="right", padx=0)

        open_btn = ctk.CTkButton(
            button_frame, text="Abrir Carpeta",
            command=self.open_folder,
            font=ctk.CTkFont(weight="bold")
        )
        open_btn.pack(side="right", padx=(0, 10))

        self.after(100, open_btn.focus_set)
        self.bind("<Return>", lambda e: self._close())
        self.bind("<Escape>", lambda e: self._close())

        try:
            self.update_idletasks()
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def open_folder(self):
        if self.folder_path and os.path.exists(self.folder_path):
            try:
                os.startfile(self.folder_path)
            except Exception as e:
                mb.showerror("Error", f"No se pudo abrir la carpeta:\n{e}", parent=self)
        self._close()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


# ===== UI MODERNA v3.5.1 (Flujo "Task-First" Corregido) =====
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.config_data = _load_config()
        self.theme_mode = self.config_data.get("theme_mode", "light")
        ctk.set_appearance_mode(self.theme_mode)

        self.title(APP_NAME)
        self.geometry("800x600")
        self.minsize(720, 580)
        try:
            if os.path.isfile(ICON_PATH):
                self.iconbitmap(ICON_PATH)
        except Exception:
            pass

        self.pdf_paths: List[str] = []
        self.last_output_folder: str | None = self.config_data.get("last_output_folder")
        self.progress_queue: queue.Queue | None = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 1. Sidebar (Panel Izquierdo - SÓLO GLOBAL) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.title_lbl = ctk.CTkLabel(
            self.sidebar_frame, text=APP_NAME,
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_lbl.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.appearance_label = ctk.CTkLabel(
            self.sidebar_frame, text="Modo Oscuro:", anchor="w"
        )
        self.appearance_label.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.theme_switch = ctk.CTkSwitch(
            self.sidebar_frame, text="",
            command=self.toggle_theme
        )
        self.theme_switch.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="w")
        if self.theme_mode == "dark":
            self.theme_switch.select()
        
        self.version_label = ctk.CTkLabel(
            self.sidebar_frame, text=APP_CURRENT_VERSION,
            font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.version_label.grid(row=7, column=0, padx=20, pady=(0, 10), sticky="w")


        # --- 2. Panel Principal (Derecha - TODO EL FLUJO) ---
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # --- PASO 1: ¿QUÉ DESEAS HACER? ---
        step1_label = ctk.CTkLabel(self.main_frame, text="Paso 1: ¿Qué deseas hacer?", font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        step1_label.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        self.mode_segmented_btn = ctk.CTkSegmentedButton(
            self.main_frame,
            values=["Crear Excel Nuevo", "Añadir a Excel Existente"],
            command=self.toggle_mode
        )
        self.mode_segmented_btn.set("Crear Excel Nuevo")
        self.mode_segmented_btn.grid(row=1, column=0, sticky="ew", pady=(5, 15))

        
        # --- Frame para PASO DE SALIDA (Guardar Como / Abrir) ---
        self.step_output_frame = ctk.CTkFrame(self.main_frame)
        self.step_output_frame.grid_columnconfigure(1, weight=1)

        self.step_output_label = ctk.CTkLabel(
            self.step_output_frame, text="Paso X",
            font=ctk.CTkFont(size=16, weight="bold"), anchor="w"
        )
        self.step_output_label.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 5), padx=10)

        self.out_label = ctk.CTkLabel(self.step_output_frame, text="Guardar Excel como:")
        self.out_label.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="w")

        self.out_entry = ctk.CTkEntry(self.step_output_frame, placeholder_text=DEFAULT_OUT)
        self.out_entry_var = ctk.StringVar()
        self.out_entry.configure(textvariable=self.out_entry_var)
        self.out_entry.grid(row=1, column=1, padx=5, pady=10, sticky="ew")

        self.out_btn = ctk.CTkButton(
            self.step_output_frame, text="Examinar…",
            width=120, command=self.pick_output
        )
        self.out_btn.grid(row=1, column=2, padx=(5, 10), pady=10, sticky="e")
        
        # --- Frame para PASO DE PDFs ---
        self.step_pdf_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")

        self.step_pdf_label = ctk.CTkLabel(self.step_pdf_frame, text="Paso X: Seleccionar Archivos", font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        self.step_pdf_label.pack(fill="x", pady=(0, 5))
        
        self.pick_btn = ctk.CTkButton(
            self.step_pdf_frame, text="Añadir PDF(s)",
            command=self.pick_pdfs
        )
        self.pick_btn.pack(side="left", padx=(0, 10))

        self.clear_btn = ctk.CTkButton(
            self.step_pdf_frame, text="Limpiar Lista",
            command=self.clear_list, 
            fg_color=("gray75", "gray25"), 
            text_color=("gray10", "gray90"), 
            hover_color=("gray85", "gray35") 
        )
        self.clear_btn.pack(side="left")

        # --- Frame para PASO DE COLA DE ARCHIVOS ---
        self.step_queue_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.step_queue_label = ctk.CTkLabel(self.step_queue_frame, text="Paso X: Archivos en Cola", font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        self.step_queue_label.pack(fill="x", pady=(10, 5))
        
        self.files_scrollable_frame = ctk.CTkScrollableFrame(
            self.step_queue_frame, border_width=1, border_color=("gray85", "gray25"), height=150
        )
        self.files_scrollable_frame.pack(fill="x", expand=True, pady=(0, 15))
        
        self.initial_list_label = ctk.CTkLabel(
            self.files_scrollable_frame, text="Archivos seleccionados aparecerán aquí..."
        )
        self.initial_list_label.pack(pady=10)
        
        # --- Frame para PASO FINAL: CONVERTIR ---
        self.step_convert_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        self.step_convert_label = ctk.CTkLabel(self.step_convert_frame, text="Paso X: Convertir", font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
        self.step_convert_label.pack(fill="x", pady=(10, 5))
        
        self.convert_btn = ctk.CTkButton(
            self.step_convert_frame, text="Convertir a Excel",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=40, command=self.on_convert_click
        )
        self.convert_btn.pack(fill="x", pady=(5, 10))

        self.status_label = ctk.CTkLabel(self.step_convert_frame, text="Listo.", anchor="w")
        self.status_label.pack(fill="x", padx=5)

        self.progress_bar = ctk.CTkProgressBar(self.step_convert_frame)
        self.progress_bar.pack(fill="x", pady=(5, 15))
        self.progress_bar.set(0)

        # --- Chequeo inicial ---
        if not extractors:
            mb.showwarning(
                "Extractor no encontrado",
                f"No se pudo importar 'extractors.py'.\n\nDetalles: {_import_err}"
            )
        
        self.check_for_updates()
        self.toggle_mode("Crear Excel Nuevo")

    # ==========================================================
    #  EL RESTO DE FUNCIONES DE LA CLASE
    # ==========================================================

    # --- FUNCIÓN "GUARDIA" (v3.5.1 - CORREGIDA) ---
    def _update_ui_state(self):
        """
        HABILITA/DESHABILITA y REORDENA los pasos de la GUI 
        basado en el modo seleccionado.
        """
        mode = self.mode_segmented_btn.get()
        has_files = bool(self.pdf_paths)
        has_output_path = bool(self.out_entry_var.get().strip())
        
        self.step_output_frame.grid_remove()
        self.step_pdf_frame.grid_remove()
        self.step_queue_frame.grid_remove()
        self.step_convert_frame.grid_remove()
        
        current_row = 2

        if mode == "Crear Excel Nuevo":
            # --- Flujo CREAR ---
            self.step_pdf_label.configure(text="Paso 2: Seleccionar Archivos PDF")
            self.step_queue_label.configure(text="Paso 3: Archivos en Cola")
            self.step_output_label.configure(text="Paso 4: Guardar Excel Como...")
            self.step_convert_label.configure(text="Paso 5: Convertir")
            
            self.out_label.configure(text="Guardar Excel como:")
            self.out_btn.configure(text="Examinar…")
            self.convert_btn.configure(text="Crear Excel Nuevo")
            
            # 2. Reordenar
            self.step_pdf_frame.grid(row=current_row, column=0, sticky="ew", pady=(0, 15)); current_row += 1
            self.step_queue_frame.grid(row=current_row, column=0, sticky="ew"); current_row += 1
            self.step_output_frame.grid(row=current_row, column=0, sticky="ew", pady=(0, 15)); current_row += 1
            self.step_convert_frame.grid(row=current_row, column=0, sticky="ew"); current_row += 1
            
            # 3. Habilitar/Deshabilitar (LÓGICA CORREGIDA)
            self.pick_btn.configure(state="normal")
            self.clear_btn.configure(state="normal")
            
            # Paso 4 (Salida) SIEMPRE habilitado en "Crear Excel Nuevo" (mejor UX)
            self.out_label.configure(state="normal")
            self.out_entry.configure(state="normal")
            self.out_btn.configure(state="normal")
            
            # Paso 5 (Convertir) solo si hay PDFs Y Salida
            state_step5 = "normal" if (has_files and has_output_path) else "disabled"
            self.convert_btn.configure(state=state_step5)

        else: # mode == "Añadir a Excel Existente"
            # --- Flujo AÑADIR ---
            self.step_output_label.configure(text="Paso 2: Seleccionar Excel Existente")
            self.step_pdf_label.configure(text="Paso 3: Seleccionar Archivos PDF")
            self.step_queue_label.configure(text="Paso 4: Archivos en Cola")
            self.step_convert_label.configure(text="Paso 5: Añadir a Excel")

            self.out_label.configure(text="Añadir a Excel:")
            self.out_btn.configure(text="Abrir...")
            self.convert_btn.configure(text="Añadir a Excel")

            # 2. Reordenar
            self.step_output_frame.grid(row=current_row, column=0, sticky="ew", pady=(0, 15)); current_row += 1
            self.step_pdf_frame.grid(row=current_row, column=0, sticky="ew", pady=(0, 15)); current_row += 1
            self.step_queue_frame.grid(row=current_row, column=0, sticky="ew"); current_row += 1
            self.step_convert_frame.grid(row=current_row, column=0, sticky="ew"); current_row += 1
            
            # 3. Habilitar/Deshabilitar
            self.out_label.configure(state="normal")
            self.out_entry.configure(state="normal")
            self.out_btn.configure(state="normal")

            # Paso 3 (PDFs) solo habilitado si hay Excel de salida
            state_step3 = "normal" if has_output_path else "disabled"
            self.pick_btn.configure(state=state_step3)
            self.clear_btn.configure(state=state_step3)

            # Paso 5 (Convertir) solo si hay PDFs Y Salida
            state_step5 = "normal" if (has_files and has_output_path) else "disabled"
            self.convert_btn.configure(state=state_step5)

    # ===== Acciones =====
    
    def _save_config_data(self):
        self.config_data['theme_mode'] = self.theme_mode
        self.config_data['last_output_folder'] = self.last_output_folder
        _save_config(self.config_data)

    def toggle_theme(self):
        self.theme_mode = "dark" if self.theme_switch.get() == 1 else "light"
        ctk.set_appearance_mode(self.theme_mode)
        self._save_config_data()

    def toggle_mode(self, mode: str):
        self.pdf_paths = []
        self.out_entry_var.set("")
        self.update_file_list(reset_status=False)
        self._update_ui_state()
        
        if mode == "Añadir a Excel Existente":
            self.pick_output(is_open_dialog=True)
        elif self.last_output_folder and os.path.exists(self.last_output_folder):
            default_path = os.path.join(self.last_output_folder, DEFAULT_OUT)
            self.out_entry_var.set(default_path)
            self._update_ui_state() # Llamada extra para actualizar el estado con la nueva ruta

    def update_file_list(self, reset_status: bool = True):
        for widget in self.files_scrollable_frame.winfo_children():
            widget.destroy()
        if not self.pdf_paths:
            label = ctk.CTkLabel(self.files_scrollable_frame, text="No hay archivos seleccionados.")
            label.pack(pady=10)
        else:
            for path in self.pdf_paths:
                row_frame = ctk.CTkFrame(self.files_scrollable_frame, fg_color="transparent")
                row_frame.pack(fill="x", padx=5, pady=2)
                remove_btn = ctk.CTkButton(
                    row_frame, text="X", width=30, height=30,
                    fg_color=("gray75", "gray25"), text_color=("gray10", "gray90"),
                    command=lambda p=path: self.remove_file(p)
                )
                remove_btn.pack(side="left", padx=(0, 10))
                filename = os.path.basename(path)
                if len(filename) > 60:
                    filename = filename[:30] + "..." + filename[-30:]
                label = ctk.CTkLabel(row_frame, text=filename, anchor="w")
                label.pack(side="left", fill="x", expand=True)
        if reset_status:
            # --- INICIO DE LA CORRECCIÓN (v3.5.3) ---
            self.status_label.pack(fill="x", padx=5) # Usar .pack() en lugar de .grid()
            # --- FIN DE LA CORRECCIÓN ---
            self.status_label.configure(text=f"Listo. {len(self.pdf_paths)} archivos en la lista.")

    def remove_file(self, path_to_remove: str):
        try:
            self.pdf_paths.remove(path_to_remove)
        except ValueError:
            print(f"Error: no se pudo quitar {path_to_remove}")
        self.update_file_list(reset_status=True)
        self._update_ui_state()

    # --- MODIFICADO (v3.5.2): Lógica de estado sincronizada ---
    def pick_pdfs(self):
        paths = fd.askopenfilenames(
            title="Selecciona PDF(s) para extraer",
            filetypes=[("PDF", "*.pdf"), ("Todos los archivos", "*.*")]
        )
        if not paths:
            return
        new_paths_added = 0
        for p in paths:
            if p not in self.pdf_paths:
                self.pdf_paths.append(p)
                new_paths_added += 1
        if new_paths_added > 0:
            self.update_file_list(reset_status=True)
            self.progress_bar.set(0)
        
        # 1. Actualizar estado (habilita Paso 4 de Salida)
        self._update_ui_state()
        
        # 2. Rellenar ruta de salida por defecto (si aplica)
        if not self.out_entry_var.get() and self.mode_segmented_btn.get() == "Crear Excel Nuevo":
            base_dir = self.last_output_folder
            if not base_dir or not os.path.exists(base_dir):
                base_dir = os.path.dirname(self.pdf_paths[0])
            out_path = os.path.join(base_dir, DEFAULT_OUT)
            self.out_entry_var.set(out_path)
            
            # Sincroniza el estado, igual que hace pick_output()
            self.last_output_folder = base_dir 
            self._save_config_data()
            
            # 3. Actualizar estado DE NUEVO (ahora habilita Paso 5 de Convertir)
            self._update_ui_state()

    def clear_list(self):
        self.pdf_paths = []
        self.update_file_list(reset_status=True)
        self.progress_bar.set(0)
        self._update_ui_state()

    # --- MODIFICADO (v3.5.1): Lógica de trace eliminada ---
    def pick_output(self, is_open_dialog=False):
        initial_dir = self.last_output_folder or os.path.expanduser("~")
        if self.mode_segmented_btn.get() == "Añadir a Excel Existente" or is_open_dialog:
            out = fd.askopenfilenames(
                title="Seleccionar Excel para añadir datos",
                filetypes=[("Excel", "*.xlsx")],
                initialdir=initial_dir
            )
            if out:
                out = out[0]
        else:
            out = fd.asksaveasfilename(
                title="Guardar Excel como",
                defaultextension=".xlsx",
                filetypes=[("Excel", ".xlsx")],
                initialfile=self.out_entry_var.get() or DEFAULT_OUT,
                initialdir=initial_dir
            )
        if out:
            self.out_entry_var.set(out) # Establecer el valor
            self.last_output_folder = os.path.dirname(out)
            self._save_config_data()
            self._update_ui_state() # Llamar al guardia DESPUÉS de set

    # --- Cola/Threads ---
    def check_queue(self):
        try:
            while not self.progress_queue.empty():
                msg_type, *msg_data = self.progress_queue.get_nowait()
                if msg_type == "progress":
                    value, text = msg_data
                    self.progress_bar.set(value)
                    self.status_label.configure(text=text)
                elif msg_type == "success":
                    msg, full_out_path, filas_totales = msg_data
                    self.handle_success(msg, full_out_path, filas_totales)
                    return
                elif msg_type == "error":
                    error_msg, = msg_data
                    self.handle_error(error_msg)
                    return
        except queue.Empty:
            pass
        except Exception as e:
            self.handle_error(f"Error interno de la GUI: {e}")
            return
        self.after(100, self.check_queue)

    def run_extraction_task(self, pdf_paths, out_path, is_append, progress_queue: queue.Queue):
        try:
            def thread_progress_callback(value, text):
                progress_queue.put(("progress", value, text))
            (filas_netas_añadidas, filas_totales) = run_extraction(
                pdf_paths, out_path,
                progress_callback=thread_progress_callback,
                is_append_mode=is_append
            )
            if is_append:
                if filas_netas_añadidas > 0:
                    msg = f"¡Completado! Se añadieron {filas_netas_añadidas} filas nuevas (netas).\nTotal de filas ahora: {filas_totales}."
                elif filas_totales > 0:
                    msg = f"¡Completado! No se añadieron filas nuevas (probablemente ya existían).\nTotal de filas ahora: {filas_totales}."
                else:
                    msg = "¡Completado! No se encontraron datos válidos."
            else:
                msg = f"¡Completado! Se guardaron {filas_totales} filas."
            full_out_path = os.path.abspath(out_path)
            progress_queue.put(("success", msg, full_out_path, filas_totales))
        except Exception as e:
            tb_text = traceback.format_exc()
            _log_error(e, tb_text)
            progress_queue.put(("error", str(e)))

    def handle_success(self, msg, full_out_path, filas_totales):
        self.progress_bar.set(1.0)
        self.status_label.configure(text=f"¡Éxito! ({filas_totales} filas)")
        self.last_output_folder = os.path.dirname(full_out_path)
        
        dialog = SuccessDialog(self, title="Conversión Exitosa",
                               msg_summary=msg,
                               file_path=full_out_path,
                               folder_path=self.last_output_folder)
        self.wait_window(dialog) # Usar self.wait_window para un popup modal
        
        self.pdf_paths = []
        self.update_file_list(reset_status=False)
        self.out_entry_var.set("") # Limpiar la ruta
        self.reenable_buttons()

    def handle_error(self, error_msg: str):
        self.progress_bar.set(0)
        if "No se pudo guardar el archivo" in error_msg or "No se pudo leer el archivo" in error_msg:
            friendly_msg = "Error: El archivo Excel está abierto. Ciérralo y reintenta."
            self.status_label.configure(text=friendly_msg)
            mb.showerror("Archivo Bloqueado", friendly_msg.replace("Error: ", ""))
        else:
            self.status_label.configure(text="Error. Revisa CONVERSION_ERROR.log")
        self.reenable_buttons()

    def reenable_buttons(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        
        # Habilitar el control maestro (Paso 1)
        self.mode_segmented_btn.configure(state="normal")
        
        # Dejar que el "guardia" decida el estado del resto
        self._update_ui_state()

    def on_convert_click(self):
        out = self.out_entry_var.get().strip()
        is_append = self.mode_segmented_btn.get() == "Añadir a Excel Existente"
        
        if not self.pdf_paths:
            mb.showwarning("Faltan PDFs", "Primero selecciona uno o varios PDF.")
            return
        if not out:
            mb.showwarning("Falta Ruta", "Define un archivo de Excel de salida.")
            return
            
        if not out.lower().endswith(".xlsx"):
            out += ".xlsx"
            self.out_entry_var.set(out)
        
        self.last_output_folder = os.path.dirname(out)
        self._save_config_data()
        
        # --- INICIO DE LA CORRECCIÓN (v3.5.3) ---
        self.status_label.pack(fill="x", padx=5) # Usar .pack() en lugar de .grid()
        # --- FIN DE LA CORRECCIÓN ---
        self.status_label.configure(text="Iniciando...")
        
        # Desactivar TODOS los botones
        self.convert_btn.configure(state="disabled", text="Procesando...")
        self.pick_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")
        self.mode_segmented_btn.configure(state="disabled")
        self.out_btn.configure(state="disabled")
        self.out_entry.configure(state="disabled")
        
        self.progress_bar.set(0)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        
        self.progress_queue = queue.Queue()
        threading.Thread(
            target=self.run_extraction_task,
            args=(self.pdf_paths, out, is_append, self.progress_queue),
            daemon=True
        ).start()
        self.after(100, self.check_queue)

    # --- Auto-Actualización ---
    def check_for_updates(self):
        self.status_label.configure(text="Buscando actualizaciones...")
        threading.Thread(target=self._update_check_thread, daemon=True).start()

    def _update_check_thread(self):
        try:
            response = requests.get(GITHUB_REPO_API, timeout=5)
            response.raise_for_status()
            data = response.json()
            latest_tag = data['tag_name']
            if Version(latest_tag) > Version(APP_CURRENT_VERSION):
                download_url = None
                for asset in data.get('assets', []):
                    if asset.get('name', '').startswith("Setup-DataBridge"):
                        download_url = asset.get('browser_download_url')
                        break
                if download_url:
                    self.after(0, self.ask_user_to_update, latest_tag, download_url)
                else:
                    self.after(0, self.status_label.configure, {"text": "Listo."})
            else:
                self.after(0, self.status_label.configure, {"text": "Estás al día. Listo."})
        except Exception as e:
            print(f"No se pudo verificar actualizaciones: {e}")
            self.after(0, self.status_label.configure, {"text": "No se pudo verificar act. Listo."})

    def ask_user_to_update(self, new_version, download_url):
        if mb.askyesno("¡Actualización Disponible!",
                       f"Hay una nueva versión ({new_version}) de DataBridge.\n"
                       f"Tú tienes la {APP_CURRENT_VERSION}.\n\n"
                       "¿Quieres descargarla e instalarla ahora?"):
            self.status_label.configure(text=f"Descargando {new_version}...")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            
            # Deshabilitar todos los controles
            self.convert_btn.configure(state="disabled")
            self.pick_btn.configure(state="disabled")
            self.clear_btn.configure(state="disabled")
            self.mode_segmented_btn.configure(state="disabled")
            self.out_btn.configure(state="disabled")
            self.out_entry.configure(state="disabled")
            
            threading.Thread(target=self._download_and_install_thread,
                             args=(download_url, new_version),
                             daemon=True).start()

    def _download_and_install_thread(self, url, new_version):
        try:
            temp_dir = os.getenv('TEMP') or os.path.expanduser("~")
            temp_path = os.path.join(temp_dir, f"Setup-DataBridge-{new_version}.exe")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            self.after(0, self.status_label.configure, {"text": "Instalando... La app se reiniciará."})
            subprocess.Popen([temp_path, '/SILENT'])
            self.after(1000, self.destroy)
        except Exception as e:
            self.after(0, self.status_label.configure, {"text": "Error al descargar la actualización."})
            self.after(0, self.progress_bar.stop)
            self.after(0, self.progress_bar.configure, {"mode": "determinate"})
            self.after(0, mb.showerror, ("Error de Actualización", f"No se pudo descargar el instalador:\n{e}"))
            self.after(0, self.reenable_buttons)

# --- Bloque de ejecución principal ---
def main():
    # Establecer DPI awareness para que se vea nítido
    try:
        if sys.platform == "win32":
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    app = App()
    app.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        tb_text = traceback.format_exc()
        log_filename = "STARTUP_ERROR.log"
        try:
            log_path = os.path.join(APP_ROOT, log_filename)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(tb_text)
        except Exception:
            try:
                base_path = os.path.expanduser("~")
                log_path = os.path.join(base_path, log_filename)
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(tb_text)
            except Exception:
                pass