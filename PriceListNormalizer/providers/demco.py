"""Reglas de Demco Ltda.. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas

NOMBRE = 'Demco Ltda.'
PATRON = r'DEMCO'
MONEDA = 'CLP'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('CODIGO INTERNO',), precios=('PRECIO NETO',), stock_estricto=True, descripcion_exacta='NOMBRE')


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
