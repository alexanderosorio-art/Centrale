"""Reglas de Fujicorp. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas

NOMBRE = 'Fujicorp'
PATRON = r'FUJICORP'
MONEDA = 'CLP'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('CODIGO', 'SKU'), moneda_fija='CLP', preferir_oferta=True)


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
