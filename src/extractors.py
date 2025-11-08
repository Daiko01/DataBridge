# -*- coding: utf-8 -*-
"""
extractors.py — Parser robusto PDF → filas
Compatibilidad con gui.py (v3.4.x):
- Campos: Fecha, Hora, Máquina, Patente, Folio, Variante, Frecuencia, Conductor, AB, SD, CI, %, EV, TE
- Devuelve listas de dicts (ExtractedRow) y conteo de filas por página
- Prioriza extracción por tablas (pdfplumber), luego texto, opcional OCR
"""
from __future__ import annotations
import re
import logging
from typing import List, Tuple, TypedDict, Optional, Dict, Any
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

# ---------- Tipado ----------
ExtractedRow = TypedDict('ExtractedRow', {
    "Fecha": str,
    "Hora": str | None,
    "Máquina": int | None,
    "Patente": str | None,
    "Folio": str | None,
    "Variante": int | None,
    "Frecuencia": int | None,
    "Conductor": str | None,
    "AB": int | None,
    "SD": int | None,
    "CI": int | None,
    "%": float | None,  # <-- Esta sintaxis SÍ lo permite
    "EV": int | None,
    "TE": int | None
})

# ---------- Utilidades ----------
def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def _tokens(s: str) -> List[str]:
    return normalize_space((s or "").replace("\n", " ")).split(" ")

# Fecha (dd-mm-yyyy o dd/mm/yyyy) y hora opcional (puede venir en línea siguiente)
FECHA_HORA_RE = re.compile(
    r"(?P<Fecha>\d{2}[-/]\d{2}[-/]\d{4})\s*(?:(?:\n|\s)+(?P<Hora>\d{2}:\d{2}:\d{2}))?",
    re.MULTILINE,
)

TRIPLE_PIPE_RE = re.compile(r"(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)")
PAIR_RE = re.compile(r"(\d+)\s*\|\s*(\d+)")
PCT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")
# Folio flexible: 12–16 dígitos contiguos o con separadores
FOLIO_FLEX_RE = re.compile(r"((?:\d[\s-]?){12,16})")

# ---------- Extractores atómicos ----------
def _take_machine(tokens: List[str]) -> Tuple[Optional[int], int]:
    # Busca un entero corto (1–3 dígitos) en las primeras posiciones
    for i, t in enumerate(tokens[:5]):
        if t.isdigit() and 1 <= len(t) <= 3:
            return int(t), i + 1
    return None, 0

def _reconstruct_plate(tokens: List[str], start: int) -> Tuple[Optional[str], int]:
    """
    Reconstruye patentes del tipo AAAA00 tolerando cortes de dígitos/letras.
    Escanea una ventana y arma un candidato A-Z{4} + \d{2}.
    """
    limit = min(len(tokens), start + 12)

    # Si aparece una "cola" de dígitos largos, acotar la ventana
    for k in range(start, len(tokens)):
        if re.fullmatch(r"\d{10,}", tokens[k] or ""):
            limit = min(limit, k)
            break

    def cj(seq):  # concat & clean
        return re.sub(r"[^A-Za-z0-9]", "", " ".join(seq)).upper()

    # Caso completo AAAA00
    for i in range(start, limit):
        for j in range(i, min(i + 6, limit)):
            cand = cj(tokens[i:j + 1])
            m = re.search(r"[A-Z]{4}\d{2}\b", cand)
            if m:
                return m.group(0), j + 1

    # Caso AAAA0 + (siguiente token) 0
    for i in range(start, limit):
        for j in range(i, min(i + 6, limit)):
            cand = cj(tokens[i:j + 1])
            m5 = re.search(r"([A-Z]{4}\d)\b$", cand)
            if m5 and j + 1 < limit and re.fullmatch(r"\d\b", tokens[j + 1] or ""):
                return (m5.group(1) + tokens[j + 1]).upper(), j + 2

    return None, start

