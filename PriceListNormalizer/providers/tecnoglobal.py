"""Reglas de Tecnoglobal. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas, PART_NUMBERS, PRECIOS
import pandas as pd
import re
from datetime import datetime
from common import normalizar_productos, normalizar_texto_columna, limpiar_numero
from file_readers import obtener_nombres_hojas, leer_hoja_xlsx_con_datos

NOMBRE = 'Tecnoglobal'
PATRON = r'(?:TECNO[\W_]*GLOBAL|TG)'
MONEDA = 'USD'
REGLAS = ReglasTabla(
    nombre=NOMBRE, codigos=('CODIGO TG', 'CODIGO', 'CODIGO SISTEMA', 'SKU', 'COD. TG', 'COD TG'),
    precios=(*PRECIOS, 'VALOR LISTA', 'U$'),
    part_numbers=(*PART_NUMBERS, 'PN', 'ITEM / DESCRIPTION'),
    stocks=('STOCK SIN RESERVA', 'CANTIDAD', 'STOCK DISPONIBLE', 'STOCK REFERENCIAL', 'STOCK', 'QTY'),
    catalogo_por_pn=True, requiere_descripcion=False,
)


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.xlsx'):
        nombres = obtener_nombres_hojas(archivo) if hojas_seleccionadas is None else hojas_seleccionadas
        requeridas = {'CODIGOARTICULO', 'PARTNUMBER', 'DESCRIPCORTA', 'DESCRIPCIONMARCA', 'STOCK', 'PRECIO VOLUMEN'}
        salida, leidos, usadas = [], 0, []
        for nombre in nombres:
            bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
            for indice, fila in bruto.iterrows():
                cols = [normalizar_texto_columna(v) for v in fila]
                aging = {'SKU', 'PARTNUMBER', 'DESCRIPCION', 'STOCK', 'VALOR', 'AGING', 'VALOR AGING'}
                if aging.issubset(cols):
                    if any(cols.count(c) != 1 for c in aging):
                        raise ValueError(f'Tecnoglobal Aging: encabezados duplicados en {nombre}.')
                    datos = bruto.iloc[indice + 1:].dropna(how='all')
                    def campo(c):
                        return datos.iloc[:, cols.index(c)]
                    cantidad_aging = pd.to_numeric(campo('AGING'), errors='coerce')
                    precio_aging = campo('VALOR AGING').map(limpiar_numero)
                    usar_aging = (cantidad_aging > 0) & (precio_aging > 0)
                    base = pd.DataFrame({'SKU': campo('SKU'),
                        'venta neto usd': precio_aging.where(usar_aging, campo('VALOR').map(limpiar_numero)),
                        'stock actual': cantidad_aging.where(usar_aging, pd.to_numeric(campo('STOCK'), errors='coerce'))}, index=datos.index)
                    result = normalizar_productos(base, fecha)
                    result['mpn'] = campo('PARTNUMBER').loc[result.index].fillna('').astype(str).str.strip()
                    result['name'] = campo('DESCRIPCION').loc[result.index].fillna('').astype(str).str.strip()
                    result['currency'] = moneda
                    salida.append(result)
                    usadas.append(nombre)
                    leidos += len(datos)
                    break
                lenovo = {'CODIGO', 'PART NUMBER', 'DESCRIPCION', 'ESTADO', 'CANTIDAD', 'PRECIO STOCK USD'}
                if lenovo.issubset(cols):
                    if any(cols.count(c) != 1 for c in lenovo):
                        raise ValueError(f'Tecnoglobal Lenovo: encabezados duplicados en {nombre}.')
                    datos = bruto.iloc[indice + 1:].dropna(how='all')
                    def campo(c):
                        return datos.iloc[:, cols.index(c)]
                    disponible = campo('ESTADO').map(normalizar_texto_columna).eq('EN STOCK')
                    codigos = campo('CODIGO').fillna('').astype(str).str.strip()
                    producto = disponible & codigos.ne('') & codigos.ne('Código')
                    base = pd.DataFrame({'SKU': codigos,
                        'venta neto usd': campo('PRECIO STOCK USD').map(limpiar_numero),
                        'stock actual': pd.to_numeric(campo('CANTIDAD'), errors='coerce').where(producto)}, index=datos.index)
                    result = normalizar_productos(base, fecha)
                    result['mpn'] = campo('PART NUMBER').loc[result.index].fillna('').astype(str).str.strip()
                    result['name'] = campo('DESCRIPCION').loc[result.index].fillna('').astype(str).str.strip()
                    result['currency'] = 'USD'
                    salida.append(result)
                    usadas.append(nombre)
                    leidos += len(datos)
                    break
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
                    usadas.append(nombre)
            resultado = pd.concat(salida, ignore_index=True)
            resultado.attrs['currency_policy'] = 'SOURCE'
            return resultado, leidos, ('Hojas procesadas: ' + ', '.join(usadas) +
                '. Aging: VALOR AGING con cantidad AGING si ambos son positivos; en los demás, VALOR con STOCK. Lenovo: Precio Stock USD, solo En stock, sin garantías ni próximas llegadas. Componentes: Precio Volumen; Linksys: Precio Especial USD; Cyber: precio Cyber CLP y vigencia limitada al archivo. Monedas sin conversión.')
    return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)

