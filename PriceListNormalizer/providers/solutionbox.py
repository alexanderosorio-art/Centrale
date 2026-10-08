"""Lectura de las listas SolutionBox."""
import re
import pandas as pd
from common import limpiar_numero, normalizar_texto_columna, normalizar_productos

NOMBRE = 'SolutionBox'
PATRON = r'SOLUTION[\W_]*BOX'
MONEDA = 'USD'

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
            resultado = normalizar_productos(base, fecha)
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


def leer_solutionbox_pdf(archivo, fecha, moneda):
    import pdfplumber
    salida, leidos = [], 0
    archivo.seek(0)
    with pdfplumber.open(archivo) as documento:
        for pagina in documento.pages:
            for tabla in pagina.extract_tables():
                if not tabla:
                    continue
                encabezado = [normalizar_texto_columna(v) for v in tabla[0]]
                # En esta plantilla el encabezado se extrae como celda combinada.
                if encabezado == ['STOCK SKU DESCRIPCION PRECIO UNITARIO', 'NONE', 'NONE', 'NONE']:
                    encabezado = ['STOCK', 'SKU', 'DESCRIPCION', 'PRECIO UNITARIO']
                if encabezado != ['STOCK', 'SKU', 'DESCRIPCION', 'PRECIO UNITARIO']:
                    continue
                if any(len(fila) != 4 for fila in tabla[1:]):
                    raise ValueError('SolutionBox PDF: cambió la estructura de la tabla; revisa las columnas.')
                datos = pd.DataFrame(tabla[1:], columns=encabezado)
                leidos += len(datos)
                stock = datos['STOCK'].astype(str).str.strip()
                stock = pd.to_numeric(stock.where(stock.str.fullmatch(r'\d+\+?')).str.rstrip('+'), errors='coerce')
                base = pd.DataFrame({'SKU': datos['SKU'],
                    'venta neto usd': datos['PRECIO UNITARIO'].map(limpiar_numero), 'stock actual': stock})
                result = normalizar_productos(base, fecha)
                result['name'] = datos.loc[result.index, 'DESCRIPCION'].fillna('').astype(str).str.strip()
                result['currency'] = moneda
                # No hay columna PN ni marca: no se deducen del logo o del SKU.
                salida.append(result)
    archivo.seek(0)
    if not salida:
        raise ValueError('SolutionBox PDF: no hay tabla compatible STOCK, SKU, DESCRIPCION, precio unitario; un PDF escaneado requiere OCR.')
    return pd.concat(salida, ignore_index=True), leidos, 'PDF SolutionBox: SKU, descripción, stock y precio unitario. No se infiere PN ni marca.'


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if archivo.name.lower().endswith('.pdf'):
        return leer_solutionbox_pdf(archivo, fecha, moneda)
    return leer_solutionbox(archivo, fecha, moneda, hojas_seleccionadas)
