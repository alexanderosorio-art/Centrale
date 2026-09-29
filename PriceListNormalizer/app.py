import streamlit as st
import pandas as pd
import csv
import re
import hashlib

from datetime import datetime, time, timedelta
from calendar import monthrange
from io import BytesIO
import json
from html import escape
import streamlit.components.v1 as components


def palabras_clave_encabezado():
    return [
        "sku",
        "pn",
        "part number",
        "material",
        "stock",
        "precio",
        "price",
        "cost",
        "quantity",
        "venta neto usd",
        "stock actual"
    ]


def detectar_csv(archivo):
    archivo.seek(0)
    contenido = archivo.read()
    if isinstance(contenido, bytes):
        try:
            texto = contenido.decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            texto = contenido.decode("latin-1")
            encoding = "latin-1"
    else:
        texto = contenido
        encoding = None

    mejor_fila = 0
    mejor_delimitador = ","
    mejor_puntaje = 0
    for indice, linea in enumerate(texto.splitlines()):
        for delimitador in [",", ";", "\t", "|"]:
            celdas = next(csv.reader([linea], delimiter=delimitador))
            texto_fila = " ".join(celdas).lower()
            puntaje = sum(
                palabra in texto_fila
                for palabra in palabras_clave_encabezado()
            )
            if puntaje > mejor_puntaje:
                mejor_fila = indice
                mejor_delimitador = delimitador
                mejor_puntaje = puntaje

    return mejor_fila, mejor_delimitador, encoding


def detectar_encabezado(archivo):
    if archivo.name.lower().endswith(".csv"):
        return detectar_csv(archivo)[0]

    archivo.seek(0)
    df_raw = pd.read_excel(
        archivo,
        header=None
    )

    palabras_clave = [
        *palabras_clave_encabezado()
    ]

    mejor_fila = 0
    mejor_puntaje = 0

    for indice, fila in df_raw.iterrows():
        texto_fila = " ".join(
            fila.fillna("")
            .astype(str)
            .str.lower()
        )

        puntaje = sum(
            palabra in texto_fila
            for palabra in palabras_clave
        )

        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_fila = indice

    return mejor_fila


def calcular_expiry_date():
    hoy = datetime.now().date()

    fecha_objetivo = hoy + timedelta(days=14)

    ultimo_dia = monthrange(
        hoy.year,
        hoy.month
    )[1]

    fin_de_mes = hoy.replace(
        day=ultimo_dia
    )

    if fecha_objetivo > fin_de_mes:
        return fin_de_mes

    return fecha_objetivo


def convertir_expiry_date(fecha):
    return datetime.combine(fecha, time(hour=12))


def formatear_expiry_date(fecha):
    return convertir_expiry_date(fecha).strftime("%d-%m-%Y  %H:%M")


def limpiar_numero(valor):
    if pd.isna(valor):
        return None
    if not isinstance(valor, str):
        return valor

    texto = valor.strip()
    negativo = texto.startswith("(") and texto.endswith(")")
    texto = texto.replace("(", "").replace(")", "")
    texto = (
        texto.replace("$", "")
        .replace("USD", "")
        .replace("usd", "")
        .replace("US$", "")
        .replace("+", "")
        .replace(" ", "")
    )
    texto = "".join(c for c in texto if c.isdigit() or c in ",.-")
    entero_con_sufijo = texto.endswith(".-") or texto.endswith(",-")
    if entero_con_sufijo:
        texto = texto[:-2]
        texto = texto.replace(".", "").replace(",", "")

    if not entero_con_sufijo and "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif not entero_con_sufijo and "," in texto:
        decimales = len(texto.rsplit(",", 1)[1])
        texto = texto.replace(",", "" if decimales == 3 else ".")

    if negativo:
        texto = "-" + texto
    return pd.to_numeric(texto, errors="coerce")


def procesar_intcomex(df, expiry_date):
    df = df.copy()
    df.columns = [str(columna).strip().lower() for columna in df.columns]
    resultado = pd.DataFrame()

    # Mapeo Intcomex
    resultado["provider_code"] = df["sku"]

    resultado["currency_unaware_cost_neto"] = (
        df["venta neto usd"]
    )

    resultado["currency"] = "USD"

    resultado["expiry_date"] = (
        formatear_expiry_date(expiry_date)
    )

    resultado["quantity"] = (
        df["stock actual"]
    )

    # Columnas adicionales requeridas por la estructura CRM
    resultado["mpn"] = ""
    resultado["brand"] = ""
    resultado["name"] = ""
    resultado["condition"] = 0
    resultado["working_days_to_deliver"] = ""

    # Limpiar provider_code
    resultado["provider_code"] = (
        resultado["provider_code"]
        .astype(str)
        .str.strip()
    )

    # Limpiar stock
    resultado["quantity"] = resultado["quantity"].map(limpiar_numero)

    # Limpiar precio
    resultado["currency_unaware_cost_neto"] = (
        resultado["currency_unaware_cost_neto"].map(limpiar_numero)
    )

    # Eliminar stock inválido
    resultado = resultado[
        resultado["quantity"] > 0
    ]

    # Eliminar códigos inválidos
    resultado = resultado[
        resultado["provider_code"].notna()
        & (resultado["provider_code"] != "")
        & (resultado["provider_code"] != "nan")
    ]

    # Eliminar precios inválidos
    resultado = resultado[
        resultado["currency_unaware_cost_neto"].notna()
        & (
            resultado["currency_unaware_cost_neto"] > 0
        )
    ]

    # Orden exacto de columnas CRM
    columnas_crm = [
        "provider_code",
        "currency_unaware_cost_neto",
        "currency",
        "expiry_date",
        "quantity",
        "mpn",
        "brand",
        "name",
        "condition",
        "working_days_to_deliver"
    ]

    resultado = resultado[
        columnas_crm
    ]

    return resultado


def generar_excel(df):
    buffer = BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Lista"
        )

        hoja = writer.book["Lista"]

        # Columna D = expiry_date: texto con prefijo de apóstrofe de Excel.
        for celda in hoja["D"][1:]:
            celda.number_format = "@"
            celda.quotePrefix = True
        hoja.column_dimensions["D"].width = 23

    buffer.seek(0)

    return buffer


