"""Reglas de Kepler. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas
import pandas as pd
from common import normalizar_productos, normalizar_columna, normalizar_texto_columna, limpiar_numero
from file_readers import leer_csv

NOMBRE = 'Kepler'
PATRON = r'KEPLER'
MONEDA = 'USD'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('SKU', 'SKU/LINK', 'CODIGO'))


def procesar_kepler(df, fecha, nombre, moneda_valor):
    df = df.copy()
    df.columns = [normalizar_columna(c) for c in df.columns]
    def buscar(opciones):
        return next((c for c in opciones if c in df.columns), None)
    codigo = buscar(['SKU', 'SKU/LINK', 'CODIGO'])
    precio = buscar(['DOLAR', 'VALOR USD', 'U$ NETO', 'VALOR'])
    stock = buscar(['STOCK', 'QTY'])
    # Plantillas revisadas: Vertagear C y D-Link B contienen cantidades sin encabezado.
    if stock is None and {'FAMILIA/LINK', 'SKU', 'U$ NETO'}.issubset(df.columns) and len(df.columns) > 2:
        stock = df.columns[2] if df.columns[2].startswith('UNNAMED:') else None
    if stock is None and {'FAMILIA', 'SKU/LINK', 'U$ NETO'}.issubset(df.columns) and len(df.columns) > 1:
        stock = df.columns[1] if df.columns[1].startswith('UNNAMED:') else None
    if not all([codigo, precio, stock]):
        raise ValueError('Formato Kepler no reconocido: se requieren código, precio y stock.')
    if precio == 'VALOR' and moneda_valor == 'Sin confirmar':
        raise ValueError('Confirma la moneda de la columna VALOR (Threadripper) en el selector antes de procesar.')
    def numero(v):
        return limpiar_numero(v)
    codigos = df[codigo].fillna('').astype(str).str.replace(r'[ \t]*[\r\n]+[ \t]*', '', regex=True).str.strip()
    fuente = pd.DataFrame({'SKU': codigos, 'venta neto usd': df[precio].map(numero),
                           'stock actual': df[stock].map(numero)}, index=df.index)
    if 'LLEGADA' in df.columns:
        fuente = fuente.loc[df['LLEGADA'].astype(str).map(normalizar_columna).eq('EN STOCK')]
    resultado = normalizar_productos(fuente, fecha)
    resultado['currency'] = moneda_valor if precio == 'VALOR' else 'USD'
    # Estos campos solo se copian cuando Kepler los entrega explícitamente.
    # No se deducen marca, PN ni descripción desde SKU u otros datos.
    columnas_producto = {
        normalizar_texto_columna(columna): columna for columna in df.columns
    }
    campos_kepler = {
        'mpn': ('PN', 'P/N', 'MPN', 'PART NUMBER', 'PART NUMBER (MPN)',
                'NUMERO DE PARTE', 'CODIGO FABRICANTE'),
        'name': ('NOMBRE', 'NAME', 'DESCRIPTION', 'DESCRIPCION',
                 'PRODUCT NAME', 'PRODUCTO', 'MODELO'),
        'brand': ('MARCA', 'BRAND', 'MANUFACTURER', 'FABRICANTE'),
    }
    for destino, alias in campos_kepler.items():
        columna = next(
            (columnas_producto[normalizar_texto_columna(opcion)]
             for opcion in alias
             if normalizar_texto_columna(opcion) in columnas_producto),
            None,
        )
        if columna:
            valores = df.loc[resultado.index, columna].fillna('').astype(str).str.strip()
            if destino == 'name':
                valores = valores.str.replace(r'\s*[\r\n]+\s*', ' ', regex=True)
            resultado[destino] = valores.replace({'nan': '', 'None': ''})
    # Equivalencia PN/código confirmada por el usuario para Kepler.
    # Una columna PN explícita siempre prevalece, incluso si tiene vacíos.
    if not any(normalizar_texto_columna(c) in campos_kepler['mpn'] for c in df.columns):
        resultado['mpn'] = resultado['provider_code']
    return resultado


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.pdf'):
        return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
    archivo.seek(0)
    if archivo.name.lower().endswith('.csv'):
        df = leer_csv(archivo)
    else:
        bruto = pd.read_excel(archivo, header=None)
        candidatos = [i for i, row in bruto.iterrows() if set(row.map(normalizar_columna)) & {'SKU', 'SKU/LINK', 'CODIGO'} and set(row.map(normalizar_columna)) & {'DOLAR', 'VALOR USD', 'U$ NETO', 'VALOR'}]
        if not candidatos:
            raise ValueError('No se encontró un encabezado Kepler compatible.')
        archivo.seek(0)
        df = pd.read_excel(archivo, header=candidatos[0])
    resultado = procesar_kepler(df, fecha, archivo.name, moneda)
    detalle = 'Se excluyen códigos vacíos, precios inválidos y stock no positivo.'
    if 'PREVENTA' in normalizar_columna(archivo.name):
        detalle += ' Preventa: las cantidades provienen del archivo; no indican disponibilidad inmediata. No se asignó plazo de entrega.'
    return resultado, len(df), detalle
