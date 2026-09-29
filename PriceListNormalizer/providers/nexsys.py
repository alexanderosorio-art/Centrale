"""Reglas de Nexsys. No se infieren datos de producto ausentes."""
from table_reader import ReglasTabla, leer_tablas
import math
import re
import pandas as pd
import openpyxl
from common import normalizar_texto_columna as norm, limpiar_numero, normalizar_productos
from file_readers import obtener_nombres_hojas

NOMBRE = 'Nexsys'
PATRON = r'NEXSYS'
MONEDA = 'USD'
REGLAS = ReglasTabla(
    nombre=NOMBRE, codigos=('SKU', 'CODIGO'), codigo_desde_pn=True,
    preferir_oferta=True,
    # Ofertas unitarias observadas en ASUS. No incluir precios por volumen.
    ofertas=('OFERTA', 'PRECIO OFERTA', 'PRECIOS OFERTAS USD'),
)


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.xlsx') and es_catalogo(obtener_nombres_hojas(archivo)):
        return leer_catalogo(archivo, fecha, hojas_seleccionadas)
    # Equivalencia PN/código confirmada por el usuario para Nexsys.
    resultado, leidos, detalle = leer_tablas(
        archivo, fecha, moneda, True, hojas_seleccionadas, reglas=REGLAS)
    resultado['mpn'] = resultado['mpn'].where(resultado['mpn'].ne(''), resultado['provider_code'])
    return resultado, leidos, detalle


# Solo este catálogo: USD por defecto según las hojas aprobadas por el usuario.
# Una indicación explícita de CLP siempre prevalece y excluye el producto.
HOJAS_CATALOGO = {
    norm(nombre) for nombre in (
        'HP Notebook', 'HP Poly', 'HP Desktop - AIO', 'HP Workstation',
        'Impresión Láser - Tinta', 'HP POS', 'Suministros HP', 'Retail',
        'LISTA AXS&MONITORES', 'LENOVO NOTEBOOK_WS',
        'LENOVO AIO-DESKTOP-MONITORES', 'LENOVO SMARTHUB',
        'ACCS.CORPORATIVOS', 'EPSON', 'ASUS Notebook', 'ASUS Dekstop - AIO', 'JABRA',
    )
}


def es_catalogo(nombres):
    # Las listas ASUS independientes siguen usando su lector existente.
    return any(norm(n) in HOJAS_CATALOGO - {'ASUS NOTEBOOK', 'ASUS DEKSTOP - AIO'} for n in nombres)


