"""Interfaz Streamlit. Reglas de mayoristas en providers/."""
import hashlib
import pandas as pd
import streamlit as st
from common import calcular_expiry_date, formatear_expiry_date, normalizar_columna, consolidar, preparar_vista
from file_readers import obtener_nombres_hojas
from exports import generar_excel, boton_copiar_excel
from processing import detectar_proveedor_lote, moneda_predeterminada, procesar_archivos
from providers import PROVEEDORES_CONFIGURADOS, PROVEEDORES_SIN_REGLAS, OPCIONES_PROVEEDORES, REGISTRO
from providers.nexsys import es_catalogo
from ui import iniciar_interfaz, AYUDA_ARCHIVOS, ayuda_proveedor

iniciar_interfaz()
st.title('Price List Normalizer')
st.caption('Ordena tus listas y prepara un único resultado para el CRM.')
modo = st.radio('Tipo de procesamiento', ['Listas de precios', 'Inventario de marca (solo stock)'], horizontal=True,
    help='Listas de precios incluye costos y stock. Inventario de marca prepara resultados separados sin completar precios ausentes. Siempre se excluyen OPEN BOX y BAD BOX.')
if modo == 'Inventario de marca (solo stock)':
    from stock_reader import procesar_stock
    st.info('Resultados separados para Ingram y Compusoluciones. Se conservan las 10 columnas, sin completar precios, moneda, fecha ni otros datos ausentes. Esto no actualiza el CRM automáticamente.')
    inventarios = st.file_uploader('Subir inventarios de marca', type=['xlsx'], accept_multiple_files=True, key='stock_archivos')
    firma_stock = tuple((a.name, hashlib.sha256(a.getvalue()).hexdigest()) for a in inventarios)
    if st.session_state.get('firma_stock') != firma_stock:
        st.session_state['firma_stock'] = firma_stock
        st.session_state.pop('resultado_stock', None)
        for clave in list(st.session_state):
            if clave.startswith('editor_stock_'):
                del st.session_state[clave]
    if st.button('Procesar inventario'):
        if inventarios:
            st.session_state['resultado_stock'] = procesar_stock(inventarios)
        else:
            st.warning('Sube un inventario primero.')
    if 'resultado_stock' in st.session_state:
        resumen_stock, separados = st.session_state['resultado_stock']
        st.dataframe(resumen_stock, hide_index=True)
        for mayorista, datos_stock in separados.items():
            st.subheader(mayorista)
            st.caption('Puedes desmarcar filas para excluirlas. No se suman ni fusionan productos repetidos.')
            if mayorista == 'Compusoluciones':
                st.warning('Esta hoja no informa código del proveedor: provider_code queda vacío. Confirma que el destino admite identificar por PN antes de cargar al CRM.')
            repetidos_stock = datos_stock.duplicated(subset=['provider_code', 'mpn'], keep=False)
            if repetidos_stock.any():
                st.warning('Hay identificadores repetidos. Revisa las filas antes de copiar; no se eligió ni sumó stock automáticamente.')
            revision_stock = datos_stock.copy()
            revision_stock.insert(0, 'Incluir', True)
            elegido_stock = st.data_editor(revision_stock, hide_index=True, disabled=list(datos_stock.columns),
                key='editor_stock_' + mayorista, column_config={'Incluir': st.column_config.CheckboxColumn('Incluir')})
            final_stock = elegido_stock.loc[elegido_stock['Incluir']].drop(columns='Incluir')
            st.write(f'{len(final_stock)} productos seleccionados')
            if not final_stock.empty:
                descarga_stock, copia_stock = st.columns([2, 1])
                with descarga_stock:
                    st.download_button('Descargar inventario de ' + mayorista, generar_excel(final_stock),
                        file_name='Stock ' + mayorista + '.xlsx', key='descarga_stock_' + mayorista)
                with copia_stock:
                    boton_copiar_excel(final_stock)
    st.stop()
st.subheader('1. Agrega tus listas')
archivos = st.file_uploader('Subir listas de precios del mismo proveedor',
                           type=['xlsx', 'xls', 'csv', 'pdf'], accept_multiple_files=True, help=AYUDA_ARCHIVOS)
archivos = list(archivos)
texto_pendiente = False
formato_pegado = None
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
    OPCIONES_PROVEEDORES,
    key='proveedor_lista',
    help=ayuda_proveedor(st.session_state.get('proveedor_lista')),
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
def limpiar_lista_pegada():
    """Limpiar la entrada y su revisión, conservando archivos y formatos aprendidos."""
    st.session_state['texto_ingram'] = ''
    for clave in list(st.session_state):
        if clave.startswith(('revision_texto_', 'esquema_', 'manual_', 'duda_')):
            del st.session_state[clave]
    st.session_state.pop('lote', None)


