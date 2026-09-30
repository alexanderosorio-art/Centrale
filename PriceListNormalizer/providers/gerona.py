"""Gerona: mapeo confirmado, procesamiento pendiente de información de stock."""
NOMBRE = 'Gerona'
PATRON = r'GERONA'
MONEDA = 'CLP'

# CodigoSKU identifica cada producto del proveedor (p. ej. 112275),
# no es un ID fijo que deba asignarse a todo el catálogo.
MAPEO_CONFIRMADO = {
    'provider_code': 'CodigoSKU',
    'mpn': 'Modelo',
    'name': 'Descripcion',
    'brand': 'Marca',
    'currency_unaware_cost_neto': 'Precio Lista (sin IVA)',
}
AVISO_PENDIENTE = (
    'Gerona: creado con moneda CLP. CodigoSKU será el código del proveedor y '
    'Modelo será el PN. El procesamiento está pendiente de confirmar cómo '
    'Gerona entrega el stock; no se asignan cantidades automáticamente.'
)
leer = None