def _take_folio(tokens: List[str], start: int) -> Tuple[Optional[str], int]:
    # Unir múltiples tokens numéricos consecutivos hasta lograr 12–14 dígitos
    digs = ""
    i = start
    while i < len(tokens) and re.fullmatch(r"\d{1,}", tokens[i] or ""):
        digs += tokens[i]
        if 12 <= len(digs) <= 14:
            return digs, i + 1
        if len(digs) > 16:
            break
        i += 1
    # Búsqueda directa en una ventana corta
    for j in range(start, min(start + 8, len(tokens))):
        if re.fullmatch(r"\d{12,16}", tokens[j] or ""):
            cand = re.sub(r"\D+", "", tokens[j])
            if 12 <= len(cand) <= 16:
                return cand, j + 1
    # Patrón flexible con separadores
    for j in range(start, min(start + 8, len(tokens))):
        m = FOLIO_FLEX_RE.search(tokens[j] or "")
        if m:
            cand = re.sub(r"\D+", "", m.group(1))
            if 12 <= len(cand) <= 16:
                return cand, j + 1
    return None, start

def _take_variant_freq(tokens: List[str], start: int) -> Tuple[Optional[int], Optional[int], int]:
    var = freq = None
    i = start
    # Variante: 3 dígitos
    for k in range(i, min(i + 6, len(tokens))):
        if re.fullmatch(r"\d{3}", tokens[k] or ""):
            var = int(tokens[k])
            i = k + 1
            break
    # Frecuencia: 1–3 dígitos
    for k in range(i, min(i + 6, len(tokens))):
        if re.fullmatch(r"\d{1,3}", tokens[k] or ""):
            freq = int(tokens[k])
            i = k + 1
            break
    return var, freq, i

# ---------- Parser de bloque ----------
def _parse_block(block: str, fecha: str, hora: Optional[str]) -> Optional[ExtractedRow]:
    """
    Recibe el texto posterior a Fecha/Hora y arma una fila.
    Orden esperado (tolerante): Máquina, Patente, Folio, Variante, Frecuencia, Conductor, AB|SD|CI, %, EV|TE
    """
    # Pegar dígitos rotos por saltos de línea: "12\n3" → "123"
    b = re.sub(r"(\d)\s*\n\s*(\d)", r"\1\2", block or "")
    b = normalize_space(b)
    tokens = _tokens(b)

    maquina, pos = _take_machine(tokens)
    patente, pos = _reconstruct_plate(tokens, pos)
    folio, pos = _take_folio(tokens, pos)
    variante, frecuencia, pos = _take_variant_freq(tokens, pos)

    rest_text = " ".join(tokens[pos:]).strip()

    # Conductor hasta AB|SD|CI (si existe)
    ab = sd = ci = None
    conductor = None
    m_tri_rest = TRIPLE_PIPE_RE.search(rest_text)
    if m_tri_rest:
        conductor = normalize_space(rest_text[:m_tri_rest.start()]) or None
        try:
            ab, sd, ci = map(int, m_tri_rest.groups())
        except Exception:
            pass
        after_triple = rest_text[m_tri_rest.end():]
    else:
        conductor = normalize_space(rest_text) or None
        after_triple = ""

    # % y EV|TE
    pct_txt: Optional[str] = None
    ev = te = None
    search_zone = after_triple if after_triple else rest_text

    m_pct = PCT_RE.search(search_zone)
    zone = search_zone[m_pct.end():] if m_pct else search_zone
    if m_pct:
        # Guardar como TEXTO con el símbolo
        pct_core = m_pct.group(1).replace(",", ".")
        pct_txt = f"{pct_core}%"

    m_pair = PAIR_RE.search(zone)
    if m_pair:
        try:
            ev = int(m_pair.group(1))
        except Exception:
            ev = None
        try:
            te = int(m_pair.group(2))
        except Exception:
            te = None

    row: ExtractedRow = {
        "Fecha": fecha,
        "Hora": hora,
        "Máquina": maquina,
        "Patente": patente,
        "Folio": folio,
        "Variante": variante,
        "Frecuencia": frecuencia,
        "Conductor": conductor,
        "AB": ab,
        "SD": sd,
        "CI": ci,
        "%": pct_txt,
        "EV": ev,
        "TE": te,
    }
    if not row.get("Folio") or not row.get("Fecha"):
        return None
    return row