def formatear_datos_copia(df):
    """Formatea solo las filas de datos para el portapapeles de Excel."""
    datos = df.copy()
    columnas_numericas = {
        'currency_unaware_cost_neto', 'quantity', 'condition',
        'working_days_to_deliver'
    }

    def formatear(columna, valor):
        if pd.isna(valor):
            return ''
        if columna == 'expiry_date':
            if isinstance(valor, datetime):
                fecha = valor
            else:
                texto_fecha = re.sub(r'\s+', ' ', str(valor).strip().lstrip("'"))
                fecha = None
                for formato in (
                    '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M',
                    '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
                    '%d-%m-%Y', '%Y-%m-%d',
                ):
                    try:
                        fecha = datetime.strptime(texto_fecha, formato)
                        break
                    except ValueError:
                        continue
            if fecha is not None:
                return fecha.strftime('%d-%m-%Y  %H:%M')
            return str(valor).strip().lstrip("'")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if float(valor).is_integer():
                return str(int(valor))
        texto = str(valor).strip()
        if columna in columnas_numericas and re.fullmatch(r'[+-]?\d+\.0+', texto):
            return texto.split('.', 1)[0]
        if (
            columna == 'currency_unaware_cost_neto'
            and re.fullmatch(r'[+-]?\d+\.\d+', texto)
        ):
            # El Excel del usuario usa coma decimal. Un punto seguido por muchos
            # dígitos se interpreta al pegar como separador de miles.
            return texto.replace('.', ',')
        return texto

    for columna in datos.columns:
        datos[columna] = datos[columna].map(
            lambda valor: formatear(columna, valor)
        )

    return datos


def generar_tsv(df):
    """Genera texto tabulado sin encabezados y sin apóstrofe visible."""
    datos = formatear_datos_copia(df)

    return datos.to_csv(
        sep="\t",
        index=False,
        header=False,
        lineterminator="\n",
        na_rep="",
    )


def generar_html_copia_excel(df):
    """Copia fechas con el prefijo de texto interno de Excel."""
    datos = formatear_datos_copia(df)
    filas = []
    for valores in datos.itertuples(index=False, name=None):
        celdas = []
        for columna, valor in zip(datos.columns, valores):
            contenido = escape(str(valor))
            if columna == 'expiry_date':
                # x:str pasa el apóstrofe como prefijo de Excel, no como texto
                # visible. El contenido de la celda conserva solo la fecha.
                valor_excel = escape("'" + str(valor), quote=True) if valor else ''
                celdas.append(
                    f'<td x:str="{valor_excel}"><pre style="margin:0; font-family:inherit">{contenido}</pre></td>'
                )
            else:
                celdas.append(f'<td>{contenido}</td>')
        filas.append('<tr>' + ''.join(celdas) + '</tr>')
    return '<html xmlns:x="urn:schemas-microsoft-com:office:excel"><head><meta charset="utf-8"></head><body><table xmlns:x="urn:schemas-microsoft-com:office:excel"><tbody>' + ''.join(filas) + '</tbody></table></body></html>'

def boton_copiar_excel(df):
    html = json.dumps(generar_html_copia_excel(df), ensure_ascii=False).replace("</", "<\\/")
    components.html(
        f"""
        <button id="copiar-excel" type="button" style="
            width:100%; min-height:42px; padding:0.4rem 0.75rem;
            border:1px solid rgba(250,250,250,.2); border-radius:.5rem;
            background:#262730; color:#fafafa; font:inherit; cursor:pointer;
        ">Copiar para Excel</button>
        <script>
            const html = {html};
            const boton = document.getElementById('copiar-excel');
            function copiarHtmlAlternativo() {{
                const bloque = document.createElement('div');
                bloque.innerHTML = html;
                bloque.contentEditable = 'true';
                bloque.style.position = 'fixed';
                bloque.style.left = '-10000px';
                document.body.appendChild(bloque);
                const rango = document.createRange();
                rango.selectNodeContents(bloque);
                const seleccion = window.getSelection();
                seleccion.removeAllRanges();
                seleccion.addRange(rango);
                const copiado = document.execCommand('copy');
                seleccion.removeAllRanges();
                bloque.remove();
                return copiado;
            }}
            boton.addEventListener('click', async () => {{
                try {{
                    if (navigator.clipboard.write && window.ClipboardItem) {{
                        const contenido = new ClipboardItem({{
                            'text/html': new Blob([html], {{ type: 'text/html' }})
                        }});
                        await navigator.clipboard.write([contenido]);
                    }} else {{
                        if (!copiarHtmlAlternativo()) throw new Error('HTML clipboard unavailable');
                    }}
                }} catch (error) {{
                    try {{
                        if (!copiarHtmlAlternativo()) throw new Error('HTML clipboard unavailable');
                    }} catch (errorAlternativo) {{
                        boton.textContent = 'Error: descarga el Excel';
                        setTimeout(() => boton.textContent = 'Copiar para Excel', 3500);
                        return;
                    }}
                }}
                boton.textContent = '¡Copiado!';
                setTimeout(() => boton.textContent = 'Copiar para Excel', 2000);
            }});
        </script>
        """,
        height=50,
    )

def normalizar_columna(valor):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD', str(valor)) if not unicodedata.combining(c)).strip().upper()


def normalizar_texto_columna(valor):
    return ' '.join(normalizar_columna(valor).split())


def obtener_nombres_hojas(archivo):
    archivo.seek(0)
    nombres = pd.ExcelFile(archivo).sheet_names
    archivo.seek(0)
    return nombres


