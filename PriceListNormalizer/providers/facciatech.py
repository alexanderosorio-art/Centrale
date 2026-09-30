"""Facciatech: solo Resumen y precio neto de detalle, sin descuentos por mayor."""
import pandas as pd
from common import normalizar_texto_columna, normalizar_productos, limpiar_numero
from file_readers import obtener_nombres_hojas, leer_hoja_xlsx_con_datos

NOMBRE = 'Facciatech'
PATRON = r'FACCIATECH'
MONEDA = 'CLP'


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if not archivo.name.lower().endswith(('.xlsx', '.xls')):
        raise ValueError('Facciatech: carga un Excel que contenga la hoja Resumen.')
    hojas = obtener_nombres_hojas(archivo)
    resumen = [h for h in hojas if normalizar_texto_columna(h) == 'RESUMEN']
    if len(resumen) != 1:
        raise ValueError('Facciatech: se requiere una única hoja llamada Resumen.')
    hoja = resumen[0]
    if archivo.name.lower().endswith('.xlsx'):
        # Algunas hojas del catálogo tienen formato hasta el límite de Excel.
        # Leer solo celdas con datos de Resumen evita recorrerlas completas.
        bruto = leer_hoja_xlsx_con_datos(archivo, hoja)
    else:
        archivo.seek(0)
        bruto = pd.read_excel(archivo, sheet_name=hoja, header=None, dtype=object)
    requeridas = {'ID', 'PART NUMBER', 'NOMBRE', 'MARCA', 'STOCK', 'PRECIO NETO DETALLE'}
    encabezado = None
    for indice, fila in bruto.iterrows():
        columnas = [normalizar_texto_columna(v) for v in fila]
        if requeridas.issubset(columnas):
            if any(columnas.count(c) != 1 for c in requeridas):
                raise ValueError('Facciatech: hay columnas requeridas duplicadas en Resumen.')
            encabezado = indice
            break
    if encabezado is None:
        raise ValueError('Facciatech: Resumen debe contener ID, Part Number, Nombre, Marca, '
                         'Stock y Precio Neto detalle. No se usa Precio Neto x mayor.')
    datos = bruto.iloc[encabezado + 1:].dropna(how='all').copy()

    def texto(valor):
        if pd.isna(valor):
            return ''
        if isinstance(valor, (int, float)) and not isinstance(valor, bool) and float(valor).is_integer():
            return str(int(valor))
        return str(valor).strip()

    def campo(nombre):
        return datos.iloc[:, columnas.index(nombre)]

    base = pd.DataFrame({
        'SKU': campo('ID').map(texto),
        'venta neto usd': campo('PRECIO NETO DETALLE').map(limpiar_numero),
        'stock actual': pd.to_numeric(campo('STOCK'), errors='coerce'),
    }, index=datos.index)
    resultado = normalizar_productos(base, fecha)
    for destino, origen in [('mpn', 'PART NUMBER'), ('name', 'NOMBRE'), ('brand', 'MARCA')]:
        resultado[destino] = campo(origen).loc[resultado.index].map(texto)
    resultado['currency'] = moneda
    archivo.seek(0)
    return resultado, len(datos), (
        f'Hoja procesada: {hoja}. Costo: Precio Neto detalle; se excluye el precio por mayor. '
        'Se descartan códigos vacíos, precios inválidos y stock no positivo.'
    )
