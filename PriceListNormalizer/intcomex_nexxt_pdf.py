"""Lector auxiliar PDF Nexxt Intcomex: cantidad inmediata y precio neto USD."""
import re
from datetime import datetime
import pandas as pd
from common import normalizar_texto_columna, normalizar_productos, limpiar_numero

ENCABEZADOS = ['FOTO', 'MPN', 'SKU', 'DESCRIPCION', 'CANTIDAD', 'TRANSITO', 'PRECIO USD NETO']


def leer_nexxt_pdf(archivo, fecha):
    import pdfplumber
    filas, reconocida = [], False
    archivo.seek(0)
    with pdfplumber.open(archivo) as documento:
        for pagina in documento.pages:
            texto = pagina.extract_text() or ''
            for tabla in pagina.extract_tables():
                for fila in tabla:
                    if [normalizar_texto_columna(v) for v in fila] == ENCABEZADOS:
                        reconocida = True
                        vigencia = re.search(r'Validez\s*(\d{2}-\d{2}-\d{4})', texto, re.I)
                        if vigencia:
                            fecha = datetime.strptime(vigencia[1], '%d-%m-%Y').date()
                        continue
                    if not reconocida:
                        continue
                    if len(fila) != len(ENCABEZADOS):
                        raise ValueError('Intcomex Nexxt PDF: cambió la estructura de la tabla; revisa la página.')
                    if not any(str(v or '').strip() for v in fila):
                        continue
                    if not re.fullmatch(r'[A-Z0-9]+NXT\d+', str(fila[2] or '').strip()):
                        raise ValueError('Intcomex Nexxt PDF: código de producto no reconocible en la tabla.')
                    filas.append(fila)
    archivo.seek(0)
    if not reconocida:
        return None
    datos = pd.DataFrame(filas, columns=ENCABEZADOS)
    def cantidad(v):
        texto = normalizar_texto_columna(v)
        if re.fullmatch(r'MAS DE \d+ UNIDADES', texto):
            return int(re.search(r'\d+', texto)[0])
        if re.fullmatch(r'\d+\s*\+?', texto):
            return int(texto.rstrip('+').strip())
        return None
    base = pd.DataFrame({'SKU': datos['SKU'],
                         'venta neto usd': datos['PRECIO USD NETO'].map(limpiar_numero),
                         'stock actual': datos['CANTIDAD'].map(cantidad)})
    resultado = normalizar_productos(base, fecha)
    for destino, origen in [('mpn', 'MPN'), ('name', 'DESCRIPCION')]:
        resultado[destino] = datos.loc[resultado.index, origen].fillna('').astype(str).str.replace('\n', ' ', regex=False).str.strip()
    resultado.attrs['currency_policy'] = 'USD_ONLY'
    return resultado, len(datos), ('Intcomex Nexxt PDF: todas las páginas; Precio USD Neto y solo Cantidad inmediata. '
        'Tránsito no se suma; Más de 100 unidades se registra como 100. Vigencia del PDF; marca no inferida.')

