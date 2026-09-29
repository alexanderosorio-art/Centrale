"""Interfaz Streamlit. Reglas de mayoristas en providers/."""
import hashlib
import pandas as pd
import streamlit as st
from common import calcular_expiry_date, formatear_expiry_date, normalizar_columna, consolidar, preparar_vista
from file_readers import obtener_nombres_hojas
from exports import generar_excel, boton_copiar_excel
from processing import detectar_proveedor_lote, moneda_predeterminada, procesar_archivos
from providers import PROVEEDORES_CONFIGURADOS, PROVEEDORES_SIN_REGLAS, OPCIONES_PROVEEDORES

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
    OPCIONES_PROVEEDORES,
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
st.caption('Puedes seleccionar varios archivos. PDF: se recorren todas las páginas y se extraen tablas con texto seleccionable. Los PDF escaneados requieren OCR. Tecnoglobal, Nexsys, Ingram, Coimco y Fujicorp: se revisan las hojas elegidas. Intcomex y Kepler: primera hoja. '
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
    st.caption('Kepler: se usa el precio normal de la lista.')
    if any('PREVENTA' in normalizar_columna(a.name) for a in archivos):
        st.warning('Lista de preventa: se copiarán las cantidades indicadas en el archivo. No representan stock inmediato y no se asignará un plazo de entrega si no está informado.')
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
