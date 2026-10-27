"""Diccionario compartido de encabezados confirmados.

Las reglas explícitas del proveedor tienen prioridad. Las equivalencias de
precio de esta base son alternativas de respaldo, no autorizan descuentos
por volumen ni conversiones de moneda. Agregar variantes aquí permite
reutilizarlas en todos los proveedores que usan el lector común.
"""

ENCABEZADOS = {
    'stock': ('DISPONIBLE', 'DISPONIBILIDAD', 'BOH', 'QTY'),
    'pn': ('PN', 'MPN', 'PART NUMBER', 'PART_NUMBER', 'NUMERO DE PARTE', 'P/N'),
    'codigo': ('SKU', 'PRODUCT ID', 'CODIGO PRODUCTO', 'CODIGO DE PRODUCTO'),
    'precio': ('PRECIO ESPECIAL', 'PRECIOS REFERENCIALES', 'P.LISTA', 'PMIN'),
    'nombre': ('DESCRIPTION', 'MKT NAME', 'MODELO', 'PRODUCT NAME', 'DETALLE', 'NOMBRE'),
}


def ampliar_encabezados(configurados, tipo):
    """Añade alternativas sin cambiar la prioridad de las reglas existentes."""
    return tuple(dict.fromkeys((*configurados, *ENCABEZADOS[tipo])))