# ---------- Métodos de extracción ----------
def parse_pdf_text(pdf_path: str | Path) -> Tuple[List[ExtractedRow], List[int]]:
    """
    Intenta por tablas con pdfplumber (lattice/stream). Fallback a texto por bloques.
    """
    rows: List[ExtractedRow] = []
    by_page: List[int] = []

    table_modes = [
        {"vertical_strategy": "lines", "horizontal_strategy": "lines"},  # lattice
        {"vertical_strategy": "text", "horizontal_strategy": "text"},    # stream
    ]

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_rows = 0
            tables = []
            # Probar distintas estrategias de tabla
            for settings in table_modes:
                try:
                    tables = page.extract_tables(table_settings=settings)  # pdfplumber >=0.11
                    if tables:
                        break
                except TypeError:
                    # Compatibilidad con versiones viejas que aceptan settings posicional
                    try:
                        tables = page.extract_tables(settings)
                        if tables:
                            break
                    except Exception:
                        continue
                except Exception:
                    continue

            if not tables:
                # Fallback a texto con layout
                text = page.extract_text(layout=True) or page.extract_text() or ""
                matches = list(FECHA_HORA_RE.finditer(text))
                if not matches:
                    by_page.append(0)
                    continue
                idxs = [m.start() for m in matches] + [len(text)]
                for i, m in enumerate(matches):
                    block = text[idxs[i]: idxs[i + 1]]
                    r = _parse_block(block[m.end():], m.group("Fecha"), m.group("Hora"))
                    if r:
                        rows.append(r)
                        page_rows += 1
                by_page.append(page_rows)
                continue

            # Parse fila por fila desde tablas
            for table in tables:
                for row_cells in table:
                    line_text = " ".join(str(c or "") for c in row_cells)
                    line_text = normalize_space(line_text.replace("\n", " "))
                    m = FECHA_HORA_RE.search(line_text)
                    if not m:
                        continue
                    r = _parse_block(line_text[m.end():], m.group("Fecha"), m.group("Hora"))
                    if r:
                        rows.append(r)
                        page_rows += 1
            by_page.append(page_rows)

    return rows, by_page

def parse_pdf_tabula(pdf_path: str | Path) -> Tuple[List[ExtractedRow], List[int]]:
    """
    Alternativa con tabula-py (si está instalado). Llama en stream y lattice.
    """
    if tabula is None:
        return [], []
    try:
        dfs = tabula.read_pdf(str(pdf_path), pages="all", lattice=True, multiple_tables=True) or []
        if not dfs:
            dfs = tabula.read_pdf(str(pdf_path), pages="all", stream=True, multiple_tables=True) or []
    except Exception:
        return [], []

    rows: List[ExtractedRow] = []
    for df in dfs:
        for _, r in df.iterrows():
            line = " ".join(str(v) for v in r.to_list())
            m = FECHA_HORA_RE.search(line)
            if not m:
                continue
            rr = _parse_block(line[m.end():], m.group("Fecha"), m.group("Hora"))
            if rr:
                rows.append(rr)
    return rows, []

def parse_pdf_ocr(pdf_path: str | Path) -> Tuple[List[ExtractedRow], List[int]]:
    """
    Fallback OCR (lento). Requiere pdf2image + Tesseract.
    """
    if convert_from_path is None or pytesseract is None:
        return [], []
    images = convert_from_path(str(pdf_path), dpi=300)
    text = "\n".join(pytesseract.image_to_string(img, lang="spa") for img in images)
    matches = list(FECHA_HORA_RE.finditer(text))
    if not matches:
        return [], []
    idxs = [m.start() for m in matches] + [len(text)]
    rows: List[ExtractedRow] = []
    for i, m in enumerate(matches):
        block = text[idxs[i]: idxs[i + 1]]
        r = _parse_block(block[m.end():], m.group("Fecha"), m.group("Hora"))
        if r:
            rows.append(r)
    return rows, [len(rows)]

def parse_pdf_any(pdf_path: str | Path, use_ocr: bool = False) -> Tuple[List[ExtractedRow], List[int], str]:
    """
    Orquestador: intenta texto/tablas → tabula → OCR (opc.)
    """
    rows, by_page = parse_pdf_text(pdf_path)
    if rows:
        return rows, by_page, "text (tables)"
    rows, by_page = parse_pdf_tabula(pdf_path)
    if rows:
        return rows, by_page, "tabula"
    if use_ocr:
        rows, by_page = parse_pdf_ocr(pdf_path)
        if rows:
            return rows, by_page, "ocr"
    return [], [], "none"