def procesar_kepler(df, fecha, nombre, moneda_valor):
    df = df.copy()
    df.columns = [normalizar_columna(c) for c in df.columns]
    if 'PREVENTA' in normalizar_columna(nombre):
        raise ValueError('Preventa: se excluye del stock inmediato. Procesar por separado.')
    def buscar(opciones):
        return next((c for c in opciones if c in df.columns), None)
    codigo = buscar(['SKU', 'SKU/LINK', 'CODIGO'])
    precio = buscar(['DOLAR', 'VALOR USD', 'U$ NETO', 'VALOR'])
    stock = buscar(['STOCK', 'QTY'])
    # Plantillas revisadas: Vertagear C y D-Link B contienen cantidades sin encabezado.
    if stock is None and {'FAMILIA/LINK', 'SKU', 'U$ NETO'}.issubset(df.columns) and len(df.columns) > 2:
        stock = df.columns[2] if df.columns[2].startswith('UNNAMED:') else None
    if stock is None and {'FAMILIA', 'SKU/LINK', 'U$ NETO'}.issubset(df.columns) and len(df.columns) > 1:
        stock = df.columns[1] if df.columns[1].startswith('UNNAMED:') else None
    if not all([codigo, precio, stock]):
        raise ValueError('Formato Kepler no reconocido: se requieren código, precio y stock.')
    if precio == 'VALOR' and moneda_valor == 'Sin confirmar':
        raise ValueError('Confirma la moneda de la columna VALOR (Threadripper) en el selector antes de procesar.')
    def numero(v):
        return limpiar_numero(v)
    fuente = pd.DataFrame({'SKU': df[codigo], 'venta neto usd': df[precio].map(numero),
                           'stock actual': df[stock].map(numero)}, index=df.index)
    if 'LLEGADA' in df.columns:
        fuente = fuente.loc[df['LLEGADA'].astype(str).map(normalizar_columna).eq('EN STOCK')]
    resultado = procesar_intcomex(fuente, fecha)
    resultado['currency'] = moneda_valor if precio == 'VALOR' else 'USD'
    # Copiar solo PN, nombre y marca que Kepler entrega explícitamente.
    # No deducir esos datos desde SKU ni desde otros campos.
    columnas_producto = {
        normalizar_texto_columna(columna): columna for columna in df.columns
    }
    campos_kepler = {
        'mpn': ('PN', 'P/N', 'MPN', 'PART NUMBER', 'PART NUMBER (MPN)',
                'NUMERO DE PARTE', 'CODIGO FABRICANTE'),
        'name': ('NOMBRE', 'NAME', 'DESCRIPTION', 'DESCRIPCION',
                 'PRODUCT NAME', 'PRODUCTO', 'MODELO'),
        'brand': ('MARCA', 'BRAND', 'MANUFACTURER', 'FABRICANTE'),
    }
    for destino, alias in campos_kepler.items():
        columna = next(
            (columnas_producto[normalizar_texto_columna(opcion)]
             for opcion in alias
             if normalizar_texto_columna(opcion) in columnas_producto),
            None,
        )
        if columna:
            valores = df.loc[resultado.index, columna].fillna('').astype(str).str.strip()
            resultado[destino] = valores.replace({'nan': '', 'None': ''})
    return resultado


def leer_hoja_xlsx_con_datos(archivo, nombre_hoja=None):
    """Limita la lectura a celdas con datos, no al formato de filas vacías."""
    import posixpath
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    import openpyxl
    from openpyxl.utils.cell import coordinate_from_string, column_index_from_string

    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    archivo.seek(0)
    with ZipFile(archivo) as paquete:
        libro = ET.fromstring(paquete.read('xl/workbook.xml'))
        hojas = libro.findall('s:sheets/s:sheet', ns)
        primera = hojas[0] if nombre_hoja is None else next(
            (hoja for hoja in hojas if hoja.attrib['name'] == nombre_hoja), None)
        if primera is None:
            raise ValueError(f'No se encontró la hoja {nombre_hoja}.')
        nombre_hoja = primera.attrib['name']
        relacion = primera.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        relaciones = ET.fromstring(paquete.read('xl/_rels/workbook.xml.rels'))
        destino = next(r.attrib['Target'] for r in relaciones if r.attrib['Id'] == relacion)
        ruta = destino.lstrip('/') if destino.startswith('/') else posixpath.normpath(posixpath.join('xl', destino))
        ultima_fila, ultima_columna = 0, 0
        with paquete.open(ruta) as contenido:
            for _, elemento in ET.iterparse(contenido, events=('end',)):
                if elemento.tag == '{' + ns['s'] + '}c':
                    if any(elemento.find('s:' + tipo, ns) is not None for tipo in ('v', 'is', 'f')):
                        columna, fila = coordinate_from_string(elemento.attrib['r'])
                        ultima_fila = max(ultima_fila, fila)
                        ultima_columna = max(ultima_columna, column_index_from_string(columna))
                    elemento.clear()
                elif elemento.tag == '{' + ns['s'] + '}row':
                    elemento.clear()
    if not ultima_fila:
        archivo.seek(0)
        return pd.DataFrame()
    archivo.seek(0)
    libro = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
    try:
        bruto = pd.DataFrame(libro[nombre_hoja].iter_rows(
            max_row=ultima_fila, max_col=ultima_columna, values_only=True), dtype=object)
    finally:
        libro.close()
        archivo.seek(0)
    return bruto


def leer_intcomex_xlsx(archivo):
    bruto = leer_hoja_xlsx_con_datos(archivo)
    if bruto.empty:
        raise ValueError('La primera hoja de Intcomex no contiene datos.')
    columnas_asus = {'SKU INTCOMEX', 'NUMERO DE PARTE', 'PRECIO USD (S/IVA)',
                     'STOCK REFERENCIAL', 'DETALLE'}
    candidatos = [i for i, fila in bruto.iterrows()
                  if columnas_asus.issubset({normalizar_texto_columna(v) for v in fila})]
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
    resultado = procesar_intcomex(base, expiry_date)
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
    resultado = procesar_intcomex(base, expiry_date)
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


