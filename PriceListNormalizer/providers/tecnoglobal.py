"""Reglas de Tecnoglobal. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas

NOMBRE = 'Tecnoglobal'
PATRON = r'TECNO[\W_]*GLOBAL'
MONEDA = 'USD'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('CODIGO TG', 'CODIGO', 'CODIGO SISTEMA', 'SKU'))


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
