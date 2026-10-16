"""Reglas de Compu Soluciones. No se infieren datos de producto ausentes."""
import pandas as pd

from common import limpiar_numero, normalizar_productos, normalizar_texto_columna
from file_readers import leer_hoja_xlsx_con_datos, obtener_nombres_hojas

NOMBRE = 'Compu Soluciones'
PATRON = r'(?:COMPU[\W_]*SOLUCIONES|COMPUSOLUCIONES)'
MONEDA = 'USD'


def leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None):
    if not archivo.name.lower().endswith(('.xlsx', '.xls')):
        raise ValueError('Compu Soluciones: por ahora se admiten listas Excel.')
    nombres = hojas_seleccionadas if hojas_seleccionadas is not None else obtener_nombres_hojas(archivo)
    salida, leidos, usadas = [], 0, []
    for nombre in nombres:
        bruto = leer_hoja_xlsx_con_datos(archivo, nombre)
        for inicio, fila in bruto.iterrows():
            columnas = [normalizar_texto_columna(v) for v in fila]
            if 'MODELO' not in columnas:
                continue
            stock = next((c for c in ('CANTIDAD', 'STOCK') if c in columnas), None)
            precio_regular = next((c for c in ('PRECIO DISTR.', 'PRECIO LISTA DISTR.') if c in columnas), None)
            descuento = 'PRECIO CON DESCUENTO' if 'PRECIO CON DESCUENTO' in columnas else None
            nombre_producto = next((c for c in ('NOMBRE PRODUCTO', 'DESCRIPCION') if c in columnas), None)
            if not all((stock, precio_regular, nombre_producto)):
                continue
            requeridas = {'MODELO', stock, precio_regular, nombre_producto}
            if descuento:
                requeridas.add(descuento)
            if any(columnas.count(c) != 1 for c in requeridas):
                raise ValueError(f'Compu Soluciones: encabezados duplicados en {nombre}.')
            datos = bruto.iloc[inicio + 1:].dropna(how='all').copy()
            def campo(columna):
                return datos.iloc[:, columnas.index(columna)]
            precio = campo(precio_regular).map(limpiar_numero)
            if descuento:
                oferta = campo(descuento).map(limpiar_numero)
                # La oferta solo aplica si está informada y es un importe positivo.
                precio = pd.concat([precio, oferta], axis=1).where(lambda f: f > 0).min(axis=1)
            base = pd.DataFrame({
                'SKU': campo('MODELO'),
                'venta neto usd': precio,
                'stock actual': campo(stock).map(limpiar_numero),
            }, index=datos.index)
            resultado = normalizar_productos(base, fecha)
            pn = 'NO. DE PARTE' if 'NO. DE PARTE' in columnas else 'MODELO'
            resultado['mpn'] = campo(pn).loc[resultado.index].fillna('').astype(str).str.strip()
            resultado['name'] = campo(nombre_producto).loc[resultado.index].fillna('').astype(str).str.strip()
            resultado['currency'] = 'USD'
            salida.append(resultado)
            leidos += len(datos)
            usadas.append(nombre)
            break
    archivo.seek(0)
    if not salida:
        raise ValueError('Compu Soluciones: no se encontraron hojas con Modelo, stock y precio compatibles.')
    return pd.concat(salida, ignore_index=True), leidos, (
        'Compu Soluciones: Modelo como provider_code; No. de Parte como PN cuando existe. '
        'Se usa Precio con descuento si está informado; de lo contrario, Precio Distribuidor. '
        'Marca no inferida. Hojas procesadas: ' + ', '.join(usadas)
    )

