"""Inventario de marca con hojas separadas por mayorista, sin inventar precios."""
import pandas as pd
from common import normalizar_texto_columna, excluir_cajas_abiertas
from file_readers import obtener_nombres_hojas, leer_hoja_xlsx_con_datos

COLUMNAS_CRM = ['provider_code', 'currency_unaware_cost_neto', 'currency', 'expiry_date',
                'quantity', 'mpn', 'brand', 'name', 'condition', 'working_days_to_deliver']


def procesar_stock(archivos):
    resultados, resumen = {}, []
    plantillas = {
        'INGRAM MICRO': ('Ingram', {'SKU', 'VDR_PARTNBR', 'DESCRIPCION', 'BOH'},
                         {'provider_code': 'SKU', 'mpn': 'VDR_PARTNBR', 'name': 'DESCRIPCION'}, 'BOH'),
        'COMPUSOLUCIONES': ('Compusoluciones', {'MODELO', 'NUMERO DE PARTE', 'CANALES'},
                           {'mpn': 'NUMERO DE PARTE', 'name': 'MODELO'}, 'CANALES'),
    }
    def texto(v):
        if pd.isna(v):
            return ''
        if isinstance(v, (int, float)) and float(v).is_integer():
            return str(int(v))
        return str(v).strip()
    for archivo in archivos:
        try:
            if not archivo.name.lower().endswith('.xlsx'):
                raise ValueError('El modo stock admite Excel .xlsx de la plantilla de inventario de marca.')
            hojas = obtener_nombres_hojas(archivo)
            compatibles = [h for h in hojas if normalizar_texto_columna(h) in plantillas]
            if not compatibles:
                raise ValueError('No hay hojas Ingram micro o Compusoluciones compatibles.')
        except Exception as error:
            resumen.append({'Archivo': archivo.name, 'Hoja': '', 'Estado': 'Error', 'Detalle': str(error)})
            continue
        for hoja in compatibles:
            proveedor, requeridas, mapeo, cantidad = plantillas[normalizar_texto_columna(hoja)]
            try:
                bruto = leer_hoja_xlsx_con_datos(archivo, hoja)
                for indice, fila in bruto.iterrows():
                    cols = [normalizar_texto_columna(v) for v in fila]
                    if requeridas.issubset(cols):
                        break
                else:
                    raise ValueError('No se encontraron encabezados compatibles.')
                if any(cols.count(c) != 1 for c in requeridas):
                    raise ValueError('Hay columnas requeridas duplicadas.')
                datos = bruto.iloc[indice + 1:].dropna(how='all')
                leidos = len(datos)
                datos = excluir_cajas_abiertas(datos)
                cajas = leidos - len(datos)
                stock = pd.to_numeric(datos.iloc[:, cols.index(cantidad)], errors='coerce')
                valido = stock.notna() & (stock >= 0) & (stock % 1 == 0)
                identificador = 'SKU' if proveedor == 'Ingram' else 'NUMERO DE PARTE'
                valido &= datos.iloc[:, cols.index(identificador)].map(texto).ne('')
                datos = datos.loc[valido]
                result = pd.DataFrame('', index=datos.index, columns=COLUMNAS_CRM)
                for destino, origen in mapeo.items():
                    result[destino] = datos.iloc[:, cols.index(origen)].map(texto)
                result['quantity'] = stock.loc[datos.index].astype(int)
                # Brand/Linea son categorías, no una marca explícita de producto.
                # Sin precio, moneda, fecha, condición ni código de Compusoluciones.
                resultados.setdefault(proveedor, []).append(result)
                resumen.append({'Archivo': archivo.name, 'Hoja': hoja, 'Estado': 'Procesado',
                                'Leídos': leidos, 'Válidos': len(result), 'OPEN/BAD BOX': cajas,
                                'Detalle': 'Incluye stock cero; no se completan datos ausentes ni se suman duplicados.'})
            except Exception as error:
                resumen.append({'Archivo': archivo.name, 'Hoja': hoja, 'Estado': 'Error', 'Detalle': str(error)})
        archivo.seek(0)
    return pd.DataFrame(resumen), {p: pd.concat(dfs, ignore_index=True) for p, dfs in resultados.items()}