def leer_solutionbox(archivo, fecha, moneda, hojas_seleccionadas=None):
    """Lee las tablas de SolutionBox sin convertir plazos de entrega en stock."""
    if not archivo.name.lower().endswith(('.xlsx', '.xls')):
        raise ValueError('SolutionBox: carga una lista Excel (.xlsx o .xls).')
    if hojas_seleccionadas == []:
        raise ValueError('SolutionBox: selecciona al menos una hoja.')
    archivo.seek(0)
    hojas = pd.read_excel(archivo, sheet_name=hojas_seleccionadas, header=None, dtype=object)
    salida, usadas, omitidas = [], [], []
    leidos = 0

    def texto(valor):
        if pd.isna(valor):
            return ''
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if float(valor).is_integer():
                return str(int(valor))
        return str(valor).strip()

    def cantidad(valor):
        # Solo cantidades explícitas. "POR ENCARGO 90 DÍAS" no equivale a 90.
        if isinstance(valor, str) and not re.fullmatch(r'\+?\d+(?:[.,]\d+)?\+?', valor.strip()):
            return float('nan')
        return limpiar_numero(valor)

    for hoja, bruto in hojas.items():
        encabezados = []
        for indice, fila in bruto.iterrows():
            columnas = {normalizar_texto_columna(v): i for i, v in enumerate(fila)}
            def buscar(*opciones):
                return next((columnas[c] for c in opciones if c in columnas), None)
            pn = buscar('PN', 'PART NUMBER', 'P/N')
            codigo = pn if pn is not None else buscar('PRODUCT')
            precio = buscar('PRECIO LISTA', 'VALOR', 'PRECIO UNITARIO US$NETO',
                            'PRECIO UNITARIO US$', 'PRECIO USD (NETO)')
            stock = buscar('STOCK', 'STOCK DISPONIBLE', 'CANTIDAD', 'DISPONIBILIDAD')
            nombre = buscar('DESCRIPCION AMPLIADA', 'DESCRIPCION', 'COMMENT', 'MODELO')
            if all(c is not None for c in (codigo, precio, stock, nombre)):
                encabezados.append((indice, codigo, pn, precio, stock, nombre,
                                    buscar('MARCA'), buscar('ESTADO')))
        if not encabezados:
            omitidas.append(hoja)
            continue
        validos_hoja = 0
        for posicion, (inicio, codigo, pn, precio, stock, nombre, marca, estado) in enumerate(encabezados):
            fin = encabezados[posicion + 1][0] if posicion + 1 < len(encabezados) else len(bruto)
            datos = bruto.iloc[inicio + 1:fin].dropna(how='all')
            datos = datos.loc[datos.iloc[:, codigo].notna() &
                              (datos.iloc[:, precio].notna() | datos.iloc[:, stock].notna())]
            leidos += len(datos)
            titulo_precio = normalizar_texto_columna(bruto.iloc[inicio, precio])
            divisa = 'USD' if 'USD' in titulo_precio or 'US$' in titulo_precio else moneda
            if divisa not in ('USD', 'CLP'):
                raise ValueError(f'SolutionBox: confirma la moneda de {titulo_precio} (hoja {hoja}).')
            cantidades = datos.iloc[:, stock].map(cantidad)
            if estado is not None:
                disponible = datos.iloc[:, estado].fillna('').map(normalizar_texto_columna)
                cantidades = cantidades.where(disponible.isin(['', 'STOCK', 'EN STOCK', 'DISPONIBLE']))
            base = pd.DataFrame({'SKU': datos.iloc[:, codigo].map(texto),
                                 'venta neto usd': datos.iloc[:, precio].map(limpiar_numero),
                                 'stock actual': cantidades}, index=datos.index)
            resultado = procesar_intcomex(base, fecha)
            resultado['currency'] = divisa
            for destino, columna in [('mpn', pn), ('name', nombre), ('brand', marca)]:
                if columna is not None:
                    resultado[destino] = datos.loc[resultado.index].iloc[:, columna].map(texto)
            validos_hoja += len(resultado)
            salida.append(resultado)
        usadas.append(f'{hoja} ({validos_hoja} productos)')
    if not salida:
        raise ValueError('SolutionBox: no se encontraron tablas con identificador, precio y stock.')
    detalle = 'Hojas procesadas: ' + ', '.join(usadas)
    if omitidas:
        detalle += '. Hojas sin tabla de precios: ' + ', '.join(omitidas)
    detalle += '. Se excluyen productos sin stock numérico positivo o con precio inválido.'
    return pd.concat(salida, ignore_index=True), leidos, detalle



