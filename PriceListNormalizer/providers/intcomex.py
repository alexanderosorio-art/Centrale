"""Reglas de Intcomex. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas
import pandas as pd
import re
from datetime import date
from common import normalizar_productos, normalizar_texto_columna, limpiar_numero
from file_readers import leer_csv, detectar_encabezado, leer_hoja_xlsx_con_datos, palabras_clave_encabezado, obtener_nombres_hojas

NOMBRE = 'Intcomex'
PATRON = r'(?:INTCOMEX|IX)'
MONEDA = 'USD'
ASUS_BASE = {'SKU INTCOMEX', 'NUMERO DE PARTE', 'STOCK REFERENCIAL', 'DETALLE'}
ASUS_PRECIOS = {'PRECIO USD (S/IVA)', 'PRECIO (S/IVA)'}
REGLAS = ReglasTabla(
    nombre=NOMBRE, codigos=('SKU', 'MATERIAL/SKU', 'MATERIAL', 'CODIGO'),
    moneda_fija='USD', catalogo_por_pn=True,
)
HIKVISION = {'SKU', 'PART #', 'DESCRIPCION', 'DPV', 'UNIT PRICE$'}
PRECIOS_TOP = {'SKU', 'PART NUMBER MARCA', 'PRODUCT NAME', 'STOCK', 'PRECIOS TOP'}
DELL = {'SKU', 'PN DELL', 'DESCRIPCION', 'PRECIO USD', 'STOCK REF'}
HP_SEMANAL = {'LOCAL SKU', 'MPN', 'PRODUCT NAME (LOCAL)', 'STOCK', 'PRECIO NORMAL'}
LOGITECH = {'SKU XCL', 'LOGITECH PART NUMBER', 'DESCRIPCION', 'STOCK', 'COSTO NETO USD'}
CLIENTES_ESTRATEGICOS = {'PRODUCT ID', 'MPN', 'PRODUCT NAME', 'MARCA', 'STOCK', 'PRECIO ESPECIAL NETO UNIT. CLIENTES ESTRATEGICOS'}
FORZA = {'SKU', 'MPN', 'DETALLE', 'DISPONIBLE', 'PRECIO ESPECIAL'}
NEXXT = {'PRODUCT ID', 'MPN', 'PRODUCT NAME', 'DISPONIBLE', 'PRECIO ESPECIAL'}


def leer_intcomex_xlsx(archivo):
    bruto = leer_hoja_xlsx_con_datos(archivo)
    if bruto.empty:
        raise ValueError('La primera hoja de Intcomex no contiene datos.')
    columnas_asus = {'SKU INTCOMEX', 'NUMERO DE PARTE', 'PRECIO USD (S/IVA)',
                     'STOCK REFERENCIAL', 'DETALLE'}
    candidatos = [i for i, fila in bruto.iterrows()
                  if (ASUS_BASE.issubset({normalizar_texto_columna(v) for v in fila})
                      and ASUS_PRECIOS.intersection({normalizar_texto_columna(v) for v in fila}))
                  or HIKVISION.issubset({normalizar_texto_columna(v) for v in fila})
                  or PRECIOS_TOP.issubset({normalizar_texto_columna(v) for v in fila})
                  or DELL.issubset({normalizar_texto_columna(v) for v in fila})
                  or HP_SEMANAL.issubset({normalizar_texto_columna(v) for v in fila})
                  or FORZA.issubset({normalizar_texto_columna(v) for v in fila})
                  or NEXXT.issubset({normalizar_texto_columna(v) for v in fila})
                  or CLIENTES_ESTRATEGICOS.issubset({normalizar_texto_columna(v) for v in fila})]
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


def procesar_disponible_especial(df, fecha, plantilla):
    columnas = [normalizar_texto_columna(c) for c in df.columns]
    requeridas = FORZA if plantilla == 'Forza' else NEXXT
    if any(columnas.count(c) != 1 for c in requeridas):
        raise ValueError(f'Intcomex {plantilla}: encabezados duplicados.')
    def campo(c):
        return df.iloc[:, columnas.index(c)]
    codigo, nombre = ('SKU', 'DETALLE') if plantilla == 'Forza' else ('PRODUCT ID', 'PRODUCT NAME')
    base = pd.DataFrame({'SKU': campo(codigo),
                         'venta neto usd': campo('PRECIO ESPECIAL').map(limpiar_numero),
                         'stock actual': pd.to_numeric(campo('DISPONIBLE'), errors='coerce')}, index=df.index)
    resultado = normalizar_productos(base, fecha)
    resultado['mpn'] = campo('MPN').loc[resultado.index].fillna('').astype(str).str.strip()
    resultado['name'] = campo(nombre).loc[resultado.index].fillna('').astype(str).str.strip()
    return resultado


def procesar_intcomex_asus(df, expiry_date):
    nombres = [normalizar_texto_columna(c) for c in df.columns]
    precios = ASUS_PRECIOS.intersection(nombres)
    if len(precios) != 1 or any(nombres.count(c) != 1 for c in ASUS_BASE | precios):
        raise ValueError('Intcomex ASUS: columnas requeridas duplicadas o precio ambiguo.')
    columnas = {normalizar_texto_columna(c): c for c in df.columns}
    base = pd.DataFrame({
        'SKU': df[columnas['SKU INTCOMEX']],
        'venta neto usd': df[columnas[next(iter(precios))]],
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


def procesar_intcomex_logitech(df, fecha):
    cols = [normalizar_texto_columna(c) for c in df.columns]
    if any(cols.count(c) != 1 for c in LOGITECH):
        raise ValueError('Intcomex Logitech: columnas requeridas duplicadas.')
    def campo(c):
        return df.iloc[:, cols.index(c)]
    def cantidad(v):
        texto = str(v).strip()
        if re.fullmatch(r'\d{1,3}(?:,\d{3})+', texto):
            texto = texto.replace(',', '')
        if not re.fullmatch(r'\d+(?:\.0+)?\s*\+?', texto):
            return None
        return pd.to_numeric(texto.rstrip('+').strip(), errors='coerce')
    base = pd.DataFrame({'SKU': campo('SKU XCL'), 'venta neto usd': campo('COSTO NETO USD'),
                         'stock actual': campo('STOCK').map(cantidad)}, index=df.index)
    resultado = normalizar_productos(base, fecha)
    for destino, origen in [('mpn', 'LOGITECH PART NUMBER'), ('name', 'DESCRIPCION')]:
        resultado[destino] = campo(origen).loc[resultado.index].fillna('').astype(str).str.strip()
    return resultado


def procesar_clientes_estrategicos(df, fecha, nombre):
    cols = [normalizar_texto_columna(c) for c in df.columns]
    if any(cols.count(c) != 1 for c in CLIENTES_ESTRATEGICOS):
        raise ValueError('Intcomex: encabezados de clientes estratégicos duplicados.')
    meses = {'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
             'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12}
    vigencia = re.search(r'\bHASTA\s+(\d{1,2})\s+(?:DE\s+)?(' + '|'.join(meses) + r')\s+(?:DE\s+)?(\d{4})\b', normalizar_texto_columna(nombre))
    if vigencia:
        fecha = date(int(vigencia[3]), meses[vigencia[2]], int(vigencia[1]))
    def campo(c):
        return df.iloc[:, cols.index(c)]
    base = pd.DataFrame({'SKU': campo('PRODUCT ID'),
        'venta neto usd': campo('PRECIO ESPECIAL NETO UNIT. CLIENTES ESTRATEGICOS').map(limpiar_numero),
        'stock actual': pd.to_numeric(campo('STOCK'), errors='coerce')}, index=df.index)
    resultado = normalizar_productos(base, fecha)
    def texto(v):
        if pd.isna(v):
            return ''
        if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v).is_integer():
            return str(int(v))
        return str(v).strip()
    for destino, origen in [('mpn', 'MPN'), ('name', 'PRODUCT NAME'), ('brand', 'MARCA')]:
        resultado[destino] = campo(origen).loc[resultado.index].map(texto)
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
    if FORZA.issubset(columnas) or NEXXT.issubset(columnas):
        plantilla = 'Forza' if FORZA.issubset(columnas) else 'Nexxt'
        resultado = procesar_disponible_especial(df, fecha, plantilla)
        return resultado, len(df), f'Intcomex {plantilla}: Precio Especial y solo Disponible; Tránsito no se suma. Marca no inferida.'
    elif CLIENTES_ESTRATEGICOS.issubset(columnas):
        resultado = procesar_clientes_estrategicos(df, fecha, archivo.name)
        return resultado, len(df), 'Intcomex: Product ID como código; precio especial Clientes Estratégicos. MPN, nombre y marca explícitos. Se conserva la vigencia indicada en el nombre del archivo, aunque esté vencida.'
    elif LOGITECH.issubset(columnas):
        resultado = procesar_intcomex_logitech(df, fecha)
        return resultado, len(df), 'Intcomex Logitech: COSTO NETO USD; no se usa PVP ni costo por volumen. Stock con coma de miles. Marca no inferida.'
    elif HP_SEMANAL.issubset(columnas):
        resultado = procesar_intcomex_hp_semanal(df, fecha)
        return resultado, len(df), 'Intcomex HP: precio promocional con respaldo normal. Solo Stock; Llegada no se suma. Marca no inferida.'
    elif DELL.issubset(columnas):
        resultado = procesar_intcomex_dell(df, fecha)
        return resultado, len(df), 'Intcomex Dell: Precio USD y Stock Ref. Se excluyen stock cero, tránsito, Pronto Stock y hojas de garantías sin stock. Marca no inferida.'
    elif PRECIOS_TOP.issubset(columnas):
        resultado = procesar_intcomex_top(df, fecha)
    elif HIKVISION.issubset(columnas):
        resultado = procesar_intcomex_hikvision(df, fecha)
    elif ASUS_BASE.issubset(columnas) and ASUS_PRECIOS.intersection(columnas):
        resultado = procesar_intcomex_asus(df, fecha)
    elif {'PART NUMBER (MPN)', 'PRECIO ESPECIAL NETO UNIT. CENTRALE'}.issubset(columnas):
        resultado = procesar_intcomex_wd(df, fecha)
    elif {'SKU', 'VENTA NETO USD', 'STOCK ACTUAL'}.issubset(columnas):
        # Formato interno ya normalizado, con SKU explícito.
        resultado = normalizar_productos(df, fecha)
    else:
        # El lector común permite recuperar el SKU desde el catálogo privado
        # si una lista trae PN, precio y stock, pero no código Intcomex.
        return leer_tablas(archivo, fecha, moneda, permitir_pn, hojas_seleccionadas, reglas=REGLAS)
    return resultado, len(df), 'Se excluyen códigos vacíos, precios inválidos y stock no positivo.'

