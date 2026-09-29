"""Motor común de tablas Excel/CSV/PDF; las reglas viven en providers/."""
import re
import pandas as pd
from dataclasses import dataclass
from common import normalizar_texto_columna, normalizar_productos
from file_readers import obtener_nombres_hojas, leer_hoja_xlsx_con_datos

PRECIOS = ('PV OFERTA C/U', 'PRECIO UNITARIO US$', 'PRECIO USD (S/IVA)', 'PRECIOS USD', 'PRECIO USD$',
           'VALOR USD + IVA', 'PRECIO ESPECIAL NETO UNIT. CENTRALE', 'VENTA NETO USD',
           'PRECIO US$', 'VALOR USD', 'PRECIO', 'MAYORISTA', 'DISTRIBUIDOR', 'VALOR $', 'VALOR', 'NETO')
PART_NUMBERS = ('NUMERO DE PARTE', 'PART_NUMBER', 'PART NUMBER', 'PARTNUMBER', 'P/N')

@dataclass(frozen=True)
class ReglasTabla:
    nombre: str
    codigos: tuple[str, ...]
    precios: tuple[str, ...] = PRECIOS
    stocks: tuple[str, ...] = ('STOCK SIN RESERVA', 'CANTIDAD', 'STOCK DISPONIBLE', 'STOCK REFERENCIAL', 'STOCK')
    part_numbers: tuple[str, ...] = PART_NUMBERS
    lectura_acotada: bool = False
    preferir_oferta: bool = False
    codigo_desde_pn: bool = False
    stock_estricto: bool = False
    descripcion_exacta: str | None = None
    requiere_descripcion: bool = True
    moneda_fija: str | None = None


def leer_tablas(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None, *, reglas):
    codigos = reglas.codigos
    precios = reglas.precios
    stocks = reglas.stocks
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
                    # Alternativa para tablas sin bordes visibles.
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
    elif reglas.lectura_acotada and archivo.name.lower().endswith('.xlsx'):
        if hojas_seleccionadas == []:
            raise ValueError(f'Selecciona al menos una hoja de {reglas.nombre} para procesar.')
        nombres = hojas_seleccionadas if hojas_seleccionadas is not None else obtener_nombres_hojas(archivo)
        hojas = {nombre: leer_hoja_xlsx_con_datos(archivo, nombre) for nombre in nombres}
    else:
        archivo.seek(0)
        hojas = pd.read_excel(
            archivo,
            sheet_name=hojas_seleccionadas or None,
            header=None,
        )
        if isinstance(hojas, pd.DataFrame):
            hojas = {hojas_seleccionadas[0] if hojas_seleccionadas else 'Hoja 1': hojas}
    preferir_oferta = reglas.preferir_oferta
    salida, omitidas, usadas = [], [], []
    leidos = 0
    for hoja, bruto in hojas.items():
        candidatos = []
        for i, row in bruto.iterrows():
            cols = list(row.map(norm))
            opciones_pn = reglas.part_numbers
            pn = next((c for c in opciones_pn if c in cols), None)
            cod = next((c for c in codigos if c in cols), None)
            if not cod and reglas.codigo_desde_pn:
                cod = pn
            stk = next((c for c in stocks if c in cols), None)
            ofertas = [c for c in ['OFERTA', 'OFERTA X VOLUMEN', 'PRECIO OFERTA'] if c in cols]
            precio_neto = next((c for c in precios if c in cols), None)
            descripcion = next((c for c in cols if c in ['DESCRIPTION', 'MKT NAME', 'MODELO']
                                or c.startswith('DESCRIPCI')), None)
            if reglas.descripcion_exacta:
                descripcion = reglas.descripcion_exacta if reglas.descripcion_exacta in cols else None
            if cod and precio_neto and stk and (descripcion or not reglas.requiere_descripcion):
                candidatos.append((i, cols, cod, precio_neto, stk, pn, ofertas, descripcion))
        if not candidatos:
            omitidas.append(hoja)
            continue
        usadas.append(hoja)
        for posicion, (inicio, cols, cod, pre, stk, pn, ofertas, descripcion) in enumerate(candidatos):
            if reglas.codigo_desde_pn and cod == pn and not permitir_pn:
                raise ValueError(f'{reglas.nombre}: confirma que el CRM acepta el número de parte como provider_code.')
            divisa = (
                reglas.moneda_fija if reglas.moneda_fija
                else 'USD' if 'USD' in pre or 'US$' in pre
                else moneda
            )
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
            if reglas.stock_estricto:
                # No interpretar plazos o comentarios como cantidades.
                cantidades = pd.to_numeric(datos.iloc[:,cols.index(stk)], errors='coerce')
            base = pd.DataFrame({'SKU': datos.iloc[:,cols.index(cod)],
                'venta neto usd': precio_base,
                'stock actual': cantidades})
            result = normalizar_productos(base, fecha)
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