def leer_nuevo_proveedor(archivo, proveedor, fecha, moneda, permitir_pn, hojas_seleccionadas=None):
    if proveedor == 'SolutionBox':
        return leer_solutionbox(archivo, fecha, moneda, hojas_seleccionadas)
    # Solo se admiten encabezados observados; tránsito y ofertas no sustituyen stock/precio normal.
    codigos = {'Tecnoglobal': ['CODIGO TG', 'CODIGO', 'CODIGO SISTEMA', 'SKU'],
               'Ingram': ['MATERIAL/SKU', 'INGRAM MICRO SKU', 'IM SKU', 'MATERIAL', 'SKU INGRAM'],
               'Coimco': ['CODIGO', 'CODIGO SISTEMA', 'SKU'],
               'Fujicorp': ['CODIGO', 'SKU'],
               'Nexsys': ['SKU', 'CODIGO'],
               'Intcomex': ['SKU', 'MATERIAL/SKU', 'MATERIAL', 'CODIGO'],
               'Kepler': ['SKU', 'SKU/LINK', 'CODIGO'],
               'Demco Ltda.': ['CODIGO INTERNO']}[proveedor]
    precios = ['PV OFERTA C/U', 'PRECIO UNITARIO US$', 'PRECIO USD (S/IVA)', 'PRECIOS USD', 'PRECIO USD$',
               'VALOR USD + IVA', 'PRECIO ESPECIAL NETO UNIT. CENTRALE', 'VENTA NETO USD',
               'PRECIO US$', 'VALOR USD', 'PRECIO', 'MAYORISTA', 'DISTRIBUIDOR', 'VALOR $',
               'VALOR', 'NETO']
    if proveedor == 'Ingram':
        precios = ['COSTO', *precios]
    if proveedor == 'Demco Ltda.':
        precios = ['PRECIO NETO']
    stocks = ['STOCK SIN RESERVA', 'CANTIDAD', 'STOCK DISPONIBLE', 'STOCK REFERENCIAL', 'STOCK']
    def norm(v):
        return normalizar_texto_columna(v)
    def numero(v):
        if not isinstance(v, str):
            return v
        v = v.strip()
        if '$' in v:
            v = v.rsplit('$', 1)[1]
        elif any(letra.isalpha() for letra in v):
            cantidades = re.findall(r'-?\d[\d.,]*', v)
            v = cantidades[-1] if cantidades else ''
        v = v.replace('$', '').replace('USD', '').replace('+', '')
        v = ''.join(v.split())
        if v.endswith('.-'):
            v = v[:-2]
        if ',' in v:
            v = v.replace('.', '').replace(',', '.')
        elif re.fullmatch(r'\d{1,3}(?:\.\d{3})+', v):
            v = v.replace('.', '')
        return pd.to_numeric(v, errors='coerce')
    archivo.seek(0)
    es_pdf = archivo.name.lower().endswith('.pdf')
    if es_pdf:
        import pdfplumber

        hojas = {}
        tiene_texto = False
        with pdfplumber.open(archivo) as documento:
            for numero_pagina, pagina in enumerate(documento.pages, 1):
                tiene_texto = tiene_texto or bool(pagina.extract_text())
                tablas = pagina.extract_tables()
                if not tablas:
                    tablas = pagina.extract_tables(table_settings={
                        'vertical_strategy': 'text',
                        'horizontal_strategy': 'text',
                        'min_words_vertical': 1,
                        'min_words_horizontal': 1,
                    })
                for numero_tabla, tabla in enumerate(tablas, 1):
                    if not tabla:
                        continue
                    ancho = max(len(fila) for fila in tabla)
                    filas = [
                        list(fila) + [None] * (ancho - len(fila))
                        for fila in tabla
                    ]
                    hojas[f'Página {numero_pagina}, tabla {numero_tabla}'] = pd.DataFrame(filas)
        if not hojas:
            if not tiene_texto:
                raise ValueError(
                    'El PDF parece escaneado o no contiene texto seleccionable. '
                    'Este formato requiere OCR antes de procesarlo.'
                )
            raise ValueError(
                'No se detectaron tablas en el PDF. Verifica que el documento '
                'contenga una tabla de texto y no una imagen.'
            )
    elif archivo.name.lower().endswith('.csv'):
        hojas = {'CSV': pd.read_csv(archivo, header=None)}
    elif proveedor == 'Ingram' and archivo.name.lower().endswith('.xlsx'):
        if hojas_seleccionadas == []:
            raise ValueError('Selecciona al menos una hoja de Ingram para procesar.')
        nombres = hojas_seleccionadas if hojas_seleccionadas is not None else obtener_nombres_hojas(archivo)
        hojas = {nombre: leer_hoja_xlsx_con_datos(archivo, nombre) for nombre in nombres}
    else:
        hojas = pd.read_excel(
            archivo, sheet_name=hojas_seleccionadas or None, header=None
        )
        if isinstance(hojas, pd.DataFrame):
            nombre_hoja = hojas_seleccionadas[0] if hojas_seleccionadas else 'Hoja 1'
            hojas = {nombre_hoja: hojas}
    preferir_oferta = proveedor == 'Fujicorp'
    salida, omitidas, usadas = [], [], []
    leidos = 0
    for hoja, bruto in hojas.items():
        candidatos = []
        for i, row in bruto.iterrows():
            cols = list(row.map(norm))
            opciones_pn = ['NUMERO DE PARTE', 'PART_NUMBER', 'PART NUMBER', 'PARTNUMBER', 'P/N']
            if proveedor == 'Ingram':
                opciones_pn.append('PN')
            pn = next((c for c in opciones_pn if c in cols), None)
            cod = next((c for c in codigos if c in cols), None)
            if not cod and proveedor == 'Nexsys':
                cod = pn
            stk = next((c for c in stocks if c in cols), None)
            ofertas = [c for c in ['OFERTA', 'OFERTA X VOLUMEN', 'PRECIO OFERTA'] if c in cols]
            precio_neto = next((c for c in precios if c in cols), None)
            descripcion = next((c for c in cols if c in ['DESCRIPTION', 'MKT NAME', 'MODELO']
                                or c.startswith('DESCRIPCI')), None)
            if proveedor == 'Demco Ltda.':
                descripcion = 'NOMBRE' if 'NOMBRE' in cols else None
            if cod and precio_neto and stk and (descripcion or proveedor == 'Ingram'):
                candidatos.append((i, cols, cod, precio_neto, stk, pn, ofertas, descripcion))
        if not candidatos:
            omitidas.append(hoja)
            continue
        usadas.append(hoja)
        for posicion, (inicio, cols, cod, pre, stk, pn, ofertas, descripcion) in enumerate(candidatos):
            if proveedor == 'Nexsys' and cod == pn and not permitir_pn:
                raise ValueError('Nexsys: confirma que el CRM acepta el número de parte como provider_code.')
            divisa = ('CLP' if proveedor in ['Coimco', 'Fujicorp'] else
                      'USD' if proveedor == 'Intcomex' or 'USD' in pre or 'US$' in pre else moneda)
            if divisa == 'Sin confirmar':
                raise ValueError('Confirma la moneda de la columna PRECIO antes de procesar este archivo.')
            fin = candidatos[posicion+1][0] if posicion+1 < len(candidatos) else len(bruto)
            datos = bruto.iloc[inicio+1:fin].copy()
            datos = datos.dropna(how='all')
            leidos += len(datos)
            precio_base = datos.iloc[:,cols.index(pre)].map(numero)
            if preferir_oferta and ofertas:
                precios_opcion = [precio_base]
                for columna_oferta in ofertas:
                    precios_opcion.append(
                        datos.iloc[:,cols.index(columna_oferta)].map(numero)
                    )
                matriz_precios = pd.concat(precios_opcion, axis=1)
                precio_base = matriz_precios.where(matriz_precios > 0).min(axis=1)
            cantidades = datos.iloc[:,cols.index(stk)].map(numero)
            if proveedor == 'Demco Ltda.':
                # No interpretar plazos o comentarios como cantidades.
                cantidades = pd.to_numeric(datos.iloc[:,cols.index(stk)], errors='coerce')
            base = pd.DataFrame({'SKU': datos.iloc[:,cols.index(cod)],
                'venta neto usd': precio_base,
                'stock actual': cantidades})
            result = procesar_intcomex(base, fecha)
            result['currency'] = divisa
            # La marca solo se toma de una columna explícita del archivo.
            # El nombre de la hoja no es un dato de producto y no debe inferirse.
            if 'MARCA' in cols:
                result['brand'] = datos.loc[result.index].iloc[:,cols.index('MARCA')].fillna('').astype(str).str.strip()
            if pn:
                result['mpn'] = datos.loc[result.index].iloc[:,cols.index(pn)].fillna('').astype(str).str.strip()
            if descripcion:
                result['name'] = datos.loc[result.index].iloc[:,cols.index(descripcion)].fillna('').astype(str).str.strip()
            salida.append(result)
    if not salida:
        raise ValueError('No se encontraron hojas con código, stock y precio compatibles.')
    detalle = ('Tablas PDF procesadas: ' if es_pdf else 'Hojas procesadas: ') + ', '.join(usadas)
    if omitidas:
        detalle += '. Hojas sin tabla compatible: ' + ', '.join(omitidas)
    return pd.concat(salida, ignore_index=True), leidos, detalle


