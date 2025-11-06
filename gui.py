# gui.py (v2.7 - Limpieza Automática y Threading)
import os
import sys
import traceback
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from typing import List
import threading

import customtkinter as ctk
import pandas as pd

APP_NAME = "DataBridge"
DEFAULT_OUT = "Reportes Fenur.xlsx"

# ===== Log de errores (Útil para producción) =====
def _log_error(e, tb_text):
    """Guarda el traceback en un archivo para depurar el .exe"""
    log_filename = "CONVERSION_ERROR.log"
    try:
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(__file__)
        log_path = os.path.join(base_path, log_filename)
        
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Ha ocurrido un error durante la conversión:\n\n")
            f.write(f"Error: {e}\n\n")
            f.write("="*50 + "\n")
            f.write("Traceback:\n")
            f.write(tb_text)
        
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

# ===== Apariencia inicial =====
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ===== Importar Extractor =====
try:
    import extractors  # tu archivo existente
    _import_err = None
except Exception as e:
    extractors = None
    _import_err = e

# Columnas objetivo (mantener)
TARGET_COLS = [
    "Fecha", "Maquina", "Patente", "Folio", "Variante", "Frec",
    "Conductores", "Ab", "SD", "CI", "%", "EV", "TE"
]

# ===== Lógica de Extracción (Sin cambios) =====
# (Esta función ahora se ejecutará en un hilo separado)
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

def _rows_to_df(rows: list[dict]) -> pd.DataFrame:
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
    for c in ["Fecha", "Patente", "Conductores"]:
        df[c] = df[c].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        df[c] = df[c].replace({"None": ""})
    return df

def run_extraction(pdf_paths: list[str], out_path: str, progress_callback, is_append_mode: bool) -> tuple[int, int]:
    """
    Ejecuta la extracción.
    Devuelve (filas_nuevas, filas_totales)
    """
    if not extractors:
        raise RuntimeError(f"No se pudo importar 'extractors.py': {_import_err}")
    
    # --- Parte 1: Leer datos antiguos (si está en modo "Añadir") ---
    df_old = pd.DataFrame()
    if is_append_mode:
        if not os.path.exists(out_path):
            raise FileNotFoundError(f"No se encontró el archivo '{os.path.basename(out_path)}' para añadir datos.")
        progress_callback(0.0, f"Leyendo {os.path.basename(out_path)}...")
        try:
            df_old = pd.read_excel(out_path, sheet_name="Datos")
        except Exception as e:
            raise ValueError(f"No se pudo leer la hoja 'Datos' del Excel. ¿Es el archivo correcto?\nError: {e}")
        
        df_old = df_old.reindex(columns=TARGET_COLS)
        
    # --- Parte 2: Extraer nuevos datos de los PDFs ---
    all_rows = []
    total_files = len(pdf_paths)
    for i, p in enumerate(pdf_paths):
        # Actualizar progreso (de 0% a 80%)
        progress_callback((i + 1) / total_files * 0.8, f"Procesando {os.path.basename(p)}...")
        rows, by_page, method = extractors.parse_pdf_any(p, use_ocr=False)
        all_rows.extend(rows)
        
    df_new = _rows_to_df(all_rows)
    filas_nuevas = len(df_new)
    
    if filas_nuevas == 0 and len(df_old) == 0:
        return 0, 0 
    if filas_nuevas == 0 and len(df_old) > 0:
        return 0, len(df_old)

    # --- Parte 3: Combinar y Guardar ---
    progress_callback(0.9, "Combinando y guardando Excel...")
    
    if is_append_mode:
        df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new
    
    df_final.drop_duplicates(inplace=True)
    filas_totales = len(df_final)

    df_final.to_excel(out_path, index=False, sheet_name="Datos")
    return filas_nuevas, filas_totales

