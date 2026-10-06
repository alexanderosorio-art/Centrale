"""Catálogo Gerona: precio neto informado y stock ausente, nunca inferido."""
import pandas as pd
from common import normalizar_texto_columna, limpiar_numero, formatear_expiry_date, excluir_cajas_abiertas
from file_readers import obtener_nombres_hojas, leer_hoja_xlsx_con_datos
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


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if not archivo.name.lower().endswith(('.xlsx', '.xls')):
        raise ValueError('Gerona: carga el catálogo Excel con Precio Lista (sin IVA).')
    nombres = obtener_nombres_hojas(archivo) if hojas_seleccionadas is None else hojas_seleccionadas
    requeridas = {normalizar_texto_columna(c) for c in MAPEO_CONFIRMADO.values()}
    salida, usadas, leidos = [], [], 0
    def texto(v):
        if pd.isna(v):
            return ''
        if isinstance(v, (int, float)) and float(v).is_integer():
            return str(int(v))
        return str(v).strip()
    for nombre in nombres:
        if archivo.name.lower().endswith('.xlsx'):
            bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
        else:
            archivo.seek(0)
            bruto = pd.read_excel(archivo, sheet_name=nombre, header=None, dtype=object)
        for indice, fila in bruto.iterrows():
            cols = [normalizar_texto_columna(v) for v in fila]
            if not requeridas.issubset(cols):
                continue
            if any(cols.count(c) != 1 for c in requeridas):
                raise ValueError(f'Gerona: columnas requeridas duplicadas en {nombre}.')
            datos = bruto.iloc[indice + 1:].dropna(how='all')
            leidos += len(datos)
            datos = excluir_cajas_abiertas(datos)
            resultado = pd.DataFrame(index=datos.index)
            for destino, origen in MAPEO_CONFIRMADO.items():
                valores = datos.iloc[:, cols.index(normalizar_texto_columna(origen))]
                resultado[destino] = valores.map(limpiar_numero if destino == 'currency_unaware_cost_neto' else texto)
            resultado = resultado.loc[resultado.provider_code.ne('') &
                (resultado.currency_unaware_cost_neto > 0)].copy()
            resultado['currency'] = moneda
            resultado['expiry_date'] = formatear_expiry_date(fecha)
            resultado['quantity'] = ''
            resultado['condition'] = ''
            resultado['working_days_to_deliver'] = ''
            columnas = ['provider_code', 'currency_unaware_cost_neto', 'currency', 'expiry_date',
                        'quantity', 'mpn', 'brand', 'name', 'condition', 'working_days_to_deliver']
            salida.append(resultado[columnas])
            usadas.append(nombre)
            break
    archivo.seek(0)
    if not salida:
        raise ValueError('Gerona: no se encontraron hojas con CodigoSKU, Modelo, Descripcion, Marca y Precio Lista (sin IVA).')
    return pd.concat(salida, ignore_index=True), leidos, ('Hojas procesadas: ' + ', '.join(usadas) +
        '. Se usa Precio Lista (sin IVA), no Precio Sugerido. Stock vacío: el catálogo no informa disponibilidad.')
