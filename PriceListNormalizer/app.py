import streamlit as st
import pandas as pd
import csv
import re

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
                # Excel usa el apóstrofe inicial como indicador de texto al pegar.
                return "'" + fecha.strftime('%d-%m-%Y  %H:%M')
            return str(valor).strip()
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
    """Genera tabla HTML que mantiene expiry_date como texto al pegar en Excel."""
    datos = formatear_datos_copia(df)
    filas = []
    for valores in datos.itertuples(index=False, name=None):
        celdas = []
        for columna, valor in zip(datos.columns, valores):
            contenido = escape(str(valor)).replace("  ", "&#160;&#160;")
            if columna == "expiry_date":
                celdas.append(
                    f'<td style="mso-number-format:\'\\@\'; white-space:pre">{contenido}</td>'
                )
            else:
                celdas.append(f"<td>{contenido}</td>")
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    return "<html><head><meta charset=\"utf-8\"></head><body><table><tbody>" + "".join(filas) + "</tbody></table></body></html>"


def boton_copiar_excel(df):
    texto = json.dumps(generar_tsv(df), ensure_ascii=False).replace("</", "<\\/")
    html = json.dumps(generar_html_copia_excel(df), ensure_ascii=False).replace("</", "<\\/")
    components.html(
        f"""
        <button id="copiar-excel" type="button" style="
            width:100%; min-height:42px; padding:0.4rem 0.75rem;
            border:1px solid rgba(250,250,250,.2); border-radius:.5rem;
            background:#262730; color:#fafafa; font:inherit; cursor:pointer;
        ">Copiar para Excel</button>
        <script>
            const texto = {texto};
            const html = {html};
            const boton = document.getElementById('copiar-excel');
            boton.addEventListener('click', async () => {{
                try {{
                    if (navigator.clipboard.write && window.ClipboardItem) {{
                        const contenido = new ClipboardItem({{
                            'text/plain': new Blob([texto], {{ type: 'text/plain' }}),
                            'text/html': new Blob([html], {{ type: 'text/html' }})
                        }});
                        await navigator.clipboard.write([contenido]);
                    }} else {{
                        await navigator.clipboard.writeText(texto);
                    }}
                }} catch (error) {{
                    const campo = document.createElement('textarea');
                    campo.value = texto;
                    campo.style.position = 'fixed';
                    campo.style.opacity = '0';
                    document.body.appendChild(campo);
                    campo.select();
                    const copiado = document.execCommand('copy');
                    campo.remove();
                    if (!copiado) {{
                        boton.textContent = 'No se pudo copiar';
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
    # El formato Kepler validado por el CRM mantiene name vacío.
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


def leer_nuevo_proveedor(archivo, proveedor, fecha, moneda, permitir_pn):
    # Solo se admiten encabezados observados; tránsito y ofertas no sustituyen stock/precio normal.
    codigos = {'Tecnoglobal': ['CODIGO TG', 'CODIGO', 'CODIGO SISTEMA', 'SKU'],
               'Ingram': ['MATERIAL/SKU', 'INGRAM MICRO SKU', 'IM SKU', 'MATERIAL'],
               'Coimco': ['CODIGO', 'CODIGO SISTEMA', 'SKU'],
               'Fujicorp': ['CODIGO', 'SKU'],
               'Nexsys': ['SKU', 'CODIGO']}[proveedor]
    precios = ['PV OFERTA C/U', 'PRECIO UNITARIO US$', 'PRECIO USD (S/IVA)', 'PRECIOS USD', 'PRECIO USD$',
               'PRECIO US$', 'VALOR USD', 'PRECIO', 'MAYORISTA', 'DISTRIBUIDOR', 'VALOR $',
               'VALOR', 'NETO']
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
    hojas = {'CSV': pd.read_csv(archivo, header=None)} if archivo.name.lower().endswith('.csv') else pd.read_excel(archivo, sheet_name=None, header=None)
    preferir_oferta = proveedor == 'Fujicorp'
    salida, omitidas, usadas = [], [], []
    leidos = 0
    for hoja, bruto in hojas.items():
        candidatos = []
        for i, row in bruto.iterrows():
            cols = list(row.map(norm))
            pn = next((c for c in ['NUMERO DE PARTE', 'PART_NUMBER', 'PART NUMBER', 'PARTNUMBER', 'P/N'] if c in cols), None)
            cod = next((c for c in codigos if c in cols), None)
            if not cod and proveedor == 'Nexsys':
                cod = pn
            stk = next((c for c in stocks if c in cols), None)
            ofertas = [c for c in ['OFERTA', 'OFERTA X VOLUMEN', 'PRECIO OFERTA'] if c in cols]
            precio_neto = next((c for c in precios if c in cols), None)
            descripcion = next((c for c in cols if c in ['DESCRIPTION', 'MKT NAME', 'MODELO']
                                or c.startswith('DESCRIPCI')), None)
            if cod and precio_neto and stk and descripcion:
                candidatos.append((i, cols, cod, precio_neto, stk, pn, ofertas, descripcion))
        if not candidatos:
            omitidas.append(hoja)
            continue
        usadas.append(hoja)
        for posicion, (inicio, cols, cod, pre, stk, pn, ofertas, descripcion) in enumerate(candidatos):
            if proveedor == 'Nexsys' and cod == pn and not permitir_pn:
                raise ValueError('Nexsys: confirma que el CRM acepta el número de parte como provider_code.')
            divisa = 'CLP' if proveedor in ['Coimco', 'Fujicorp'] else ('USD' if 'USD' in pre or 'US$' in pre else moneda)
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
            base = pd.DataFrame({'SKU': datos.iloc[:,cols.index(cod)],
                'venta neto usd': precio_base,
                'stock actual': datos.iloc[:,cols.index(stk)].map(numero)})
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
    detalle = 'Hojas procesadas: ' + ', '.join(usadas)
    if omitidas:
        detalle += '. Hojas sin tabla compatible: ' + ', '.join(omitidas)
    return pd.concat(salida, ignore_index=True), leidos, detalle


def procesar_archivos(archivos, fecha, proveedor="Intcomex", moneda_valor="Sin confirmar", permitir_pn=False):
    resumen, resultados = [], []
    for numero, archivo in enumerate(archivos, 1):
        nombre = f"{numero}. {archivo.name}"
        fila = {"Archivo": nombre, "Leídos": 0, "Válidos": 0,
                "Descartados": 0, "Estado": "", "Detalle": ""}
        try:
            if proveedor in ['Tecnoglobal', 'Nexsys', 'Ingram', 'Coimco', 'Fujicorp']:
                resultado, leidos, detalle = leer_nuevo_proveedor(archivo, proveedor, fecha, moneda_valor, permitir_pn)
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
                if proveedor == 'Kepler':
                    bruto = pd.read_excel(archivo, header=None)
                    candidatos = [i for i, row in bruto.iterrows() if set(row.map(normalizar_columna)) & {'SKU', 'SKU/LINK', 'CODIGO'} and set(row.map(normalizar_columna)) & {'DOLAR', 'VALOR USD', 'U$ NETO', 'VALOR'}]
                    if not candidatos:
                        raise ValueError('No se encontró un encabezado Kepler compatible.')
                    encabezado = candidatos[0]
                else:
                    encabezado = detectar_encabezado(archivo)
                archivo.seek(0)
                df = pd.read_excel(archivo, header=encabezado)
            fila['Leídos'] = len(df)
            if proveedor == 'Kepler':
                resultado = procesar_kepler(df, fecha, archivo.name, moneda_valor)
            elif (
                proveedor == 'Intcomex'
                and {'PART NUMBER (MPN)', 'PRECIO ESPECIAL NETO UNIT. CENTRALE'}
                .issubset({normalizar_texto_columna(columna) for columna in df.columns})
            ):
                resultado = procesar_intcomex_wd(df, fecha)
            else:
                resultado = procesar_intcomex(df, fecha)
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


st.title('Price List Normalizer')
st.write('Generador de listas de precios para carga al CRM')
proveedor = st.selectbox('Proveedor', ['Seleccionar...', 'Ingram', 'Intcomex', 'Tecnoglobal', 'Coimco', 'Fujicorp', 'Kepler', 'Nexsys'])
archivos = st.file_uploader('Subir listas de precios del mismo proveedor',
                           type=['xlsx', 'xls', 'csv'], accept_multiple_files=True)
st.caption('Puedes seleccionar varios archivos. Tecnoglobal, Nexsys, Ingram, Coimco y Fujicorp: se revisan todas las hojas. Intcomex y Kepler: primera hoja. '
           'La consolidación CRM está disponible para los proveedores con reglas configuradas.')
moneda_valor = st.selectbox('Moneda cuando el archivo no la indica (PRECIO / VALOR)', ['Sin confirmar', 'USD', 'CLP']) if proveedor in ['Kepler', 'Tecnoglobal', 'Nexsys', 'Ingram'] else 'Sin confirmar'
if proveedor == 'Kepler':
    st.caption('Kepler: se usa el precio normal; la preventa se excluye. Confirma la moneda si una lista solo dice VALOR.')
permitir_pn = st.checkbox('Confirmo que para Nexsys el CRM acepta el número de parte como código de proveedor') if proveedor == 'Nexsys' else False
fecha = st.date_input('Fecha de vigencia', value=calcular_expiry_date())

# Evitar que se descarguen resultados de archivos, proveedor o fecha anteriores.
import hashlib
firma = (proveedor, moneda_valor, permitir_pn, str(fecha), tuple((a.name, hashlib.sha256(a.getvalue()).hexdigest()) for a in archivos))
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
    elif proveedor not in ['Intcomex', 'Kepler', 'Tecnoglobal', 'Nexsys', 'Ingram', 'Coimco', 'Fujicorp']:
        st.warning('Este proveedor todavía no tiene reglas configuradas. La carga múltiple está disponible para Intcomex y Kepler.')
    else:
        st.session_state['lote'] = procesar_archivos(archivos, fecha, proveedor, moneda_valor, permitir_pn)

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