def detectar_proveedores_archivo(nombre):
    # Comparar palabras completas; fechas y separadores pueden rodear el nombre.
    nombre = normalizar_columna(str(nombre).replace('\\', '/').rsplit('/', 1)[-1].rsplit('.', 1)[0])
    patrones = {
        'Intcomex': r'INTCOMEX', 'Ingram': r'INGRAM', 'Kepler': r'KEPLER',
        'Tecnoglobal': r'TECNO[\W_]*GLOBAL', 'Coimco': r'COIMCO',
        'Fujicorp': r'FUJICORP', 'Nexsys': r'NEXSYS',
        'SolutionBox': r'SOLUTION[\W_]*BOX', 'Demco Ltda.': r'DEMCO',
        'Facciatech': r'FACCIATECH', 'Gtc ribbon': r'GTC[\W_]*RIBBON',
    }
    return [proveedor for proveedor, patron in patrones.items()
            if re.search(r'(?<![A-Z])' + patron + r'(?![A-Z])', nombre)]


def detectar_proveedor_lote(nombres):
    coincidencias = [detectar_proveedores_archivo(nombre) for nombre in nombres]
    proveedores = {p for lista in coincidencias for p in lista}
    if any(len(lista) > 1 for lista in coincidencias) or len(proveedores) > 1:
        return 'Seleccionar...', 'conflicto'
    if coincidencias and all(len(lista) == 1 for lista in coincidencias):
        return next(iter(proveedores)), 'detectado'
    return 'Seleccionar...', 'sin_coincidencia'


def moneda_predeterminada(proveedor):
    return 'CLP' if proveedor in {'Fujicorp', 'Coimco', 'Demco Ltda.', 'Facciatech'} else 'USD'


def procesar_archivos(archivos, fecha, proveedor="Intcomex", moneda_valor=None, permitir_pn=False, hojas_por_archivo=None):
    moneda_valor = moneda_valor or moneda_predeterminada(proveedor)
    if moneda_valor not in ('USD', 'CLP'):
        raise ValueError('Selecciona USD o CLP como moneda de la lista.')
    resumen, resultados = [], []
    for numero, archivo in enumerate(archivos, 1):
        nombre = f"{numero}. {archivo.name}"
        fila = {"Archivo": nombre, "Leídos": 0, "Válidos": 0,
                "Descartados": 0, "Estado": "", "Detalle": ""}
        try:
            if (proveedor in ['Tecnoglobal', 'Nexsys', 'Ingram', 'Coimco', 'Fujicorp', 'SolutionBox', 'Demco Ltda.']
                    or archivo.name.lower().endswith('.pdf')):
                resultado, leidos, detalle = leer_nuevo_proveedor(
                    archivo, proveedor, fecha, moneda_valor, permitir_pn,
                    hojas_seleccionadas=(hojas_por_archivo or {}).get(numero - 1),
                )
                resultado['currency'] = moneda_valor
                fila.update({'Leídos': leidos, 'Válidos': len(resultado), 'Descartados': leidos-len(resultado), 'Estado': 'Procesado', 'Detalle': detalle})
                resultado['Archivo de origen'] = nombre
                resultados.append(resultado)
                resumen.append(fila)
                continue
            archivo.seek(0)
            if archivo.name.lower().endswith('.csv'):
                encabezado, separador, encoding = detectar_csv(archivo)
                archivo.seek(0)
                df = pd.read_csv(
                    archivo,
                    header=encabezado,
                    sep=separador,
                    encoding=encoding
                )
            else:
                if proveedor == 'Intcomex' and archivo.name.lower().endswith('.xlsx'):
                    df = leer_intcomex_xlsx(archivo)
                elif proveedor == 'Kepler':
                    bruto = pd.read_excel(archivo, header=None)
                    candidatos = [i for i, row in bruto.iterrows() if set(row.map(normalizar_columna)) & {'SKU', 'SKU/LINK', 'CODIGO'} and set(row.map(normalizar_columna)) & {'DOLAR', 'VALOR USD', 'U$ NETO', 'VALOR'}]
                    if not candidatos:
                        raise ValueError('No se encontró un encabezado Kepler compatible.')
                    encabezado = candidatos[0]
                else:
                    encabezado = detectar_encabezado(archivo)
                if not (proveedor == 'Intcomex' and archivo.name.lower().endswith('.xlsx')):
                    archivo.seek(0)
                    df = pd.read_excel(archivo, header=encabezado)
            fila['Leídos'] = len(df)
            if proveedor == 'Kepler':
                resultado = procesar_kepler(df, fecha, archivo.name, moneda_valor)
            elif (proveedor == 'Intcomex' and
                  {'SKU INTCOMEX', 'NUMERO DE PARTE', 'PRECIO USD (S/IVA)',
                   'STOCK REFERENCIAL', 'DETALLE'}.issubset(
                       {normalizar_texto_columna(c) for c in df.columns})):
                resultado = procesar_intcomex_asus(df, fecha)
            elif (
                proveedor == 'Intcomex'
                and {'PART NUMBER (MPN)', 'PRECIO ESPECIAL NETO UNIT. CENTRALE'}
                .issubset({normalizar_texto_columna(columna) for columna in df.columns})
            ):
                resultado = procesar_intcomex_wd(df, fecha)
            else:
                resultado = procesar_intcomex(df, fecha)
            # La elección del usuario prevalece sobre los encabezados del archivo.
            # Solo asigna la moneda; no modifica ni convierte los precios.
            resultado['currency'] = moneda_valor
            fila['Válidos'] = len(resultado)
            fila['Descartados'] = len(df) - len(resultado)
            fila['Estado'] = 'Procesado'
            fila['Detalle'] = 'Se excluyen códigos vacíos, precios inválidos y stock no positivo.'
            resultado = resultado.copy()
            resultado['Archivo de origen'] = nombre
            resultados.append(resultado)
        except Exception as error:
            fila['Estado'] = 'Error'
            fila['Detalle'] = str(error)
        resumen.append(fila)
    combinado = pd.concat(resultados, ignore_index=True) if resultados else pd.DataFrame()
    return pd.DataFrame(resumen), combinado


def consolidar(combinado):
    if combinado.empty:
        return combinado.copy(), combinado.copy(), 0
    columnas = [c for c in combinado.columns if c != 'Archivo de origen']
    unicos = combinado.drop_duplicates(subset=columnas).copy()
    repetidos = len(combinado) - len(unicos)
    conflicto = unicos['provider_code'].duplicated(keep=False)
    return unicos.loc[~conflicto].copy(), unicos.loc[conflicto].copy(), repetidos


