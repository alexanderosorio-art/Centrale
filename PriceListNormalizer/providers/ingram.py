"""Reglas de Ingram. No se infieren datos de producto ausentes."""
import pandas as pd
from table_reader import ReglasTabla, leer_tablas, PRECIOS, PART_NUMBERS
from common import normalizar_productos, normalizar_texto_columna
from file_readers import leer_hoja_xlsx_con_datos, obtener_nombres_hojas
from catalog_lookup import resolver_por_catalogo

NOMBRE = 'Ingram'
PATRON = r'(?:INGRAM|IM)'
MONEDA = 'USD'
REGLAS = ReglasTabla(
    nombre=NOMBRE,
    codigos=('MATERIAL/SKU', 'INGRAM MICRO SKU', 'IM SKU', 'MATERIAL', 'SKU INGRAM'),
    precios=('COSTO', 'PRECIOS REFERENCIALES', *PRECIOS),
    part_numbers=(*PART_NUMBERS, 'PN'),
    lectura_acotada=True, requiere_descripcion=False, catalogo_por_pn=True,
)
STOCK_TRANSITOS = {
    'VDR_NAME', 'SKU', 'VDR_PARTNB', 'MODELO', 'DESC TECNICA',
    'C REVENDEDOR', 'STOCK', 'TRANSITOS', 'ETA CD',
}
PN_QTY_PRECIO = {'PN', 'QTY', 'PRECIO'}
INVENTARIO_MARCA = {'SKU', 'VDR_PARTNBR', 'DESCRIPCION', 'BOH', 'P.LISTA'}


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


def _leer_pn_con_catalogo(archivo, fecha, hojas_seleccionadas=None):
    nombres = hojas_seleccionadas if hojas_seleccionadas is not None else obtener_nombres_hojas(archivo)
    salida, leidos, pendientes = [], 0, 0
    for nombre in nombres:
        bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
        for inicio, fila in bruto.iterrows():
            columnas = [normalizar_texto_columna(v) for v in fila]
            # Consolidado por mayorista: la primera columna lleva el nombre
            # Ingram en lugar de PN; sus valores son referencias del producto.
            if {'INGRAM', 'QTY', 'PRECIO'}.issubset(columnas) and 'PN' not in columnas:
                columnas = ['PN' if c == 'INGRAM' else c for c in columnas]
            if not PN_QTY_PRECIO.issubset(columnas):
                continue
            if any(columnas.count(c) != 1 for c in PN_QTY_PRECIO):
                raise ValueError(f'Ingram: encabezados duplicados en {nombre}.')
            datos = bruto.iloc[inicio + 1:].dropna(how='all').copy()
            leidos += len(datos)
            def campo(columna):
                return datos.iloc[:, columnas.index(columna)]
            tabla = pd.DataFrame({
                'provider_code': '',
                'currency_unaware_cost_neto': campo('PRECIO'),
                'quantity': campo('QTY'),
                'mpn': campo('PN'),
                'name': '',
                'brand': '',
            }, index=datos.index)
            tabla, por_revisar, detalle = resolver_por_catalogo(tabla, NOMBRE)
            pendientes += len(por_revisar)
            tabla = tabla.drop(index=por_revisar)
            if tabla.empty:
                continue
            base = tabla.rename(columns={
                'provider_code': 'SKU',
                'currency_unaware_cost_neto': 'venta neto usd',
                'quantity': 'stock actual',
            })
            resultado = normalizar_productos(base, fecha)
            resultado['mpn'] = tabla.loc[resultado.index, 'mpn'].fillna('').astype(str).str.strip()
            salida.append(resultado)
            break
    archivo.seek(0)
    if not salida:
        return None
    texto = 'Ingram: SKU recuperado desde catálogo privado usando PN.'
    if pendientes:
        texto += f' Filas sin coincidencia única excluidas: {pendientes}.'
    return pd.concat(salida, ignore_index=True), leidos, texto


def _leer_inventario_marca(archivo, fecha, hojas_seleccionadas=None):
    """Lee inventarios de marca de Ingram que sí informan precio de lista."""
    nombres = hojas_seleccionadas if hojas_seleccionadas is not None else obtener_nombres_hojas(archivo)
    salida, leidos, usadas = [], 0, []
    for nombre in nombres:
        bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
        for inicio, fila in bruto.iterrows():
            columnas = [normalizar_texto_columna(v) for v in fila]
            if not INVENTARIO_MARCA.issubset(columnas):
                continue
            if any(columnas.count(c) != 1 for c in INVENTARIO_MARCA):
                raise ValueError(f'Ingram: encabezados duplicados en {nombre}.')
            datos = bruto.iloc[inicio + 1:].dropna(how='all').copy()
            leidos += len(datos)

            def campo(columna):
                return datos.iloc[:, columnas.index(columna)]

            base = pd.DataFrame({
                'SKU': campo('SKU'),
                'venta neto usd': campo('P.LISTA'),
                'stock actual': campo('BOH'),
            }, index=datos.index)
            resultado = normalizar_productos(base, fecha)
            resultado['mpn'] = campo('VDR_PARTNBR').loc[resultado.index].fillna('').astype(str).str.strip()
            resultado['name'] = campo('DESCRIPCION').loc[resultado.index].fillna('').astype(str).str.strip()
            # "Brand" en este archivo es una categoría comercial, no una marca
            # explícita del producto. Se conserva vacío para no inventar datos.
            salida.append(resultado)
            usadas.append(nombre)
            break
    archivo.seek(0)
    if not salida:
        return None
    return pd.concat(salida, ignore_index=True), leidos, (
        'Inventario de marca Ingram: se usa P.Lista y BOH. '
        'OPEN BOX/BAD BOX se excluyen; brand queda vacío si no viene explícito.'
    )


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.xlsx'):
        resultado = _leer_stock_y_transitos(archivo, fecha, hojas_seleccionadas)
        if resultado is not None:
            return resultado
        resultado = _leer_inventario_marca(archivo, fecha, hojas_seleccionadas)
        if resultado is not None:
            return resultado
        resultado = _leer_pn_con_catalogo(archivo, fecha, hojas_seleccionadas)
        if resultado is not None:
            return resultado
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)