def numero_catalogo(valor):
    """No convertir comentarios, fechas ni plazos de tránsito en cantidades."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return valor if math.isfinite(valor) else None
    texto = norm(valor).replace('USD', '').replace('US$', '').replace('$', '')
    texto = texto.replace('(+)', '+').replace(' ', '')
    if not re.fullmatch(r'[+\-]?\d[\d.,]*(?:[+]|[.,]-)?', texto):
        return None
    valor = limpiar_numero(texto)
    return float(valor) if pd.notna(valor) else None


def moneda_celda(celda):
    # El símbolo $ y los códigos de idioma de Excel NO identifican una moneda.
    texto = norm(celda.value)
    formato = norm(celda.number_format)
    if re.search(r'\bCLP\b', texto + ' ' + formato):
        return 'CLP'
    if re.search(r'\bUSD\b|US\$', texto + ' ' + formato):
        return 'USD'
    return None


def leer_catalogo(archivo, fecha, hojas_seleccionadas=None):
    """Catálogo Hardware aprobado: hojas permitidas, USD y ofertas aplicables."""
    if hojas_seleccionadas == []:
        raise ValueError('Selecciona al menos una hoja de Nexsys.')
    archivo.seek(0)
    libro = openpyxl.load_workbook(archivo, data_only=True, read_only=True)
    filas, resumen, omitidas = [], [], []
    leidos = 0
    codigos = ('SKU', 'CODIGO DE ARTICULO', 'P/N', 'NUMERO DE PARTE', 'PART NUMBER')
    stocks = ('STOCK', 'STOCK REFERENCIAL', 'QTY', 'INVENTARIO FISICO', 'INVENTARIO')
    nombres = ('DESCRIPCION', 'DESCRIPCION RESUMIDA', 'NOMBRE DEL ARTICULO', 'MODELO')
    precios = ('PRECIO NORMAL USD', 'PRECIO DE VENTA US$', 'VALOR NORMAL', 'PRECIO USD',
               'PRECIO NORMAL', 'PRECIO FINAL', 'PRECIO CANAL USD-CLP', 'PRECIO CANAL $',
               'PRECIO LISTA NETO USD', 'PRECIO NETO USD', 'PRECIO REGULAR USD', 'USD',
               'PRECIO USD (S/IVA)', 'PRECIOS USD', 'PRECIO RESELLER PREMIUM (CERTIFICADOS)')
    ofertas = ('PRECIO OFERTA USD', 'PRECIO OFERTA', 'OFERTA', 'PRECIO DESCUENTO USD',
               'PRECIOS OFERTAS USD')
    try:
        for hoja in libro:
            clave = norm(hoja.title)
            if clave not in HOJAS_CATALOGO or (hojas_seleccionadas is not None and hoja.title not in hojas_seleccionadas):
                omitidas.append(hoja.title.strip())
                continue
            if clave == 'EPSON':
                resumen.append('EPSON: excluida completa (CLP)')
                continue
            esquema = None
            validos = clp = invalidos = desconocidos = cantidad_leida = 0
            for row in hoja.iter_rows():
                cols = [norm(c.value) if c.value is not None else '' for c in row]
                def buscar(opciones):
                    return next((cols.index(c) for c in opciones if c in cols), None)
                cod = buscar(codigos)
                if cod is not None:
                    stk, pre, nom = buscar(stocks), buscar(precios), buscar(nombres)
                    # Un encabezado de garantías termina la tabla de hardware.
                    esquema = None
                    if all(c is not None for c in (stk, pre, nom)):
                        promo = [cols.index(c) for c in ofertas if c in cols]
                        if clave == 'HP POLY':
                            # Plantilla validada: única columna entre inventario y precio.
                            # Su título/fecha cambia; no depende del texto del encabezado.
                            if pre != stk + 2:
                                raise ValueError('HP Poly: cambió la posición de la columna promocional; requiere revisión.')
                            promo.append(stk + 1)
                        esquema = (cod, stk, pre, nom, promo, buscar(('MONEDA',)),
                                   buscar(('MARCA',)), buscar(('PRECIO PROMO NETO', 'PRECIO PROMO')),
                                   buscar(('UNIDADES PROMO',)))
                    continue
                if esquema is None:
                    continue
                cod, stk, pre, nom, promo, div, marca, promo_lenovo, unidades = esquema
                valor_codigo = row[cod].value
                if valor_codigo is None or not str(valor_codigo).strip():
                    continue
                if row[pre].value is None and row[stk].value is None and not any(row[c].value is not None for c in promo):
                    continue
                cantidad_leida += 1
                # CLP en el valor o formato prevalece incluso sobre un encabezado USD.
                moneda_base = moneda_celda(row[pre])
                if div is not None:
                    moneda_fila = norm(row[div].value).replace('$', '').replace(' ', '')
                    if moneda_fila not in ('USD', 'CLP'):
                        desconocidos += 1
                        continue
                    if moneda_fila == 'CLP' or moneda_base == 'CLP':
                        clp += 1
                        continue
                elif moneda_base == 'CLP':
                    clp += 1
                    continue
                cantidad = numero_catalogo(row[stk].value)
                regular = numero_catalogo(row[pre].value)
                candidatos = [(regular, cantidad)] if regular is not None and regular > 0 else []
                for col in promo:
                    precio = numero_catalogo(row[col].value)
                    if moneda_celda(row[col]) != 'CLP' and precio is not None and precio > 0:
                        candidatos.append((precio, cantidad))
                if promo_lenovo is not None and unidades is not None:
                    precio = numero_catalogo(row[promo_lenovo].value)
                    limite = numero_catalogo(row[unidades].value)
                    if (moneda_celda(row[promo_lenovo]) != 'CLP' and precio is not None and precio > 0
                            and limite is not None and limite > 0 and cantidad is not None):
                        candidatos.append((precio, min(cantidad, limite)))
                if cantidad is None or cantidad <= 0 or not candidatos:
                    invalidos += 1
                    continue
                precio, cantidad = min(candidatos, key=lambda item: item[0])
                codigo = str(valor_codigo).strip()
                filas.append({'SKU': codigo, 'venta neto usd': precio, 'stock actual': cantidad,
                              'mpn': codigo, 'name': str(row[nom].value or '').strip(),
                              'brand': str(row[marca].value or '').strip() if marca is not None else ''})
                validos += 1
            leidos += cantidad_leida
            resumen.append(f'{hoja.title.strip()}: {validos} USD, {clp} CLP excluidos, '
                           f'{desconocidos} moneda sin identificar, {invalidos} sin stock/precio válido')
            if cantidad_leida == 0:
                resumen[-1] += ' (sin filas compatibles)'
    finally:
        libro.close()
        archivo.seek(0)
    fuente = pd.DataFrame(filas, columns=['SKU', 'venta neto usd', 'stock actual', 'mpn', 'name', 'brand'])
    resultado = normalizar_productos(fuente, fecha)
    for campo in ('mpn', 'name', 'brand'):
        resultado[campo] = fuente.loc[resultado.index, campo]
    resultado.attrs['currency_policy'] = 'USD_ONLY'
    detalle = 'Catálogo Nexsys: solo USD. ' + '; '.join(resumen)
    if omitidas:
        detalle += '. Hojas fuera de selección: ' + ', '.join(omitidas)
    return resultado, leidos, detalle
