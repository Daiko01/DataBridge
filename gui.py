# gui.py (Diseño Moderno)
import os
import sys
import traceback
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from typing import List

import customtkinter as ctk
import pandas as pd

APP_NAME = "PDF \u2192 Excel"  # "PDF → Excel"
DEFAULT_OUT = "Tablas_Extraidas.xlsx"

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

# ===== Lógica de Extracción (sin cambios) =====
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

def run_extraction(pdf_paths: list[str], out_path: str, progress_callback) -> int:
    if not extractors:
        raise RuntimeError(f"No se pudo importar 'extractors.py': {_import_err}")
    
    all_rows = []
    total_files = len(pdf_paths)
    for i, p in enumerate(pdf_paths):
        # Actualizar progreso
        progress_callback((i + 1) / total_files, f"Procesando {os.path.basename(p)}...")
        rows, by_page, method = extractors.parse_pdf_any(p, use_ocr=False)
        all_rows.extend(rows)
        
    df = _rows_to_df(all_rows)
    progress_callback(1.0, "Guardando Excel...")
    df.to_excel(out_path, index=False, sheet_name="Datos")
    return len(df)

# ===== UI MODERNA =====
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("800x600")
        self.minsize(720, 480)

        self.pdf_paths: List[str] = []

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
            self.sidebar_frame, text="Elegir PDF(s)",
            command=self.pick_pdfs
        )
        self.pick_btn.grid(row=1, column=0, padx=20, pady=10)

        self.clear_btn = ctk.CTkButton(
            self.sidebar_frame, text="Limpiar Lista",
            command=self.clear_list, fg_color=("gray75", "gray25"), border_width=1,
            text_color=("gray10", "gray90"), border_color=("gray60", "gray40")
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
        self.main_frame.grid_rowconfigure(1, weight=1) # Para que la lista crezca

        # Frame de "Guardar Como"
        self.output_frame = ctk.CTkFrame(self.main_frame)
        self.output_frame.grid(row=0, column=0, sticky="new", pady=(0, 20))
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


        # Lista de archivos seleccionados (Textbox)
        self.files_textbox = ctk.CTkTextbox(
            self.main_frame, border_width=1, border_color=("gray85", "gray25")
        )
        self.files_textbox.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        self.files_textbox.insert("1.0", "Archivos seleccionados aparecerán aquí...")
        self.files_textbox.configure(state="disabled")

        # Barra de progreso y estado
        self.status_label = ctk.CTkLabel(self.main_frame, text="Listo.", anchor="w")
        self.status_label.grid(row=2, column=0, sticky="w", padx=5)

        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        self.progress_bar.set(0)

        # Chequeo inicial
        if not extractors:
            mb.showwarning(
                "Extractor no encontrado",
                f"No se pudo importar 'extractors.py'.\n\nDetalles: {_import_err}"
            )
            self.convert_btn.configure(state="disabled")

    # ===== Acciones =====
    def toggle_theme(self):
        mode = "dark" if self.theme_switch.get() == 1 else "light"
        ctk.set_appearance_mode(mode)

    def update_file_list(self):
        self.files_textbox.configure(state="normal")
        self.files_textbox.delete("1.0", "end")
        if not self.pdf_paths:
            self.files_textbox.insert("1.0", "No hay archivos seleccionados.")
        else:
            self.files_textbox.insert("1.0", f"Se seleccionaron {len(self.pdf_paths)} archivos:\n\n")
            for i, p in enumerate(self.pdf_paths):
                self.files_textbox.insert("end", f"{i+1}. {os.path.basename(p)}\n")
        self.files_textbox.configure(state="disabled")

    def pick_pdfs(self):
        paths = fd.askopenfilenames(
            title="Selecciona PDF(s)",
            filetypes=[("PDF", "*.pdf"), ("Todos los archivos", "*.*")]
        )
        if not paths:
            return
        
        self.pdf_paths = list(paths)
        self.update_file_list()
        self.progress_bar.set(0)
        self.status_label.configure(text="Listo para convertir.")

        # Sugerir un nombre de salida si no hay uno
        if not self.out_entry.get():
            first_dir = os.path.dirname(self.pdf_paths[0])
            out_path = os.path.join(first_dir, DEFAULT_OUT)
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, out_path)

    def clear_list(self):
        self.pdf_paths = []
        self.update_file_list()
        self.progress_bar.set(0)
        self.status_label.configure(text="Listo.")

    def pick_output(self):
        out = fd.asksaveasfilename(
            title="Guardar Excel como",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=self.out_entry.get() or DEFAULT_OUT
        )
        if out:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, out)

    def update_progress_callback(self, value, text):
        self.progress_bar.set(value)
        self.status_label.configure(text=text)
        self.update_idletasks() # Forzar actualización de la GUI

    def on_convert_click(self):
        if not self.pdf_paths:
            mb.showwarning("Faltan PDFs", "Primero selecciona uno o varios PDF.")
            return

        out = self.out_entry.get().strip()
        if not out:
            out = os.path.join(os.path.dirname(self.pdf_paths[0]), DEFAULT_OUT)
        
        if not out.lower().endswith(".xlsx"):
            out += ".xlsx"

        # Guardar la ruta para la próxima vez
        self.out_entry.delete(0, "end")
        self.out_entry.insert(0, out)

        self.convert_btn.configure(state="disabled", text="Procesando...")
        self.pick_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")

        try:
            n = run_extraction(
                self.pdf_paths, 
                out_path=out,
                progress_callback=self.update_progress_callback
            )
            self.progress_bar.set(1.0)
            self.status_label.configure(text=f"¡Completado! Se guardaron {n} filas.")
            mb.showinfo("Listo", f"Excel generado ({n} filas):\n{os.path.abspath(out)}")
            
        except Exception as e:
            tb_text = traceback.format_exc()
            _log_error(e, tb_text) # Guardar log
            self.progress_bar.set(0)
            self.status_label.configure(text="Error. Revisa CONVERSION_ERROR.log")
        
        finally:
            self.convert_btn.configure(state="normal", text="Convertir a Excel")
            self.pick_btn.configure(state="normal")
            self.clear_btn.configure(state="normal")

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    # Ya no necesitamos el _log_startup_debug()
    
    try:
        main()
    except Exception as e:
        # Log de error si la app ni siquiera puede iniciar
        tb_text = traceback.format_exc()
        _log_error(e, tb_text)