with st.expander('Pegar lista — cualquier mayorista'):
    texto = st.text_area('Pega la lista con sus encabezados', height=180, key='texto_ingram',
        placeholder='Copia una tabla de Excel, un correo o una lista con encabezados…',
        help='Acepta tablas tabuladas, Markdown o texto vertical. Se combina con los archivos del mismo mayorista. Puedes corregir las columnas antes de procesar; los datos ausentes no se completan.')
    st.button('Limpiar lista pegada', key='limpiar_lista_pegada',
              on_click=limpiar_lista_pegada, disabled=not texto.strip())
    if texto.strip():
        from pasted_lists import interpretar_texto, archivo_mapeado, detectar_columnas, ALIAS
        texto_pendiente = True
        huella = hashlib.sha256((proveedor + texto).encode('utf-8')).hexdigest()
        with st.expander('Corregir columnas'):
            esquema = st.text_input('Solo si falla el texto vertical: encabezados separados por punto y coma', key='esquema_' + huella)
            manual = st.checkbox('Cambiar la asignación detectada', key='manual_' + huella)
        try:
            tabla = interpretar_texto(texto, [c.strip() for c in esquema.split(';') if c.strip()] or None)
            formato = (proveedor, tuple(tabla.columns))
            memoria = st.session_state.setdefault('formatos_pegados', {})
            mapeo, dudas = detectar_columnas(tabla.columns, proveedor)
            if formato in memoria:
                mapeo, dudas = memoria[formato].copy(), {}
            if manual:
                with st.expander('Asignación manual', expanded=True):
                    for destino in ALIAS:
                        opciones = ['Sin dato'] + list(tabla.columns)
                        actual = mapeo.get(destino) or 'Sin dato'
                        valor = st.selectbox('Columna para ' + destino, opciones, index=opciones.index(actual), key='manual_map_' + destino + huella)
                        mapeo[destino] = None if valor == 'Sin dato' else valor
            else:
                for destino, candidatos in dudas.items():
                    opciones = ['Seleccionar...'] + (['Sin dato'] if destino in ('mpn', 'name', 'brand') else []) + candidatos
                    valor = st.selectbox('¿Qué columna usar para ' + destino + '?', opciones, key='duda_' + destino + huella)
                    mapeo[destino] = None if valor in ('Seleccionar...', 'Sin dato') else valor
                    if valor == 'Sin dato':
                        dudas[destino] = []
            st.caption('Detectado: ' + ' · '.join(f'{k}: {v}' for k, v in mapeo.items() if v))
            tabla = st.data_editor(tabla, hide_index=True, num_rows='fixed', key='revision_texto_' + huella)
            pendientes = [k for k, candidatos in dudas.items() if candidatos and not mapeo.get(k)] if not manual else []
            if pendientes:
                st.warning('Resuelve las columnas dudosas antes de procesar. No se eligen precios ni marcas por suposición.')
            else:
                archivo_texto = archivo_mapeado(tabla, mapeo)
                archivos.append(archivo_texto)
                formato_pegado = (formato, mapeo.copy())
                texto_pendiente = False
                st.caption('Lista preparada. Pulsa Procesar listas abajo. Los formatos confirmados se recuerdan durante esta sesión.')
        except ValueError as error:
            st.warning(str(error))
# La detección del proveedor usa solo archivos originales; el texto no altera la selección.
import_hash_archivos = tuple(hashlib.sha256(a.getvalue()).hexdigest() for a in archivos)
if proveedor in PROVEEDORES_SIN_REGLAS:
    st.info(getattr(REGISTRO[proveedor], 'AVISO_PENDIENTE',
        f'{proveedor}: esta opción ya está disponible, pero todavía no tiene reglas '
        'de lectura configuradas. Para evitar inventar o asignar mal datos, necesitamos '
        'revisar una lista de ejemplo antes de habilitar su procesamiento.'
    ))
hojas_por_archivo = {}
seleccion_hojas_incompleta = False
if proveedor == 'Ingram' and archivos:
    st.subheader('Hojas del Excel')
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
            help='Elige una o varias hojas. Solo se procesan las elegidas; no hay nombres ni hojas obligatorias.',
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
    for indice_archivo, archivo in enumerate(archivos):
        if not archivo.name.lower().endswith(('.xlsx', '.xls')):
            continue
        try:
            nombres_hojas = obtener_nombres_hojas(archivo)
            elegidas = st.multiselect(
                f'Hojas a procesar — {archivo.name}', options=nombres_hojas,
                default=nombres_hojas,
                help='Puedes seleccionar varias hojas; se procesarán únicamente las elegidas.',
                key=f'hojas_solutionbox_{indice_archivo}_{import_hash_archivos[indice_archivo]}',
            )
            hojas_por_archivo[indice_archivo] = list(elegidas)
            if not elegidas:
                st.warning('Selecciona al menos una hoja para procesar.')
                seleccion_hojas_incompleta = True
        except Exception as error:
            st.warning(f'No se pudieron leer las hojas de {archivo.name}: {error}')
            seleccion_hojas_incompleta = True
