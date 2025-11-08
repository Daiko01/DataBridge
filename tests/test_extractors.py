import pytest

# Importante: Como estamos en la carpeta 'tests',
# le decimos a Python que importe desde la carpeta 'src'.
from src.extractors import _reconstruct_plate, _take_folio

# --- Pruebas para _reconstruct_plate ---
# El nombre de la función DEBE empezar con 'test_'

def test_plate_normal():
    """Prueba una patente estándar que está en un solo token."""
    tokens = ["123", "ABCD12", "123456789012", "999"]
    
    # Probamos la función buscando desde el índice 1 (donde empieza la data)
    patente, pos = _reconstruct_plate(tokens, 1)
    
    # Comprobamos el resultado
    assert patente == "ABCD12"
    assert pos == 2  # El siguiente índice debe ser 2 (el Folio)

def test_plate_with_spaces():
    """Prueba una patente que está dividida en múltiples tokens."""
    tokens = ["123", "AB", "CD", "12", "123456789012", "999"]
    
    patente, pos = _reconstruct_plate(tokens, 1)
    
    assert patente == "ABCD12"
    assert pos == 4  # El siguiente índice debe ser 4 (el Folio)

def test_plate_split_digit_fallback():
    """Prueba la lógica de "rescate" donde el último dígito está separado."""
    tokens = ["123", "ABCD1", "2", "123456789012", "999"]
    
    patente, pos = _reconstruct_plate(tokens, 1)
    
    assert patente == "ABCD12"
    assert pos == 3  # El siguiente índice debe ser 3 (el Folio)

def test_plate_no_match():
    """Prueba que no se encuentre una patente si no existe."""
    tokens = ["123", "Hola", "Mundo", "123456789012"]
    
    patente, pos = _reconstruct_plate(tokens, 1)
    
    assert patente is None  # El resultado debe ser None
    assert pos == 1         # La posición no debe cambiar

def test_plate_interrupted_by_folio():
    """Prueba que la búsqueda se detenga si encuentra un folio."""
    # La lógica de "rescate" (ABCD1 + 2) no debe activarse
    # si un folio se interpone en medio.
    tokens = ["123", "ABCD1", "123456789012", "2"]
    
    patente, pos = _reconstruct_plate(tokens, 1)
    
    assert patente is None  # No debe encontrar "ABCD12"
    assert pos == 1         # La posición no debe cambiar

# --- Pruebas para _take_folio (Ejemplo) ---

def test_folio_normal():
    """Prueba un folio estándar."""
    tokens = ["123", "ABCD12", "123456789012", "999"]
    
    # Probamos la función buscando desde el índice 2 (después de la patente)
    folio, pos = _take_folio(tokens, 2)
    
    assert folio == "123456789012"
    assert pos == 3