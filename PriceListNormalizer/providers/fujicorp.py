"""Reglas de Fujicorp. No se infieren datos de producto ausentes."""
import pandas as pd
from table_reader import ReglasTabla, leer_tablas, PRECIOS
from common import normalizar_productos, normalizar_texto_columna, limpiar_numero
from file_readers import leer_hoja_xlsx_con_datos

NOMBRE = 'Fujicorp'
PATRON = r'FUJICORP'
MONEDA = 'CLP'
REGLAS = ReglasTabla(
    nombre=NOMBRE, codigos=('CODIGO FUJICORP', 'CODIGO', 'SKU'),
    precios=('NETO', 'PMIN', *PRECIOS), moneda_fija='CLP', preferir_oferta=True,
)


def _leer_lista_llegada(archivo, fecha):
    """Lista ACER: la cantidad viene en una columna fechada de llegada."""
    if not archivo.name.lower().endswith(('.xlsx', '.xls')):
        return None
    bruto = leer_hoja_xlsx_con_datos(archivo)
    for inicio, fila in bruto.iterrows():
        columnas = [normalizar_texto_columna(v) for v in fila]
        codigo = 'CODIGO FUJICORP'
        requeridas = {codigo, 'ITEM NO.', 'DESCRIPCION SOFTLAND', 'NETO'}
        llegada = next((c for c in columnas if 'LLEGADA' in c), None)
        if not requeridas.issubset(columnas) or not llegada:
            continue
        if any(columnas.count(c) != 1 for c in requeridas | {llegada}):
            raise ValueError('Fujicorp: encabezados duplicados en la lista de llegada.')
        datos = bruto.iloc[inicio + 1:].dropna(how='all').copy()
        def campo(columna):
            return datos.iloc[:, columnas.index(columna)]
        base = pd.DataFrame({
            'SKU': campo(codigo),
            'venta neto usd': campo('NETO').map(limpiar_numero),
            'stock actual': campo(llegada).map(limpiar_numero),
        }, index=datos.index)
        resultado = normalizar_productos(base, fecha)
        resultado['mpn'] = campo('ITEM NO.').loc[resultado.index].fillna('').astype(str).str.strip()
        resultado['name'] = campo('DESCRIPCION SOFTLAND').loc[resultado.index].fillna('').astype(str).str.strip()
        resultado['currency'] = 'CLP'
        return resultado, len(datos), (
            f'Fujicorp: NETO CLP y cantidad informada en “{llegada.title()}”. '
            'Código Fujicorp como provider_code; Item No. como PN. Marca no inferida.'
        )
    return None


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    resultado = _leer_lista_llegada(archivo, fecha)
    if resultado is not None:
        return resultado
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)

