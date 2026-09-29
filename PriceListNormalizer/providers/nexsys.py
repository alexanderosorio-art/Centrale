"""Reglas de Nexsys. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas

NOMBRE = 'Nexsys'
PATRON = r'NEXSYS'
MONEDA = 'USD'
REGLAS = ReglasTabla(
    nombre=NOMBRE, codigos=('SKU', 'CODIGO'), codigo_desde_pn=True,
    preferir_oferta=True,
    # Ofertas unitarias observadas en ASUS. No incluir precios por volumen.
    ofertas=('OFERTA', 'PRECIO OFERTA', 'PRECIOS OFERTAS USD'),
)


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
