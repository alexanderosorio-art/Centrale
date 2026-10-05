"""Listas GTC: precios netos, sin ofertas condicionadas a volumen."""
import re
import pandas as pd
from common import normalizar_texto_columna, normalizar_productos, limpiar_numero
from file_readers import obtener_nombres_hojas, leer_hoja_xlsx_con_datos

NOMBRE = 'Gtc ribbon'
PATRON = r'GTC[\W_]*RIBBON'
MONEDA = 'USD'


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if not archivo.name.lower().endswith(('.xlsx', '.xls')):
        raise ValueError('Gtc ribbon: carga una lista Excel con CODIGO GTC.')
    nombres = obtener_nombres_hojas(archivo) if hojas_seleccionadas is None else hojas_seleccionadas
    salida, usadas, leidos, excluidas = [], [], 0, 0
    for nombre in nombres:
        if archivo.name.lower().endswith('.xlsx'):
            bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
        else:
            archivo.seek(0)
            bruto = pd.read_excel(archivo, sheet_name=nombre, header=None, dtype=object)
        for indice, fila in bruto.iterrows():
            cols = [normalizar_texto_columna(v) for v in fila]
            precios = [c for c in ('OFERTA USD NETO', 'PRECIO USD NETO', 'NETO USD', 'OFERTA NETO USD') if c in cols]
            if not {'CODIGO GTC', 'DESCRIPCION', 'STOCK'}.issubset(cols) or not precios:
                continue
            requeridas = ['CODIGO GTC', 'DESCRIPCION', 'STOCK', *precios]
            if any(cols.count(c) != 1 for c in requeridas):
                raise ValueError(f'Gtc ribbon: columnas duplicadas en {nombre}.')
            datos = bruto.iloc[indice + 1:].dropna(how='all').copy()
            leidos += len(datos)
            def campo(c):
                return datos.iloc[:, cols.index(c)]
            def texto(v):
                if pd.isna(v):
                    return ''
                if isinstance(v, (int, float)) and float(v).is_integer():
                    return str(int(v))
                return str(v).strip()
            normal = campo('NETO USD').map(limpiar_numero) if 'NETO USD' in cols else pd.Series(float('nan'), index=datos.index)
            precio = normal.copy()
            for oferta in precios:
                if oferta == 'NETO USD':
                    continue
                opcion = campo(oferta).map(limpiar_numero)
                precio = pd.concat([precio, opcion.where(opcion > 0)], axis=1).min(axis=1)
            condicion = datos.apply(lambda row: bool(re.search(
                r'VOLUMEN|POR MAYOR|\b(?:COMPRA|COMPRAS|COMPRANDO|MINIMO|DESDE)\b.*\d+.*\b(?:UNIDADES|UNIDAD|UND|U/|PCS)\b',
                ' '.join(normalizar_texto_columna(v) for v in row if pd.notna(v)))), axis=1)
            # Una condición de volumen invalida la oferta, no el precio normal.
            precio.loc[condicion] = normal.loc[condicion]
            excluidas += int(condicion.sum())
            stock = campo('STOCK').map(lambda v: pd.to_numeric(str(v).strip().rstrip('+').strip(), errors='coerce'))
            base = pd.DataFrame({'SKU': campo('CODIGO GTC').map(texto),
                                 'venta neto usd': precio, 'stock actual': stock}, index=datos.index)
            result = normalizar_productos(base, fecha)
            result['name'] = campo('DESCRIPCION').loc[result.index].map(texto)
            for destino, origen in [('mpn', 'PART NUMBER'), ('brand', 'MARCA')]:
                if origen in cols:
                    result[destino] = campo(origen).loc[result.index].map(texto)
            result['currency'] = moneda
            salida.append(result)
            usadas.append(nombre)
            break
    archivo.seek(0)
    if not salida:
        raise ValueError('Gtc ribbon: no se encontraron hojas con CODIGO GTC, DESCRIPCION, STOCK y precio neto compatible.')
    return pd.concat(salida, ignore_index=True), leidos, (
        'Hojas procesadas: ' + ', '.join(usadas) +
        f'. Ofertas condicionadas a volumen ignoradas: {excluidas}. EAN no se usa como PN.'
    )
