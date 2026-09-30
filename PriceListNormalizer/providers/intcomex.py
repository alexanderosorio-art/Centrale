"""Reglas de Intcomex. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas
import pandas as pd
import re
from common import normalizar_productos, normalizar_texto_columna
from file_readers import leer_csv, detectar_encabezado, leer_hoja_xlsx_con_datos, palabras_clave_encabezado

NOMBRE = 'Intcomex'
PATRON = r'INTCOMEX'
MONEDA = 'USD'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('SKU', 'MATERIAL/SKU', 'MATERIAL', 'CODIGO'), moneda_fija='USD')
HIKVISION = {'SKU', 'PART #', 'DESCRIPCION', 'DPV', 'UNIT PRICE$'}


def leer_intcomex_xlsx(archivo):
    bruto = leer_hoja_xlsx_con_datos(archivo)
    if bruto.empty:
        raise ValueError('La primera hoja de Intcomex no contiene datos.')
    columnas_asus = {'SKU INTCOMEX', 'NUMERO DE PARTE', 'PRECIO USD (S/IVA)',
                     'STOCK REFERENCIAL', 'DETALLE'}
    candidatos = [i for i, fila in bruto.iterrows()
                  if columnas_asus.issubset({normalizar_texto_columna(v) for v in fila})
                  or HIKVISION.issubset({normalizar_texto_columna(v) for v in fila})]
    if candidatos:
        encabezado = candidatos[0]
    else:
        puntajes = bruto.apply(lambda fila: sum(
            palabra in ' '.join(fila.fillna('').astype(str)).lower()
            for palabra in palabras_clave_encabezado()), axis=1)
        encabezado = puntajes.idxmax()
    datos = bruto.iloc[encabezado + 1:].dropna(how='all').copy()
    datos.columns = bruto.iloc[encabezado]
    return datos


def procesar_intcomex_asus(df, expiry_date):
    columnas = {normalizar_texto_columna(c): c for c in df.columns}
    base = pd.DataFrame({
        'SKU': df[columnas['SKU INTCOMEX']],
        'venta neto usd': df[columnas['PRECIO USD (S/IVA)']],
        'stock actual': pd.to_numeric(df[columnas['STOCK REFERENCIAL']], errors='coerce'),
    }, index=df.index)
    resultado = normalizar_productos(base, expiry_date)
    for destino, origen in [('mpn', 'NUMERO DE PARTE'), ('name', 'DETALLE')]:
        resultado[destino] = df.loc[resultado.index, columnas[origen]].fillna('').astype(str).str.strip()
    return resultado


def procesar_intcomex_wd(df, expiry_date):
    """Lee la plantilla Intcomex de precios especiales WD para CENTRALE."""
    columnas = {
        normalizar_texto_columna(columna): columna
        for columna in df.columns
    }
    requeridas = {
        "SKU": "SKU",
        "PART NUMBER (MPN)": "mpn",
        "DESCRIPCION": "name",
        "STOCK DISPONIBLE": "stock",
        "PRECIO ESPECIAL NETO UNIT. CENTRALE": "price",
    }
    faltantes = [nombre for nombre in requeridas if nombre not in columnas]
    if faltantes:
        raise ValueError(
            "Plantilla Intcomex WD no reconocida. Faltan columnas: "
            + ", ".join(faltantes)
        )

    base = pd.DataFrame(
        {
            "SKU": df[columnas["SKU"]],
            "venta neto usd": df[
                columnas["PRECIO ESPECIAL NETO UNIT. CENTRALE"]
            ],
            "stock actual": df[columnas["STOCK DISPONIBLE"]],
        },
        index=df.index,
    )
    resultado = normalizar_productos(base, expiry_date)
    resultado["mpn"] = (
        df.loc[resultado.index, columnas["PART NUMBER (MPN)"]]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    resultado["name"] = (
        df.loc[resultado.index, columnas["DESCRIPCION"]]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    # No hay columna de marca en esta plantilla: se conserva vacía.
    return resultado


def procesar_intcomex_hikvision(df, fecha):
    columnas = {normalizar_texto_columna(c): c for c in df.columns}
    def stock(valor):
        # 500+ indica al menos 500: usar únicamente la cantidad informada.
        texto = str(valor).strip()
        return pd.to_numeric(texto.rstrip('+').strip(), errors='coerce') if re.fullmatch(r'\d+(?:\.0+)?\s*\+?', texto) else None
    base = pd.DataFrame({
        'SKU': df[columnas['SKU']],
        'venta neto usd': df[columnas['UNIT PRICE$']],
        'stock actual': df[columnas['DPV']].map(stock),
    }, index=df.index)
    resultado = normalizar_productos(base, fecha)
    for destino, origen in [('mpn', 'PART #'), ('name', 'DESCRIPCION')]:
        resultado[destino] = df.loc[resultado.index, columnas[origen]].fillna('').astype(str).str.strip()
    return resultado


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.pdf'):
        return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
    archivo.seek(0)
    if archivo.name.lower().endswith('.csv'):
        df = leer_csv(archivo)
    elif archivo.name.lower().endswith('.xlsx'):
        df = leer_intcomex_xlsx(archivo)
    else:
        encabezado = detectar_encabezado(archivo)
        archivo.seek(0)
        df = pd.read_excel(archivo, header=encabezado)
    columnas = {normalizar_texto_columna(c) for c in df.columns}
    if HIKVISION.issubset(columnas):
        resultado = procesar_intcomex_hikvision(df, fecha)
    elif {'SKU INTCOMEX', 'NUMERO DE PARTE', 'PRECIO USD (S/IVA)', 'STOCK REFERENCIAL', 'DETALLE'}.issubset(columnas):
        resultado = procesar_intcomex_asus(df, fecha)
    elif {'PART NUMBER (MPN)', 'PRECIO ESPECIAL NETO UNIT. CENTRALE'}.issubset(columnas):
        resultado = procesar_intcomex_wd(df, fecha)
    else:
        resultado = normalizar_productos(df, fecha)
    return resultado, len(df), 'Se excluyen códigos vacíos, precios inválidos y stock no positivo.'
