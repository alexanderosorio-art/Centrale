"""Reglas de Intcomex. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas
import pandas as pd
import re
from common import normalizar_productos, normalizar_texto_columna, limpiar_numero
from file_readers import leer_csv, detectar_encabezado, leer_hoja_xlsx_con_datos, palabras_clave_encabezado, obtener_nombres_hojas

NOMBRE = 'Intcomex'
PATRON = r'(?:INTCOMEX|IX)'
MONEDA = 'USD'
REGLAS = ReglasTabla(nombre=NOMBRE, codigos=('SKU', 'MATERIAL/SKU', 'MATERIAL', 'CODIGO'), moneda_fija='USD')
HIKVISION = {'SKU', 'PART #', 'DESCRIPCION', 'DPV', 'UNIT PRICE$'}
PRECIOS_TOP = {'SKU', 'PART NUMBER MARCA', 'PRODUCT NAME', 'STOCK', 'PRECIOS TOP'}
DELL = {'SKU', 'PN DELL', 'DESCRIPCION', 'PRECIO USD', 'STOCK REF'}
HP_SEMANAL = {'LOCAL SKU', 'MPN', 'PRODUCT NAME (LOCAL)', 'STOCK', 'PRECIO NORMAL'}


def leer_intcomex_xlsx(archivo):
    bruto = leer_hoja_xlsx_con_datos(archivo)
    if bruto.empty:
        raise ValueError('La primera hoja de Intcomex no contiene datos.')
    columnas_asus = {'SKU INTCOMEX', 'NUMERO DE PARTE', 'PRECIO USD (S/IVA)',
                     'STOCK REFERENCIAL', 'DETALLE'}
    candidatos = [i for i, fila in bruto.iterrows()
                  if columnas_asus.issubset({normalizar_texto_columna(v) for v in fila})
                  or HIKVISION.issubset({normalizar_texto_columna(v) for v in fila})
                  or PRECIOS_TOP.issubset({normalizar_texto_columna(v) for v in fila})
                  or DELL.issubset({normalizar_texto_columna(v) for v in fila})
                  or HP_SEMANAL.issubset({normalizar_texto_columna(v) for v in fila})]
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


def procesar_intcomex_top(df, fecha):
    nombres = [normalizar_texto_columna(c) for c in df.columns]
    if any(nombres.count(c) != 1 for c in PRECIOS_TOP | ({'MARCA'} if 'MARCA' in nombres else set())):
        raise ValueError('Intcomex: columnas duplicadas en la plantilla Precios Top.')
    columnas = dict(zip(nombres, df.columns))
    base = pd.DataFrame({
        'SKU': df[columnas['SKU']],
        'venta neto usd': df[columnas['PRECIOS TOP']],
        'stock actual': pd.to_numeric(df[columnas['STOCK']], errors='coerce'),
    }, index=df.index)
    resultado = normalizar_productos(base, fecha)
    for destino, origen in [('mpn', 'PART NUMBER MARCA'), ('name', 'PRODUCT NAME'), ('brand', 'MARCA')]:
        if origen in columnas:
            resultado[destino] = df.loc[resultado.index, columnas[origen]].fillna('').astype(str).str.strip()
    return resultado


def leer_hpe(archivo, fecha, moneda, nombres):
    """Plantilla HPE aprobada: solo stock explícito con entrega inmediata."""
    salida, leidos, usadas = [], 0, []
    for nombre in nombres:
        norm = normalizar_texto_columna(nombre)
        if norm not in ('LP GEN 11', 'LP GEN12', 'NETWORKING'):
            continue
        bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
        for indice, fila in bruto.iterrows():
            cols = [normalizar_texto_columna(v) for v in fila]
            if norm == 'NETWORKING':
                plantilla = ['NETWORKING', 'NONE', 'NONE', 'QTY DISP', 'PRECIO UN USD', 'PRECIO ESPECIAL USD', 'DISPONIBILIDAD', 'SKU INTOCMEX']
                # PN y descripción no tienen título: validar la plantilla exacta.
                if len(cols) < 8 or cols[0] != plantilla[0] or cols[3:8] != plantilla[3:8] or any(pd.notna(v) for v in fila.iloc[1:3]):
                    continue
                cod, pn, desc, stockcol, normal, promo, entrega = 7, 1, 2, 3, 4, 5, 6
            else:
                requeridas = {'SKU INTCOMEX', 'DESCRIPCION', 'PRECIO UN VENTA', 'PRECIO PROMO REFERENCIAL'}
                pncol = next((c for c in ('PN', 'PART NUMBER') if c in cols), None)
                tiempocol = next((c for c in ('TIEMPO ENTREGA', 'TIEMPO DE ENTREGA') if c in cols), None)
                if not requeridas.issubset(cols) or not pncol or not tiempocol:
                    continue
                if any(cols.count(c) != 1 for c in requeridas | {pncol, tiempocol}):
                    raise ValueError(f'Intcomex HPE: columnas duplicadas en {nombre}.')
                cod, pn, desc = [cols.index(c) for c in ('SKU INTCOMEX', pncol, 'DESCRIPCION')]
                normal, promo = [cols.index(c) for c in ('PRECIO UN VENTA', 'PRECIO PROMO REFERENCIAL')]
                entrega = cols.index(tiempocol)
                stockcol = None
            datos = bruto.iloc[indice + 1:].dropna(how='all')
            leidos += len(datos)
            estado = datos.iloc[:, entrega].map(normalizar_texto_columna)
            inmediato = estado.str.contains(r'\bENT(?:R)?REGA INMEDIATA\b', regex=True)
            inmediato &= ~estado.str.contains(r'TRANSITO|FABRICA|PEDIDO|NO DISPONIBLE|SIN STOCK', regex=True)
            if stockcol is None:
                cantidades = pd.to_numeric(estado.str.extract(r'^\s*(\d+)\s*(?:UNIDADES|UNIDAD|UN)\b', expand=False), errors='coerce')
            else:
                cantidades = pd.to_numeric(datos.iloc[:, stockcol], errors='coerce')
            precio_normal = datos.iloc[:, normal].map(limpiar_numero)
            promocion = datos.iloc[:, promo].map(limpiar_numero)
            precio = promocion.where(promocion > 0, precio_normal)
            base = pd.DataFrame({'SKU': datos.iloc[:, cod], 'venta neto usd': precio,
                                 'stock actual': cantidades.where(inmediato)}, index=datos.index)
            result = normalizar_productos(base, fecha)
            result['mpn'] = datos.loc[result.index].iloc[:, pn].fillna('').astype(str).str.strip()
            result['name'] = datos.loc[result.index].iloc[:, desc].fillna('').astype(str).str.strip()
            result['currency'] = moneda
            salida.append(result)
            usadas.append(nombre)
            break
        else:
            raise ValueError(f'Intcomex HPE: estructura no reconocida en {nombre}; revisa los encabezados.')
    archivo.seek(0)
    if not salida:
        raise ValueError('Intcomex HPE: no se encontraron hojas de productos compatibles.')
    return pd.concat(salida, ignore_index=True), leidos, ('Hojas HPE: ' + ', '.join(usadas) +
        '. Solo entrega inmediata con cantidad explícita; se excluye tránsito y pedido a fábrica. Precio promocional con respaldo normal.')


def procesar_intcomex_dell(df, fecha):
    cols = [normalizar_texto_columna(c) for c in df.columns]
    if any(cols.count(c) != 1 for c in DELL):
        raise ValueError('Intcomex Dell: columnas requeridas duplicadas.')
    # Hay encabezados repetidos; se excluyen junto con las secciones sin datos.
    datos = df.loc[df.iloc[:, cols.index('SKU')].map(normalizar_texto_columna).ne('SKU')]
    def campo(c):
        return datos.iloc[:, cols.index(c)]
    base = pd.DataFrame({'SKU': campo('SKU'), 'venta neto usd': campo('PRECIO USD'),
        'stock actual': pd.to_numeric(campo('STOCK REF'), errors='coerce')}, index=datos.index)
    resultado = normalizar_productos(base, fecha)
    for destino, origen in [('mpn', 'PN DELL'), ('name', 'DESCRIPCION')]:
        resultado[destino] = campo(origen).loc[resultado.index].fillna('').astype(str).str.strip()
    return resultado


def procesar_intcomex_hp_semanal(df, fecha):
    cols = [normalizar_texto_columna(c) for c in df.columns]
    promos = [c for c in cols if c == 'PRECIO PROMO' or c.startswith('PRECIO PROMO ')]
    if len(promos) > 1 or any(cols.count(c) != 1 for c in HP_SEMANAL):
        raise ValueError('Intcomex HP: columnas duplicadas o múltiples precios promocionales; revisa la lista.')
    def campo(c):
        return df.iloc[:, cols.index(c)]
    precio = campo('PRECIO NORMAL').map(limpiar_numero)
    if promos:
        promocion = campo(promos[0]).map(limpiar_numero)
        precio = promocion.where(promocion > 0, precio)
    base = pd.DataFrame({'SKU': campo('LOCAL SKU'), 'venta neto usd': precio,
        'stock actual': pd.to_numeric(campo('STOCK'), errors='coerce')}, index=df.index)
    resultado = normalizar_productos(base, fecha)
    for destino, origen in [('mpn', 'MPN'), ('name', 'PRODUCT NAME (LOCAL)')]:
        resultado[destino] = campo(origen).loc[resultado.index].fillna('').astype(str).str.strip()
    return resultado


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.pdf'):
        return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
    archivo.seek(0)
    if archivo.name.lower().endswith('.csv'):
        df = leer_csv(archivo)
    elif archivo.name.lower().endswith('.xlsx'):
        nombres = obtener_nombres_hojas(archivo)
        if any(normalizar_texto_columna(n) in ('LP GEN 11', 'LP GEN12') for n in nombres):
            return leer_hpe(archivo, fecha, moneda, nombres if hojas_seleccionadas is None else hojas_seleccionadas)
        df = leer_intcomex_xlsx(archivo)
    else:
        encabezado = detectar_encabezado(archivo)
        archivo.seek(0)
        df = pd.read_excel(archivo, header=encabezado)
    columnas = {normalizar_texto_columna(c) for c in df.columns}
    if HP_SEMANAL.issubset(columnas):
        resultado = procesar_intcomex_hp_semanal(df, fecha)
        return resultado, len(df), 'Intcomex HP: precio promocional con respaldo normal. Solo Stock; Llegada no se suma. Marca no inferida.'
    elif DELL.issubset(columnas):
        resultado = procesar_intcomex_dell(df, fecha)
        return resultado, len(df), 'Intcomex Dell: Precio USD y Stock Ref. Se excluyen stock cero, tránsito, Pronto Stock y hojas de garantías sin stock. Marca no inferida.'
    elif PRECIOS_TOP.issubset(columnas):
        resultado = procesar_intcomex_top(df, fecha)
    elif HIKVISION.issubset(columnas):
        resultado = procesar_intcomex_hikvision(df, fecha)
    elif {'SKU INTCOMEX', 'NUMERO DE PARTE', 'PRECIO USD (S/IVA)', 'STOCK REFERENCIAL', 'DETALLE'}.issubset(columnas):
        resultado = procesar_intcomex_asus(df, fecha)
    elif {'PART NUMBER (MPN)', 'PRECIO ESPECIAL NETO UNIT. CENTRALE'}.issubset(columnas):
        resultado = procesar_intcomex_wd(df, fecha)
    else:
        resultado = normalizar_productos(df, fecha)
    return resultado, len(df), 'Se excluyen códigos vacíos, precios inválidos y stock no positivo.'