def preparar_vista(df):
    vista = df.copy()
    if (
        "expiry_date" in vista.columns
        and pd.api.types.is_datetime64_any_dtype(vista["expiry_date"])
    ):
        vista["expiry_date"] = pd.to_datetime(
            vista["expiry_date"], errors="coerce"
        ).dt.strftime("%d-%m-%Y  %H:%M")
    return vista


PROVEEDORES_SIN_REGLAS = ['Facciatech', 'Gtc ribbon', 'Otro']
PROVEEDORES_CONFIGURADOS = ['Intcomex', 'Kepler', 'Tecnoglobal', 'Nexsys', 'Ingram', 'Coimco', 'Fujicorp', 'SolutionBox', 'Demco Ltda.']

st.title('Price List Normalizer')
st.write('Generador de listas de precios para carga al CRM')
archivos = st.file_uploader('Subir listas de precios del mismo proveedor',
                           type=['xlsx', 'xls', 'csv', 'pdf'], accept_multiple_files=True)
import_hash_archivos = tuple(hashlib.sha256(a.getvalue()).hexdigest() for a in archivos)
firma_deteccion = tuple((a.name, huella) for a, huella in zip(archivos, import_hash_archivos))
proveedor_detectado, estado_deteccion = detectar_proveedor_lote([a.name for a in archivos])
if st.session_state.get('archivos_deteccion') != firma_deteccion:
    st.session_state['archivos_deteccion'] = firma_deteccion
    st.session_state['proveedor_lista'] = proveedor_detectado
    st.session_state['confirmar_proveedor_archivos'] = False
    if estado_deteccion == 'detectado':
        st.session_state[f'moneda_lista_{proveedor_detectado}'] = moneda_predeterminada(proveedor_detectado)
proveedor = st.selectbox(
    'Proveedor',
    ['Seleccionar...', 'Ingram', 'Intcomex', 'Tecnoglobal', 'Coimco', 'Fujicorp', 'Kepler', 'Nexsys', 'SolutionBox', 'Demco Ltda.', *PROVEEDORES_SIN_REGLAS],
    key='proveedor_lista',
    on_change=lambda: st.session_state.update(confirmar_proveedor_archivos=False),
)
proveedor_confirmado = True
if archivos:
    if estado_deteccion == 'detectado':
        if proveedor == proveedor_detectado:
            st.caption(f'Mayorista detectado por el nombre del archivo: {proveedor_detectado}. Puedes corregirlo en el selector.')
        else:
            st.caption(f'Nombre del archivo: {proveedor_detectado}. Se usará tu selección manual: {proveedor}.')
    elif estado_deteccion == 'conflicto':
        st.warning('Los nombres contienen varios mayoristas o corresponden a proveedores distintos. Retira los archivos de otro proveedor o corrige y confirma la selección.')
        proveedor_confirmado = st.checkbox(
            'Confirmo que todos los archivos pertenecen al proveedor seleccionado',
            key='confirmar_proveedor_archivos',
        )
    else:
        st.info('No se pudo identificar un mismo mayorista en todos los nombres. Selecciona el proveedor manualmente.')
if proveedor in PROVEEDORES_SIN_REGLAS:
    st.info(
        f'{proveedor}: esta opción ya está disponible, pero todavía no tiene reglas '
        'de lectura configuradas. Para evitar inventar o asignar mal datos, necesitamos '
        'revisar una lista de ejemplo antes de habilitar su procesamiento.'
    )
st.caption('Puedes seleccionar varios archivos. PDF: se recorren todas las páginas y se extraen tablas con texto seleccionable; los PDF escaneados requieren OCR. Tecnoglobal, Nexsys, Ingram, Coimco y Fujicorp: se revisan las hojas elegidas. Intcomex y Kepler: primera hoja. '
           'La consolidación CRM está disponible para los proveedores con reglas configuradas.')


hojas_por_archivo = {}
seleccion_hojas_incompleta = False
if proveedor == 'Ingram' and archivos:
    st.subheader('Hojas del Excel')
    st.caption('Elige una o varias hojas de cada archivo. No hay nombres ni hojas obligatorias; solo se procesarán las que selecciones.')
    for indice_archivo, archivo in enumerate(archivos):
        if not archivo.name.lower().endswith(('.xlsx', '.xls')):
            continue
        try:
            nombres_hojas = obtener_nombres_hojas(archivo)
        except Exception as error:
            st.warning(f'No se pudieron leer las hojas de {archivo.name}: {error}')
            seleccion_hojas_incompleta = True
            continue
        huella = hashlib.sha256(f'{indice_archivo}:{archivo.name}:{import_hash_archivos[indice_archivo]}'.encode('utf-8')).hexdigest()[:16]
        elegidas = st.multiselect(
            f'Hojas a procesar — {archivo.name}', options=nombres_hojas,
            default=[], key=f'hojas_ingram_libres_{huella}',
        )
        hojas_por_archivo[indice_archivo] = list(elegidas)
        if not elegidas:
            st.warning(f'Selecciona al menos una hoja de {archivo.name} para procesar.')
            seleccion_hojas_incompleta = True
        else:
            with st.expander(f'Vista previa de {elegidas[0]}'):
                archivo.seek(0)
                vista_previa = pd.read_excel(archivo, sheet_name=elegidas[0], header=None, nrows=18).fillna('').astype(str)
                st.dataframe(vista_previa, hide_index=True)
                archivo.seek(0)
if proveedor == 'SolutionBox':
    st.caption('SolutionBox: el PN se usa como código de proveedor y mpn. La marca se copia solo de una columna MARCA. Se excluyen productos por encargo o sin cantidad disponible.')
    for indice_archivo, archivo in enumerate(archivos):
        if not archivo.name.lower().endswith(('.xlsx', '.xls')):
            continue
        try:
            nombres_hojas = obtener_nombres_hojas(archivo)
            elegidas = st.multiselect(
                f'Hojas a procesar — {archivo.name}', options=nombres_hojas,
                default=nombres_hojas,
                key=f'hojas_solutionbox_{indice_archivo}_{import_hash_archivos[indice_archivo]}',
            )
            hojas_por_archivo[indice_archivo] = list(elegidas)
            if not elegidas:
                st.warning('Selecciona al menos una hoja para procesar.')
                seleccion_hojas_incompleta = True
        except Exception as error:
            st.warning(f'No se pudieron leer las hojas de {archivo.name}: {error}')
            seleccion_hojas_incompleta = True
