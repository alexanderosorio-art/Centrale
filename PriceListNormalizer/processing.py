"""Detección del proveedor y procesamiento de lotes con errores por archivo."""
import re
import pandas as pd
from common import normalizar_columna, excluir_cajas_abiertas, normalizar_productos
from providers import REGISTRO
from catalog_lookup import resolver_por_catalogo, usar_catalogos_temporales, capturar_pendientes

def detectar_proveedores_archivo(nombre):
    # Comparar palabras completas; fechas y separadores pueden rodear el nombre.
    nombre = normalizar_columna(str(nombre).replace('\\', '/').rsplit('/', 1)[-1].rsplit('.', 1)[0])
    patrones = {m.NOMBRE: m.PATRON for m in REGISTRO.values() if m.PATRON}
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
    modulo = REGISTRO.get(proveedor)
    return modulo.MONEDA if modulo else 'USD'


def procesar_archivos(archivos, fecha, proveedor="Intcomex", moneda_valor=None, permitir_pn=False,
                     hojas_por_archivo=None, catalogos_temporales=None):
    """Procesa el lote; las bases cargadas por pantalla no se persisten."""
    with usar_catalogos_temporales(catalogos_temporales), capturar_pendientes() as pendientes:
        resumen, resultado = _procesar_archivos(
            archivos, fecha, proveedor, moneda_valor, permitir_pn,
            hojas_por_archivo=hojas_por_archivo,
        )
        resumen.attrs['pn_pendientes'] = list(dict.fromkeys(pendientes))
        return resumen, resultado


def _procesar_archivos(archivos, fecha, proveedor="Intcomex", moneda_valor=None, permitir_pn=False,
                      hojas_por_archivo=None):
    moneda_valor = moneda_valor or moneda_predeterminada(proveedor)
    if moneda_valor not in ('USD', 'CLP'):
        raise ValueError('Selecciona USD o CLP como moneda de la lista.')
    resumen, resultados = [], []
    for numero, archivo in enumerate(archivos, 1):
        nombre = f"{numero}. {archivo.name}"
        fila = {"Archivo": nombre, "Leídos": 0, "Válidos": 0,
                "Descartados": 0, "Estado": "", "Detalle": ""}
        try:
            if hasattr(archivo, 'tabla_pegada'):
                tabla = excluir_cajas_abiertas(archivo.tabla_pegada)
                tabla, pendientes_catalogo, detalle_catalogo = resolver_por_catalogo(tabla, proveedor)
                if pendientes_catalogo:
                    tabla = tabla.drop(index=pendientes_catalogo).copy()
                if tabla.empty:
                    raise ValueError('No quedaron filas con precio y SKU resoluble en el catálogo.')
                base = tabla.rename(columns={'provider_code': 'SKU', 'currency_unaware_cost_neto': 'venta neto usd', 'quantity': 'stock actual'})
                resultado = normalizar_productos(base, fecha)
                for c in ('mpn', 'name', 'brand'):
                    resultado[c] = tabla.loc[resultado.index, c]
                resultado['currency'] = moneda_valor
                detalle = 'Texto pegado: mapeo y moneda confirmados por el usuario. No se inventan datos.'
                if detalle_catalogo:
                    detalle += ' ' + detalle_catalogo + '.'
                if getattr(archivo, 'filas_sin_precio', 0):
                    detalle += f' Filas sin precio excluidas: {archivo.filas_sin_precio}.'
                if pendientes_catalogo:
                    detalle += f' Filas pendientes por código: {len(pendientes_catalogo)}.'
                fila.update({'Leídos': len(archivo.tabla_pegada), 'Válidos': len(resultado),
                    'Descartados': len(archivo.tabla_pegada)-len(resultado), 'Estado': 'Procesado',
                    'Detalle': detalle})
                resultado['Archivo de origen'] = nombre
                resultados.append(resultado)
                resumen.append(fila)
                continue
            modulo = REGISTRO.get(proveedor)
            if modulo is None or modulo.leer is None:
                raise ValueError(f'{proveedor} todavía no tiene reglas de procesamiento configuradas.')
            resultado, leidos, detalle = modulo.leer(
                archivo, fecha, moneda_valor, permitir_pn,
                hojas_seleccionadas=(hojas_por_archivo or {}).get(numero - 1),
            )
            antes = len(resultado)
            resultado = excluir_cajas_abiertas(resultado)
            if antes != len(resultado):
                detalle += f'. OPEN BOX/BAD BOX excluidos: {antes-len(resultado)}'
            # La elección del usuario prevalece; nunca convierte los importes.
            if resultado.attrs.get('currency_policy') != 'SOURCE':
                resultado['currency'] = 'USD' if resultado.attrs.get('currency_policy') == 'USD_ONLY' else moneda_valor
            fila.update({'Leídos': leidos, 'Válidos': len(resultado),
                         'Descartados': leidos-len(resultado), 'Estado': 'Procesado', 'Detalle': detalle})
            resultado['Archivo de origen'] = nombre
            resultados.append(resultado)
        except Exception as error:
            fila['Estado'] = 'Error'
            fila['Detalle'] = str(error)
        resumen.append(fila)
    combinado = pd.concat(resultados, ignore_index=True) if resultados else pd.DataFrame()
    return pd.DataFrame(resumen), combinado

