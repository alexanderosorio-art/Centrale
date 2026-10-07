"""Reglas de Ingram. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas, PRECIOS, PART_NUMBERS

NOMBRE = 'Ingram'
PATRON = r'(?:INGRAM|IM)'
MONEDA = 'USD'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('MATERIAL/SKU', 'INGRAM MICRO SKU', 'IM SKU', 'MATERIAL', 'SKU INGRAM'), precios=('COSTO', *PRECIOS), part_numbers=(*PART_NUMBERS, 'PN'), lectura_acotada=True, requiere_descripcion=False)


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
