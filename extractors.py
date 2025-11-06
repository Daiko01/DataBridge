# -*- coding: utf-8 -*-
"""
extractors.py — Parser robusto PDF → filas
Correcciones finales:
- No se pierden horas (Fecha + Hora detectadas aunque estén en líneas distintas).
- Patente reconstruida (4 letras + 2 dígitos), incluso cuando el dígito final está cortado.
- Conductor: ahora se extrae solo entre Frecuencia y "AB | SD | CI" (evita arrastrar campos previos).
- Mantiene A→B→C (texto→tablas→OCR opcional).
"""
from __future__ import annotations
import logging
import re
from typing import List, Dict, Any, Tuple
from pathlib import Path
import pdfplumber

# ====== Opcionales ======
try:
    import tabula  # type: ignore
except Exception:
    tabula = None

try:
    from pdf2image import convert_from_path  # type: ignore
    import pytesseract  # type: ignore
except Exception:
    convert_from_path = None
    pytesseract = None

LOGGER = logging.getLogger("extractors")

# ====== Regex ======
def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

# Mantenemos el regex con la hora opcional, es más robusto
FECHA_HORA_RE = re.compile(
    r"(?P<Fecha>\d{2}-\d{2}-\d{4})\s*(?:(?:\n|\s)+(?P<Hora>\d{2}:\d{2}:\d{2}))?"
)

TRIPLE_PIPE_RE = re.compile(r"(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)")
PAIR_RE = re.compile(r"(\d+)\s*\|\s*(\d+)")
PCT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")
FOLIO_FLEX_RE = re.compile(r"((?:\d[\s-]?){12,16})")

def _tokens(s: str) -> List[str]:
    return normalize_space(s.replace("\n", " ")).split(" ")

# ===== Helpers =====
def _take_machine(tokens: List[str]) -> Tuple[int | None, int]:
# ... (el resto de esta función no cambia) ...
    for i, t in enumerate(tokens[:5]):
        if t.isdigit() and 1 <= len(t) <= 3:
            return int(t), i + 1
    return None, 0

def _reconstruct_plate(tokens: List[str], start: int) -> Tuple[str | None, int]:
# ... (el resto de esta función no cambia) ...
    limit = min(len(tokens), start + 12)
    for k in range(start, len(tokens)):
        if re.fullmatch(r"\d{10,}", tokens[k] or ""):
            limit = min(limit, k)
            break
    def cj(seq): return re.sub(r"[^A-Za-z0-9]", "", " ".join(seq)).upper()
    for i in range(start, limit):
        for j in range(i, min(i + 6, limit)):
            cand = cj(tokens[i:j + 1])
            m = re.search(r"[A-Z]{4}\d{2}\b", cand)
            if m: return m.group(0), j + 1
    for i in range(start, limit):
        for j in range(i, min(i + 6, limit)):
            cand = cj(tokens[i:j + 1])
            m5 = re.search(r"([A-Z]{4}\d)\b$", cand)
            if m5 and j + 1 < limit and re.fullmatch(r"\d\b", tokens[j + 1] or ""):
                return (m5.group(1) + tokens[j + 1]).upper(), j + 2
    return None, start

def _take_folio(tokens: List[str], start: int) -> Tuple[str | None, int]:
# ... (el resto de esta función no cambia) ...
    digs = ""
    i = start
    while i < len(tokens) and re.fullmatch(r"\d{1,}", tokens[i] or ""):
        digs += tokens[i]
        if 12 <= len(digs) <= 14: return digs, i + 1
        if len(digs) > 14: break
        i += 1
    for j in range(start, min(start + 8, len(tokens))):
        if re.fullmatch(r"\d{12,16}", tokens[j] or ""):
            cand = re.sub(r"\D+", "", tokens[j])
            if 12 <= len(cand) <= 14: return cand, j + 1
    return None, start

def _take_variant_freq(tokens: List[str], start: int) -> Tuple[int | None, int | None, int]:
# ... (el resto de esta función no cambia) ...
    var = freq = None; i = start
    for k in range(i, min(i + 6, len(tokens))):
        if re.fullmatch(r"\d{3}", tokens[k] or ""):
            var = int(tokens[k]); i = k + 1; break
    for k in range(i, min(i + 6, len(tokens))):
        if re.fullmatch(r"\d{1,3}", tokens[k] or ""):
            freq = int(tokens[k]); i = k + 1; break
    return var, freq, i

# ===== Parse block =====
def _parse_block(block: str, fecha: str, hora: str | None) -> Dict[str, Any] | None:
# ... (el resto de esta función no cambia) ...
    b = re.sub(r"(\d)\s*\n\s*(\d)", r"\1\2", block)
    b = normalize_space(b)
    tokens = _tokens(b)

    maquina, pos = _take_machine(tokens)
    patente, pos = _reconstruct_plate(tokens, pos)
    folio, pos = _take_folio(tokens, pos)
    variante, frecuencia, pos = _take_variant_freq(tokens, pos)

    rest_text = " ".join(tokens[pos:]).strip()
    ab = sd = ci = None
    conductor = None
    m_tri_rest = TRIPLE_PIPE_RE.search(rest_text)
    if m_tri_rest:
        conductor = normalize_space(rest_text[:m_tri_rest.start()]) or None
        try: ab, sd, ci = map(int, m_tri_rest.groups())
        except Exception: pass
        after_triple = rest_text[m_tri_rest.end():]
    else:
        conductor = normalize_space(rest_text) or None
        after_triple = ""

    pct = ev = te = None
    search_zone = after_triple if after_triple else rest_text
    m_pct = PCT_RE.search(search_zone)
    zone = search_zone[m_pct.end():] if m_pct else search_zone
    if m_pct:
        try: pct = float(m_pct.group(1).replace(",", "."))
        except Exception: pct = None
    m_pair = PAIR_RE.search(zone)
    if m_pair:
        try: ev = int(m_pair.group(1))
        except Exception: ev = None
        try: te = int(m_pair.group(2))
        except Exception: te = None

    row = {
        "Fecha": fecha, "Hora": hora, "Máquina": maquina,
        "Patente": patente, "Folio": folio,
        "Variante": variante, "Frecuencia": frecuencia,
        "Conductor": conductor, "AB": ab, "SD": sd, "CI": ci, "%": pct, "EV": ev, "TE": te,
    }
    if not row["Folio"] or not row["Fecha"]: return None
    return row