if proveedor == 'Gerona':
    st.warning('Gerona: este catálogo no informa stock; quantity queda vacío, no en cero. Se usa Precio Lista (sin IVA), CodigoSKU como código y Modelo como PN. Confirma que el CRM acepta cantidad vacía antes de cargar.')
catalogo_nexsys = False
if proveedor == 'Nexsys':
    for archivo in archivos:
        if archivo.name.lower().endswith('.xlsx'):
            try:
                catalogo_nexsys = catalogo_nexsys or es_catalogo(obtener_nombres_hojas(archivo))
            except Exception:
                pass  # El procesamiento reportará el error del archivo.
    if catalogo_nexsys:
        st.info('Catálogo Hardware Nexsys: solo hojas autorizadas y productos en USD. Se excluyen EPSON y filas CLP; no se convierten precios. HP Poly incluye promociones y Lenovo limita el stock promocional a sus unidades disponibles. Jabra usa el precio certificado autorizado.')
        st.session_state[f'moneda_lista_{proveedor}'] = 'USD'
st.subheader('2. Revisa moneda y vigencia')
st.session_state.setdefault(f'moneda_lista_{proveedor}', moneda_predeterminada(proveedor))
moneda_valor = st.selectbox(
    'Moneda de la lista', ['USD', 'CLP'],
    key=f'moneda_lista_{proveedor}',
    disabled=catalogo_nexsys,
    help='Se aplica a todos los productos del lote, incluso si el encabezado indica otra moneda. No convierte los importes.',
)
if proveedor == 'Kepler':
    if any('PREVENTA' in normalizar_columna(a.name) for a in archivos):
        st.warning('Lista de preventa: se copiarán las cantidades indicadas en el archivo. No representan stock inmediato y no se asignará un plazo de entrega si no está informado.')
permitir_pn = proveedor == 'Nexsys'  # Equivalencia confirmada por el usuario.
fecha = st.date_input('Fecha de vigencia', value=calcular_expiry_date(),
    help='Por defecto: hoy más 14 días, sin superar el fin de mes. La hora aplicada es 12:00. Puedes cambiar la fecha.')

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

if st.button('Procesar listas', key='procesar_listas', type='primary',
    help='Combina las listas del mayorista seleccionado. Los SKU con diferencias se pueden revisar en el resultado.'):
    if texto_pendiente:
        st.warning('Revisa las columnas dudosas de la lista pegada antes de procesar.')
    elif not archivos:
        st.warning('Primero debes subir una o más listas de precios.')
    elif proveedor == 'Seleccionar...':
        st.warning('Primero debes seleccionar un proveedor.')
    elif not proveedor_confirmado:
        st.warning('Revisa los archivos y confirma que pertenecen al proveedor seleccionado antes de procesar.')
    elif proveedor not in PROVEEDORES_CONFIGURADOS and any(not hasattr(a, 'tabla_pegada') for a in archivos):
        st.warning(
            f'{proveedor} todavía no tiene reglas de procesamiento configuradas. '
            'No se generó ningún resultado.'
        )
    elif seleccion_hojas_incompleta:
        st.warning('Selecciona al menos una hoja válida antes de procesar.')
    else:
        st.session_state['lote'] = procesar_archivos(
            archivos, fecha, proveedor, moneda_valor, permitir_pn,
            hojas_por_archivo=hojas_por_archivo,
        )
        if formato_pegado and not (st.session_state['lote'][0]['Estado'] == 'Error').any():
            formato, mapeo = formato_pegado
            st.session_state['formatos_pegados'][formato] = mapeo

if 'lote' in st.session_state:
    resumen, combinado = st.session_state['lote']
    st.info('Vigencia aplicada: ' + formatear_expiry_date(fecha))
    with st.expander('Detalle por archivo', expanded=(resumen['Estado'] == 'Error').any()):
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
        st.subheader('3. Tu resultado para el CRM')
        st.write(f'{len(final)} productos listos para descargar')
        st.dataframe(preparar_vista(final), hide_index=True)
        if not final.empty and not codigos_repetidos.any():
            col_descarga, col_copiar = st.columns(2)
            with col_descarga:
                st.download_button('Descargar archivo listo para CRM', generar_excel(final),
                    file_name='Directo para cargar al CRM.xlsx',
                    use_container_width=True,
                    help='Descarga las 10 columnas del CRM con encabezados. Los SKU sin resolver quedan fuera.',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            with col_copiar:
                boton_copiar_excel(final)
        elif final.empty:
            st.warning('No quedaron productos sin conflictos para generar el Excel CRM.')
