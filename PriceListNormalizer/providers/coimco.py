"""Reglas de Coimco. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas

NOMBRE = 'Coimco'
PATRON = r'COIMCO'
MONEDA = 'CLP'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('CODIGO', 'CODIGO SISTEMA', 'SKU'), moneda_fija='CLP')


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