# ===== Intentos =====

# --- ¡¡¡FUNCIÓN COMPLETAMENTE REESCRITA!!! ---
# Esta versión usa page.extract_tables(), que es como funciona tabula.
def parse_pdf_text(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
    rows: List[Dict[str, Any]] = []; by_page: List[int] = []
    
    # Configuraciones de tabla para probar
    table_settings = [
        {"vertical_strategy": "lines", "horizontal_strategy": "lines"}, # Tablas "Lattice" (con líneas)
        {"vertical_strategy": "text", "horizontal_strategy": "text"}, # Tablas "Stream" (alineadas por texto)
    ]

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_rows_count = 0
            found_tables = []
            
            # Intentar extraer tablas con diferentes configuraciones
            for settings in table_settings:
                try:
                    found_tables = page.extract_tables(settings)
                    if found_tables:
                        break # Encontramos tablas, usamos esta configuración
                except Exception:
                    continue
            
            # --- Fallback (si extract_tables no encuentra nada) ---
            if not found_tables:
                # Usar el método de layout (el último que probamos)
                text = page.extract_text(layout=True) or ""
                matches = list(FECHA_HORA_RE.finditer(text))
                if not matches: 
                    by_page.append(0)
                    continue # No hay tablas ni texto, ir a la siguiente página
                
                idxs = [m.start() for m in matches] + [len(text)]
                for i, m in enumerate(matches):
                    block = text[idxs[i]: idxs[i+1]]
                    r = _parse_block(block[m.end():], m.group("Fecha"), m.group("Hora"))
                    if r: rows.append(r); page_rows_count += 1
                by_page.append(page_rows_count)
                continue # Ir a la siguiente página
            # --- Fin del Fallback ---


            # --- Lógica Principal (SI encontramos tablas) ---
            for table in found_tables:
                # table es una lista de filas (list[list[str]])
                for row_cells in table:
                    # Unir todas las celdas de la fila en un solo string
                    line_text = " ".join(str(cell or "") for cell in row_cells)
                    
                    # Quitar saltos de línea dentro de la celda unida y normalizar espacios
                    line_text = normalize_space(line_text.replace("\n", " "))
                    
                    # Buscar el inicio (Fecha) en la línea de texto unida
                    m = FECHA_HORA_RE.search(line_text)
                    if not m:
                        continue # Esta fila no parece ser una fila de datos
                    
                    # Encontramos una fecha, procesar el resto de la línea
                    r = _parse_block(line_text[m.end():], m.group("Fecha"), m.group("Hora"))
                    if r: 
                        rows.append(r)
                        page_rows_count += 1

            by_page.append(page_rows_count)
            
    return rows, by_page

def parse_pdf_tabula(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
# ... (el resto de esta función no cambia) ...
    if tabula is None: return [], []
    try:
        dfs = tabula.read_pdf(str(pdf_path), pages="all", lattice=True, multiple_tables=True) or []
        if not dfs: dfs = tabula.read_pdf(str(pdf_path), pages="all", stream=True, multiple_tables=True) or []
    except Exception: return [], []
    rows: List[Dict[str, Any]] = []
    for df in dfs:
        for _, r in df.iterrows():
            line = " ".join(str(v) for v in r.to_list())
            m = FECHA_HORA_RE.search(line)
            if not m: continue
            rr = _parse_block(line[m.end():], m.group("Fecha"), m.group("Hora"))
            if rr: rows.append(rr)
    return rows, []

def parse_pdf_ocr(pdf_path: str | Path) -> Tuple[List[Dict[str, Any]], List[int]]:
# ... (el resto de esta función no cambia) ...
    if convert_from_path is None or pytesseract is None: return [], []
    images = convert_from_path(str(pdf_path), dpi=300)
    text = "\n".join(__import__('pytesseract').image_to_string(img, lang="spa") for img in images)
    matches = list(FECHA_HORA_RE.finditer(text))
    if not matches: return [], []
    idxs = [m.start() for m in matches] + [len(text)]
    rows: List[Dict[str, Any]] = []
    for i, m in enumerate(matches):
        block = text[idxs[i]: idxs[i+1]]
        r = _parse_block(block[m.end():], m.group("Fecha"), m.group("Hora"))
        if r: rows.append(r)
    return rows, [len(rows)]

def parse_pdf_any(pdf_path: str | Path, use_ocr: bool = False) -> Tuple[List[Dict[str, Any]], List[int], str]:
    # ¡Ahora parse_pdf_text es la primera y MÁS FUERTE opción!
    rows, by_page = parse_pdf_text(pdf_path)
    if rows: return rows, by_page, "text (tables)" # Método de extracción de tablas
    
    # El resto de la función (tabula, ocr) sigue igual
    rows, by_page = parse_pdf_tabula(pdf_path)
    if rows: return rows, by_page, "tabula"
    
    if use_ocr:
        rows, by_page = parse_pdf_ocr(pdf_path)
        if rows: return rows, by_page, "ocr"
        
    return [], [], "none"