# ===== UI MODERNA v2.7 =====
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("800x600")
        self.minsize(720, 480)

        self.pdf_paths: List[str] = []
        self.last_output_folder: str | None = None

        # Layout principal de 2 columnas
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Panel principal
        self.grid_rowconfigure(0, weight=1)

        # --- 1. Sidebar (Panel Izquierdo) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
        self.sidebar_frame.grid_rowconfigure(4, weight=1) # Espacio de empuje

        self.title_lbl = ctk.CTkLabel(
            self.sidebar_frame, text=APP_NAME,
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_lbl.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.pick_btn = ctk.CTkButton(
            self.sidebar_frame, text="Añadir PDF(s)",
            command=self.pick_pdfs
        )
        self.pick_btn.grid(row=1, column=0, padx=20, pady=10)

        # Botón Limpiar (Corregido)
        self.clear_btn = ctk.CTkButton(
            self.sidebar_frame, text="Limpiar Lista",
            command=self.clear_list, 
            fg_color=("gray75", "gray25"), 
            text_color=("gray10", "gray90"), 
            hover_color=("gray85", "gray35") 
        )
        self.clear_btn.grid(row=2, column=0, padx=20, pady=10)
        
        self.convert_btn = ctk.CTkButton(
            self.sidebar_frame, text="Convertir a Excel",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=40, command=self.on_convert_click
        )
        self.convert_btn.grid(row=3, column=0, padx=20, pady=(20, 10))

        # Controles de apariencia (abajo)
        self.appearance_label = ctk.CTkLabel(
            self.sidebar_frame, text="Modo Oscuro:", anchor="w"
        )
        self.appearance_label.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.theme_switch = ctk.CTkSwitch(
            self.sidebar_frame, text="",
            command=self.toggle_theme
        )
        self.theme_switch.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="w")


        # --- 2. Panel Principal (Derecha) ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(3, weight=1) # Fila 3 (Lista) crecerá

        # Botón Segmentado (fila 0)
        self.mode_label = ctk.CTkLabel(self.main_frame, text="Modo de Operación:")
        self.mode_label.grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        
        self.mode_segmented_btn = ctk.CTkSegmentedButton(
            self.main_frame,
            values=["Crear Nuevo", "Añadir"],
            command=self.toggle_mode
        )
        self.mode_segmented_btn.set("Crear Nuevo") # Estado inicial
        self.mode_segmented_btn.grid(row=1, column=0, sticky="ew", pady=(0, 20))


        # Frame de "Guardar Como" (fila 2)
        self.output_frame = ctk.CTkFrame(self.main_frame)
        self.output_frame.grid(row=2, column=0, sticky="new", pady=(0, 20))
        self.output_frame.grid_columnconfigure(1, weight=1)
        
        self.out_label = ctk.CTkLabel(self.output_frame, text="Guardar Excel como:")
        self.out_label.grid(row=0, column=0, padx=(10, 5), pady=10)
        
        self.out_entry = ctk.CTkEntry(
            self.output_frame, placeholder_text=DEFAULT_OUT
        )
        self.out_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        self.out_btn = ctk.CTkButton(
            self.output_frame, text="Examinar…",
            width=120, command=self.pick_output
        )
        self.out_btn.grid(row=0, column=2, padx=(5, 10), pady=10)


        # Lista Interactiva (fila 3)
        self.files_scrollable_frame = ctk.CTkScrollableFrame(
            self.main_frame, border_width=1, border_color=("gray85", "gray25")
        )
        self.files_scrollable_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 20))
        
        self.initial_list_label = ctk.CTkLabel(
            self.files_scrollable_frame, text="Archivos seleccionados aparecerán aquí..."
        )
        self.initial_list_label.pack(pady=10)

        # Estado (fila 4)
        self.status_label = ctk.CTkLabel(self.main_frame, text="Listo.", anchor="w")
        self.status_label.grid(row=4, column=0, sticky="w", padx=5)

        # Botón de Abrir Carpeta (fila 5)
        self.open_folder_btn = ctk.CTkButton(
            self.main_frame, 
            text="Abrir Carpeta de Salida", 
            command=self.open_output_folder,
            fg_color=("gray75", "gray25"), 
            text_color=("gray10", "gray90"), 
            hover_color=("gray85", "gray35") 
        )
        self.open_folder_btn.grid(row=5, column=0, sticky="w", padx=5, pady=(5, 0))
        self.open_folder_btn.grid_remove() # Oculto al inicio

        # Barra de progreso (fila 6)
        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.grid(row=6, column=0, sticky="ew", pady=(5, 0))
        self.progress_bar.set(0)

        # Chequeo inicial
        if not extractors:
            mb.showwarning(
                "Extractor no encontrado",
                f"No se pudo importar 'extractors.py'.\n\nDetalles: {_import_err}"
            )
            self.convert_btn.configure(state="disabled")

    # ===== Acciones =====
    
    def open_output_folder(self):
        """Abre la carpeta de salida en el explorador de archivos"""
        if self.last_output_folder and os.path.exists(self.last_output_folder):
            try:
                os.startfile(self.last_output_folder)
            except Exception as e:
                mb.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")
        else:
            mb.showwarning("Error", "La ruta de la carpeta no se encontró o ya no existe.")

    def toggle_theme(self):
        mode = "dark" if self.theme_switch.get() == 1 else "light"
        ctk.set_appearance_mode(mode)

    def toggle_mode(self, mode: str):
        """Llamado por el botón segmentado"""
        if mode == "Añadir":
            self.out_label.configure(text="Añadir a Excel:")
            self.out_btn.configure(text="Abrir...")
            self.pick_output(is_open_dialog=True) 
        else: # "Crear Nuevo"
            self.out_label.configure(text="Guardar Excel como:")
            self.out_btn.configure(text="Examinar…")

    # --- ¡FUNCIÓN MODIFICADA! ---
    def update_file_list(self, reset_status: bool = True):
        """
        Limpia y redibuja la lista de archivos en el frame scrollable.
        Si reset_status es True, oculta el botón "Abrir Carpeta" y resetea el label.
        """
        # Limpiar widgets antiguos
        for widget in self.files_scrollable_frame.winfo_children():
            widget.destroy()

        if not self.pdf_paths:
            label = ctk.CTkLabel(
                self.files_scrollable_frame, text="No hay archivos seleccionados."
            )
            label.pack(pady=10)
        else:
            for path in self.pdf_paths:
                # Crear una fila (frame) para cada archivo
                row_frame = ctk.CTkFrame(self.files_scrollable_frame, fg_color="transparent")
                row_frame.pack(fill="x", padx=5, pady=2)
                
                # Botón de quitar (X)
                remove_btn = ctk.CTkButton(
                    row_frame, text="X", width=30, height=30,
                    fg_color=("gray75", "gray25"), text_color=("gray10", "gray90"),
                    command=lambda p=path: self.remove_file(p)
                )
                remove_btn.pack(side="left", padx=(0, 10))
                
                # Nombre del archivo (recortado para que quepa)
                filename = os.path.basename(path)
                if len(filename) > 60:
                    filename = filename[:30] + "..." + filename[-30:]
                
                label = ctk.CTkLabel(
                    row_frame, text=filename, anchor="w"
                )
                label.pack(side="left", fill="x", expand=True)

        # Resetear estado SÓLO si se pide (ej. al limpiar o añadir, no al terminar)
        if reset_status:
            self.open_folder_btn.grid_remove()
            self.status_label.grid() # Asegurarse de que el label normal sea visible
            self.status_label.configure(text=f"Listo. {len(self.pdf_paths)} archivos en la lista.")

    def remove_file(self, path_to_remove: str):
        """Elimina un archivo específico de la lista y actualiza la UI."""
        try:
            self.pdf_paths.remove(path_to_remove)
        except ValueError:
            print(f"Error: no se pudo quitar {path_to_remove}")
        
        self.update_file_list(reset_status=True) # Redibujar Y resetear estado

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
            self.update_file_list(reset_status=True) # Redibujar Y resetear estado
            self.progress_bar.set(0)
        
        if not self.out_entry.get() and self.mode_segmented_btn.get() == "Crear Nuevo":
            first_dir = os.path.dirname(self.pdf_paths[0])
            out_path = os.path.join(first_dir, DEFAULT_OUT)
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, out_path)

    # --- ¡FUNCIÓN MODIFICADA! ---
    def clear_list(self):
        self.pdf_paths = []
        self.update_file_list(reset_status=True) # Redibujar Y resetear estado
        self.progress_bar.set(0)

    def pick_output(self, is_open_dialog=False):
        if self.mode_segmented_btn.get() == "Añadir" or is_open_dialog:
            out = fd.askopenfilename(
                title="Seleccionar Excel para añadir datos",
                filetypes=[("Excel", "*.xlsx")]
            )
        else:
            out = fd.asksaveasfilename(
                title="Guardar Excel como",
                defaultextension=".xlsx",
                filetypes=[("Excel", ".xlsx")],
                initialfile=self.out_entry.get() or DEFAULT_OUT
            )
            
        if out:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, out)

    # Callback de progreso seguro para hilos
    def update_progress_threadsafe(self, value, text):
        """Actualiza la GUI desde el hilo de trabajo de forma segura."""
        self.after(0, self.progress_bar.set, value)
        self.after(0, self.status_label.configure, {"text": text})

    # Tarea de extracción que se ejecuta en el hilo
    def run_extraction_task(self, pdf_paths, out_path, is_append):
        """Esta es la función que realmente se ejecuta en el hilo."""
        try:
            (filas_nuevas, filas_totales) = run_extraction(
                pdf_paths, 
                out_path,
                progress_callback=self.update_progress_threadsafe,
                is_append_mode=is_append
            )
            
            if is_append:
                msg = f"¡Completado! Se añadieron {filas_nuevas} filas nuevas.\nTotal de filas ahora: {filas_totales}."
            else:
                msg = f"¡Completado! Se guardaron {filas_totales} filas."
            
            full_out_path = os.path.abspath(out_path)
            self.after(0, self.handle_success, msg, full_out_path, filas_totales)
            
        except Exception as e:
            tb_text = traceback.format_exc()
            _log_error(e, tb_text) 
            self.after(0, self.handle_error)
        
        finally:
            self.after(0, self.reenable_buttons)

    # --- ¡FUNCIÓN MODIFICADA! ---
    def handle_success(self, msg, full_out_path, filas_totales):
        """Se ejecuta en el hilo principal al tener éxito."""
        self.progress_bar.set(1.0)
        self.status_label.configure(text=f"¡Éxito! ({filas_totales}) filas añadidas")
        
        self.last_output_folder = os.path.dirname(full_out_path)
        self.open_folder_btn.grid() # Mostrar el botón de abrir carpeta

        mb.showinfo("Listo", f"{msg}\nArchivo: {full_out_path}")
        
        # --- ¡NUEVA LÓGICA! ---
        # Limpiar la lista de DATOS y actualizar la UI SIN resetear el estado
        self.pdf_paths = []
        self.update_file_list(reset_status=False) # ¡No resetear el estado!

    def handle_error(self):
        """Se ejecuta en el hilo principal al fallar."""
        self.progress_bar.set(0)
        self.status_label.configure(text="Error. Revisa CONVERSION_ERROR.log")
        self.open_folder_btn.grid_remove()

    def reenable_buttons(self):
        """Se ejecuta en el hilo principal SIEMPRE al finalizar."""
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.convert_btn.configure(state="normal", text="Convertir a Excel")
        self.pick_btn.configure(state="normal")
        self.clear_btn.configure(state="normal")
        self.mode_segmented_btn.configure(state="normal")

    # on_convert_click ahora INICIA el hilo
    def on_convert_click(self):
        if not self.pdf_paths:
            mb.showwarning("Faltan PDFs", "Primero selecciona uno o varios PDF.")
            return

        out = self.out_entry.get().strip()
        is_append = self.mode_segmented_btn.get() == "Añadir"
        
        if not out:
            if is_append:
                mb.showwarning("Falta Excel", "Selecciona un archivo Excel al cual añadir datos.")
                return
            else:
                out = os.path.join(os.path.dirname(self.pdf_paths[0]), DEFAULT_OUT)
        
        if not out.lower().endswith(".xlsx"):
            out += ".xlsx"

        self.out_entry.delete(0, "end")
        self.out_entry.insert(0, out)

        self.open_folder_btn.grid_remove()
        self.status_label.grid() # Asegurarse de que el label de estado esté visible
        self.status_label.configure(text="Iniciando...")

        # Desactivar botones
        self.convert_btn.configure(state="disabled", text="Procesando...")
        self.pick_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")
        self.mode_segmented_btn.configure(state="disabled")

        # Iniciar animación y el hilo de trabajo
        self.progress_bar.set(0)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

        threading.Thread(
            target=self.run_extraction_task, 
            args=(self.pdf_paths, out, is_append),
            daemon=True
        ).start()

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        tb_text = traceback.format_exc()
        _log_error(e, tb_text)