"""Reglas de Tecnoglobal. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas
import pandas as pd
from common import normalizar_productos, normalizar_texto_columna
from file_readers import obtener_nombres_hojas, leer_hoja_xlsx_con_datos

NOMBRE = 'Tecnoglobal'
PATRON = r'(?:TECNO[\W_]*GLOBAL|TG)'
MONEDA = 'USD'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('CODIGO TG', 'CODIGO', 'CODIGO SISTEMA', 'SKU'))


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.xlsx'):
        nombres = obtener_nombres_hojas(archivo) if hojas_seleccionadas is None else hojas_seleccionadas
        requeridas = {'CODIGOARTICULO', 'PARTNUMBER', 'DESCRIPCORTA', 'DESCRIPCIONMARCA', 'STOCK', 'PRECIO VOLUMEN'}
        salida, leidos, usadas = [], 0, []
        for nombre in nombres:
            bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
            for indice, fila in bruto.iterrows():
                cols = [normalizar_texto_columna(v) for v in fila]
                if not requeridas.issubset(cols):
                    continue
                if any(cols.count(c) != 1 for c in requeridas):
                    raise ValueError(f'Tecnoglobal: columnas duplicadas en {nombre}.')
                datos = bruto.iloc[indice + 1:].dropna(how='all')
                def campo(c):
                    return datos.iloc[:, cols.index(c)]
                base = pd.DataFrame({'SKU': campo('CODIGOARTICULO'),
                    'venta neto usd': campo('PRECIO VOLUMEN'),
                    'stock actual': pd.to_numeric(campo('STOCK'), errors='coerce')}, index=datos.index)
                result = normalizar_productos(base, fecha)
                for destino, origen in [('mpn', 'PARTNUMBER'), ('name', 'DESCRIPCORTA'), ('brand', 'DESCRIPCIONMARCA')]:
                    result[destino] = campo(origen).loc[result.index].fillna('').astype(str).str.strip()
                result['currency'] = moneda
                salida.append(result)
                usadas.append(nombre)
                leidos += len(datos)
                break
        if salida:
            # Mantener también las hojas de otras plantillas compatibles del lote.
            restantes = [n for n in nombres if n not in usadas]
            for nombre in restantes:
                try:
                    otro, cantidad, _ = leer_tablas(archivo, fecha, moneda, permitir_pn, [nombre], reglas=REGLAS)
                except ValueError as error:
                    if str(error) != 'No se encontraron hojas con código, stock y precio compatibles.':
                        raise
                else:
                    salida.append(otro)
                    leidos += cantidad
            return pd.concat(salida, ignore_index=True), leidos, ('Hojas de componentes: ' + ', '.join(usadas) +
                '. Se usa Precio Volumen por elección del usuario; no se usa Precio Venta.')
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
