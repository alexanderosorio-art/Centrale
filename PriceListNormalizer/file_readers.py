"""Lectura de archivos y detección genérica de encabezados."""
import csv
import pandas as pd

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


def obtener_nombres_hojas(archivo):
    archivo.seek(0)
    nombres = pd.ExcelFile(archivo).sheet_names
    archivo.seek(0)
    return nombres


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

def leer_csv(archivo):
    encabezado, separador, encoding = detectar_csv(archivo)
    archivo.seek(0)
    return pd.read_csv(archivo, header=encabezado, sep=separador, encoding=encoding)
