"""Listas de otros proveedores con columnas explícitas."""
from table_reader import ReglasTabla, leer_tablas

NOMBRE = 'Otro'
PATRON = None
MONEDA = 'USD'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('CODIGO PROVEEDOR',),
    precios=('VALOR', 'PRECIO'), preferir_oferta=True,
    ofertas=('VALOR ESPECIAL POR REMATE DE UNIDADES',), stock_estricto=True)


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)

