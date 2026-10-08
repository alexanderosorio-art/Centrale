"""Listas pegadas de cualquier proveedor, con mapeo explícito de columnas."""
import csv
import re
from io import BytesIO, StringIO
import pandas as pd
from common import normalizar_texto_columna, limpiar_numero

COLUMNAS = ['MATERIAL/SKU', 'PART_NUMBER', 'VDR_NAME', 'VDR_NBR', 'MKT NAME', 'STOCK DISPONIBLE', 'PRECIO']


def interpretar_texto(texto, columnas_verticales=None):
    lineas = []
    for linea in texto.replace('\u00a0', ' ').splitlines():
        linea = linea.strip()
        if not linea or re.fullmatch(r'[|\s:–-]+', linea):
            continue
        if linea in ('"', '```', '```text', '```tsv'):
            continue
        lineas.append(linea.replace('**', ''))
    if not lineas:
        raise ValueError('Pega una lista con encabezados y productos.')
    if '\t' in lineas[0] or ('|' in lineas[0] and lineas[0].strip('|').strip()):
        if '\t' not in lineas[0]:
            lineas = ['\t'.join(c.strip() for c in l.strip('|').split('|')) for l in lineas]
        filas = list(csv.reader(StringIO('\n'.join(lineas)), delimiter='\t'))
        cabecera, datos = filas[0], filas[1:]
        if any(len(fila) != len(cabecera) for fila in datos):
            raise ValueError('Hay filas incompletas: todas deben tener el mismo número de columnas que los encabezados.')
    else:
        esquema = columnas_verticales or COLUMNAS
        ancho = len(esquema)
        cabecera, valores = lineas[:ancho], lineas[ancho:]
        if [normalizar_texto_columna(c) for c in cabecera] != [normalizar_texto_columna(c) for c in esquema]:
            raise ValueError('Para texto vertical, indica los encabezados en el mismo orden del texto.')
        if len(valores) % ancho:
            raise ValueError('El texto tiene un bloque incompleto; revisa el número de campos por producto.')
        datos = [valores[i:i + ancho] for i in range(0, len(valores), ancho)]
    if len(set(cabecera)) != len(cabecera) or any(not c.strip() for c in cabecera):
        raise ValueError('Los encabezados deben ser únicos y no estar vacíos.')
    if not datos:
        raise ValueError('No hay productos después de los encabezados.')
    return pd.DataFrame(datos, columns=cabecera)


def archivo_mapeado(df, mapeo):
    tabla = pd.DataFrame(index=df.index)
    for destino in ('provider_code', 'currency_unaware_cost_neto', 'quantity', 'mpn', 'name', 'brand'):
        origen = mapeo.get(destino)
        if destino in ('provider_code', 'currency_unaware_cost_neto', 'quantity') and not origen:
            raise ValueError('Selecciona código, precio y stock antes de procesar.')
        tabla[destino] = df[origen].fillna('').astype(str).str.strip() if origen else ''
    for indice, fila in tabla.iterrows():
        stock = fila.quantity.replace('\u00a0', ' ').strip()
        if re.fullmatch(r'\d{1,3}(?:,\d{3})+', stock):
            stock = stock.replace(',', '')
        if not fila.provider_code or not re.fullmatch(r'\d+\+?', stock):
            raise ValueError(f'Fila {indice+1}: código ausente o stock ambiguo. Corrige la vista previa.')
        precio = fila.currency_unaware_cost_neto.replace('\u00a0', ' ').replace(' ', '')
        if not re.fullmatch(r'\$?\d[\d.,]*', precio) or pd.isna(limpiar_numero(precio)):
            raise ValueError(f'Fila {indice+1}: precio ambiguo o ausente. Corrige la vista previa.')
        tabla.loc[indice, 'quantity'] = stock.rstrip('+')
        tabla.loc[indice, 'currency_unaware_cost_neto'] = str(limpiar_numero(precio))
    archivo = BytesIO(tabla.to_csv(index=False).encode('utf-8-sig'))
    archivo.name = 'Lista pegada.csv'
    archivo.tabla_pegada = tabla
    return archivo


def archivo_desde_tabla(df):
    if list(df.columns) != COLUMNAS:
        raise ValueError('Cambió la estructura de siete columnas del texto Ingram.')
    datos = df.fillna('').astype(str).copy()
    for indice, fila in datos.iterrows():
        numero = indice + 1
        if not re.fullmatch(r'\d+', fila['MATERIAL/SKU'].strip()) or not re.fullmatch(r'\d+', fila['VDR_NBR'].strip()):
            raise ValueError(f'Producto {numero}: SKU o VDR_NBR no numérico; revisa que los campos no se hayan desplazado.')
        if not fila['MKT NAME'].strip():
            raise ValueError(f'Producto {numero}: falta el nombre; revisa la fila.')
        stock = fila['STOCK DISPONIBLE'].strip()
        if re.fullmatch(r'\d{1,3}(?:,\d{3})+', stock):
            stock = stock.replace(',', '')
        if not re.fullmatch(r'\d+\+?', stock):
            raise ValueError(f'Producto {numero}: stock ambiguo o ausente; corrígelo antes de procesar.')
        precio = fila['PRECIO'].replace('\u00a0', ' ').strip()
        if not re.fullmatch(r'\$?\s*\d[\d.,\s]*', precio) or pd.isna(limpiar_numero(precio.replace(' ', ''))):
            raise ValueError(f'Producto {numero}: precio ambiguo o ausente; corrígelo antes de procesar.')
        datos.loc[indice, 'STOCK DISPONIBLE'] = stock.rstrip('+')
        datos.loc[indice, 'PRECIO'] = str(limpiar_numero(precio.replace(' ', '')))
    archivo = BytesIO(datos.to_csv(index=False).encode('utf-8-sig'))
    archivo.name = 'Ingram texto pegado.csv'
    return archivo
