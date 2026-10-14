"""Reglas de Ingram. No se infieren datos de producto ausentes."""
import pandas as pd
from table_reader import ReglasTabla, leer_tablas, PRECIOS, PART_NUMBERS
from common import normalizar_productos, normalizar_texto_columna
from file_readers import leer_hoja_xlsx_con_datos, obtener_nombres_hojas

NOMBRE = 'Ingram'
PATRON = r'(?:INGRAM|IM)'
MONEDA = 'USD'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('MATERIAL/SKU', 'INGRAM MICRO SKU', 'IM SKU', 'MATERIAL', 'SKU INGRAM'), precios=('COSTO', *PRECIOS), part_numbers=(*PART_NUMBERS, 'PN'), lectura_acotada=True, requiere_descripcion=False)
STOCK_TRANSITOS = {
    'VDR_NAME', 'SKU', 'VDR_PARTNB', 'MODELO', 'DESC TECNICA',
    'C REVENDEDOR', 'STOCK', 'TRANSITOS', 'ETA CD',
}


def _leer_stock_y_transitos(archivo, fecha, hojas_seleccionadas=None):
    nombres = hojas_seleccionadas if hojas_seleccionadas is not None else obtener_nombres_hojas(archivo)
    salida, leidos, usadas = [], 0, []
    for nombre in nombres:
        bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
        for inicio, fila in bruto.iterrows():
            columnas = [normalizar_texto_columna(v) for v in fila]
            if not STOCK_TRANSITOS.issubset(columnas):
                continue
            if any(columnas.count(c) != 1 for c in STOCK_TRANSITOS):
                raise ValueError(f'Ingram: encabezados duplicados en {nombre}.')
            datos = bruto.iloc[inicio + 1:].dropna(how='all').copy()
            leidos += len(datos)
            def campo(columna):
                return datos.iloc[:, columnas.index(columna)]
            base = pd.DataFrame({
                'SKU': campo('SKU'),
                'venta neto usd': campo('C REVENDEDOR'),
                'stock actual': pd.to_numeric(campo('STOCK'), errors='coerce'),
            }, index=datos.index)
            resultado = normalizar_productos(base, fecha)
            for destino, origen in [('mpn', 'VDR_PARTNB'), ('name', 'DESC TECNICA'), ('brand', 'VDR_NAME')]:
                resultado[destino] = campo(origen).loc[resultado.index].fillna('').astype(str).str.strip()
            salida.append(resultado)
            usadas.append(nombre)
            break
    archivo.seek(0)
    if not salida:
        return None
    return pd.concat(salida, ignore_index=True), leidos, (
        'Ingram Stock y tránsitos: se usa C Revendedor y solo STOCK inmediato; '
        'TRANSITOS y ETA CD se excluyen.'
    )


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.xlsx'):
        resultado = _leer_stock_y_transitos(archivo, fecha, hojas_seleccionadas)
        if resultado is not None:
            return resultado
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)