if proveedor == 'Demco Ltda.':
    st.caption('Demco: se revisan todas las hojas. Se usa Código Interno como código de proveedor, Número de Parte como PN y Precio Neto como costo.')
st.session_state.setdefault(f'moneda_lista_{proveedor}', moneda_predeterminada(proveedor))
moneda_valor = st.selectbox(
    'Moneda de la lista', ['USD', 'CLP'],
    key=f'moneda_lista_{proveedor}',
    help='Se aplica a todos los productos del lote, incluso si el encabezado indica otra moneda. No convierte los importes.',
)
if proveedor == 'Kepler':
    st.caption('Kepler: se usa el precio normal; la preventa se excluye.')
permitir_pn = st.checkbox('Confirmo que para Nexsys el CRM acepta el número de parte como código de proveedor') if proveedor == 'Nexsys' else False
fecha = st.date_input('Fecha de vigencia', value=calcular_expiry_date())

# Evitar que se descarguen resultados de archivos, hojas, proveedor o fecha anteriores.
firma = (
    proveedor, moneda_valor, permitir_pn, str(fecha), proveedor_confirmado,
    tuple((a.name, import_hash_archivos[i]) for i, a in enumerate(archivos)),
    tuple((i, tuple(hojas)) for i, hojas in sorted(hojas_por_archivo.items())),
)
if st.session_state.get('firma_lote') != firma:
    st.session_state.pop('lote', None)
    st.session_state['firma_lote'] = firma
    for clave in list(st.session_state):
        if clave.startswith(('elegir_sku_', 'resolver_conflicto_')):
            del st.session_state[clave]

if st.button('Procesar listas'):
    if not archivos:
        st.warning('Primero debes subir una o más listas de precios.')
    elif proveedor == 'Seleccionar...':
        st.warning('Primero debes seleccionar un proveedor.')
    elif not proveedor_confirmado:
        st.warning('Revisa los archivos y confirma que pertenecen al proveedor seleccionado antes de procesar.')
    elif proveedor not in PROVEEDORES_CONFIGURADOS:
        st.warning(f'{proveedor} todavía no tiene reglas configuradas. No se procesó ningún archivo.')
    elif seleccion_hojas_incompleta:
        st.warning('Selecciona al menos una hoja válida antes de procesar.')
    else:
        st.session_state['lote'] = procesar_archivos(
            archivos, fecha, proveedor, moneda_valor, permitir_pn,
            hojas_por_archivo=hojas_por_archivo,
        )

if 'lote' in st.session_state:
    resumen, combinado = st.session_state['lote']
    st.info('Vigencia aplicada: ' + formatear_expiry_date(fecha))
    st.subheader('Resumen por archivo')
    st.dataframe(resumen, hide_index=True)
    st.download_button('Descargar resumen CSV', resumen.to_csv(index=False).encode('utf-8-sig'),
                       file_name='Resumen de listas.csv', mime='text/csv')
    errores = (resumen['Estado'] == 'Error').sum()
    if errores:
        st.warning(f'{errores} archivo(s) no pudieron procesarse. El consolidado solo incluye los archivos procesados.')
    if combinado.empty:
        st.warning('No hay productos válidos para generar el Excel CRM.')
    else:
        limpios, conflictos, repetidos = consolidar(combinado)
        st.write(f"Filas válidas: {len(combinado)} · Duplicados idénticos eliminados: {repetidos} · "
                 f"SKU con diferencias: {conflictos['provider_code'].nunique()}")
        # Solo se agregan SKU conflictivos cuando el usuario elige explícitamente
        # una fila. Las ediciones se aplican al resultado, no al archivo de origen.
        seleccionados = [limpios]
        sin_resolver = []
        if not conflictos.empty:
            st.subheader('Revisar SKU con diferencias')
            st.caption(
                'Puedes corregir los campos directamente. Marca “Conservar” en exactamente '
                'una fila por SKU. No se completan datos automáticamente. El Excel original no se modifica.'
            )
            for sku, grupo in conflictos.groupby('provider_code', sort=False):
                st.write('SKU en conflicto: ' + str(sku))
                editor = preparar_vista(grupo).copy()
                editor.insert(0, 'Conservar', False)
                clave_editor = 'resolver_conflicto_' + hashlib.sha256(
                    str(sku).encode('utf-8')
                ).hexdigest()[:16]
                editado = st.data_editor(
                    editor,
                    hide_index=True,
                    key=clave_editor,
                    num_rows='fixed',
                    disabled=['Archivo de origen'],
                    column_order=['Conservar'] + [
                        columna for columna in editor.columns if columna != 'Conservar'
                    ],
                    column_config={
                        'Conservar': st.column_config.CheckboxColumn(
                            'Conservar',
                            help='Selecciona exactamente una fila para este SKU.',
                            default=False,
                        )
                    },
                )
                elegidas = editado[editado['Conservar']]
                if len(elegidas) == 1:
                    seleccionados.append(elegidas.drop(columns=['Conservar']))
                else:
                    sin_resolver.append(str(sku))

        final = pd.concat(seleccionados, ignore_index=True).drop(
            columns=['Archivo de origen', 'Conservar'], errors='ignore'
        )
        if sin_resolver:
            st.warning(
                f"{len(sin_resolver)} SKU siguen sin resolverse y se excluirán del resultado. "
                'Para incluir uno, marca una sola fila en su tabla.'
            )
        elif not conflictos.empty:
            st.success('Todos los SKU con diferencias tienen una fila elegida para el resultado.')

        codigos_repetidos = final['provider_code'].duplicated(keep=False)
        if codigos_repetidos.any():
            st.error(
                'Hay provider_code repetidos después de las correcciones. Ajusta los códigos '
                'en las tablas de revisión antes de descargar o copiar.'
            )
        st.subheader('Consolidado CRM')
        st.write(f'{len(final)} productos listos para descargar')
        st.dataframe(preparar_vista(final), hide_index=True)
        if not final.empty and not codigos_repetidos.any():
            col_descarga, col_copiar = st.columns([2, 1])
            with col_descarga:
                st.download_button('Descargar archivo listo para CRM', generar_excel(final),
                    file_name='Directo para cargar al CRM.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            with col_copiar:
                boton_copiar_excel(final)
        elif final.empty:
            st.warning('No quedaron productos sin conflictos para generar el Excel CRM.')

