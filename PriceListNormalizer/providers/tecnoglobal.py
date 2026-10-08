"""Reglas de Tecnoglobal. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas
import pandas as pd
import re
from datetime import datetime
from common import normalizar_productos, normalizar_texto_columna, limpiar_numero
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
                linksys = {'MARCA', 'S.K.U.', 'PARTNUMBER', 'DESCRIPCION', 'PRECIO ESPECIAL', 'STOCK DISPONIBLE'}
                cyber = {'COD. TG', 'PARTNUMBER', 'DESCRIPCION', 'STOCK', 'PRECIO VENTA', 'CYBER'}
                plantilla = 'Linksys' if linksys.issubset(cols) else 'Cyber' if cyber.issubset(cols) else None
                if plantilla:
                    obligatorias = linksys if plantilla == 'Linksys' else cyber
                    if any(cols.count(c) != 1 for c in obligatorias):
                        raise ValueError(f'Tecnoglobal: encabezados duplicados en {nombre}.')
                    datos = bruto.iloc[indice + 1:].dropna(how='all')
                    def campo(c):
                        return datos.iloc[:, cols.index(c)]
                    codigo, precio, stock = ('S.K.U.', 'PRECIO ESPECIAL', 'STOCK DISPONIBLE') if plantilla == 'Linksys' else ('COD. TG', 'CYBER', 'STOCK')
                    fecha_tabla = fecha
                    divisa = 'USD' if plantilla == 'Linksys' else 'CLP'
                    if plantilla == 'Cyber':
                        titulo = ' '.join(str(v) for v in bruto.iloc[:indice].to_numpy().flatten() if pd.notna(v))
                        if not re.search(r'precios\s+netos\s+en\s+pesos', titulo, re.I):
                            raise ValueError('Tecnoglobal Cyber: falta confirmar moneda; no se encontró precios netos en pesos.')
                        vigencia = re.search(r'vigencias?\s+hasta\s+el\s+(\d{2}-\d{2}-\d{4})', titulo, re.I)
                        if vigencia:
                            fecha_tabla = min(fecha, datetime.strptime(vigencia.group(1), '%d-%m-%Y').date())
                    else:
                        valores = campo(precio).dropna().astype(str)
                        if not valores.str.contains(r'USD\s*\$', case=False, regex=True).all():
                            raise ValueError('Tecnoglobal Linksys: Precio Especial debe indicar USD$.')
                    base = pd.DataFrame({'SKU': campo(codigo), 'venta neto usd': campo(precio).map(limpiar_numero),
                                         'stock actual': campo(stock).map(limpiar_numero)}, index=datos.index)
                    result = normalizar_productos(base, fecha_tabla)
                    result['mpn'] = campo('PARTNUMBER').loc[result.index].fillna('').astype(str).str.strip()
                    result['name'] = campo('DESCRIPCION').loc[result.index].fillna('').astype(str).str.strip()
                    if 'MARCA' in cols:
                        result['brand'] = campo('MARCA').loc[result.index].fillna('').astype(str).str.strip()
                    result['currency'] = divisa
                    salida.append(result)
                    usadas.append(nombre)
                    leidos += len(datos)
                    break
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
            resultado = pd.concat(salida, ignore_index=True)
            resultado.attrs['currency_policy'] = 'SOURCE'
            return resultado, leidos, ('Hojas procesadas: ' + ', '.join(usadas) +
                '. Componentes: Precio Volumen; Linksys: Precio Especial USD; Cyber: precio Cyber CLP y vigencia limitada al archivo. Monedas sin conversión.')
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
