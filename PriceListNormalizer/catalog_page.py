"""Administración de equivalencias de producto sin precios ni stock."""
from io import BytesIO
import pandas as pd
import streamlit as st
from catalog_lookup import CATALOGOS, cargar_catalogo


def mostrar_bases():
    st.subheader('Bases de códigos')
    st.caption('Relaciona el PN con el código del mayorista para procesar listas que solo traen número de parte.')
    proveedor = st.selectbox('Mayorista de la base', list(CATALOGOS), key='base_proveedor')
    actual = st.session_state.get('bases_codigos', {}).get(proveedor)
    if actual is None:
        actual = cargar_catalogo(proveedor)
    st.caption(f'Base disponible: {len(actual):,} equivalencias.' if actual is not None else 'Todavía no hay una base disponible.')
    archivo = st.file_uploader('Subir o actualizar base', type=['xlsx', 'xls', 'csv'], key='base_archivo',
                              help='Incluye PN y código del mayorista. El nombre del producto es opcional.')
    if archivo is None:
        return
    try:
        contenido = BytesIO(archivo.getvalue())
        tabla = (pd.read_csv(contenido, dtype=str, sep=None, engine='python')
                 if archivo.name.lower().endswith('.csv') else pd.read_excel(contenido, dtype=str)).fillna('')
        columnas = list(tabla.columns)
        def indice(alias):
            return next((i for i, c in enumerate(columnas) if str(c).strip().upper() in alias), 0)
        pn = st.selectbox('Columna del PN', columnas, index=indice({'PN', 'MPN', 'PART NUMBER'}))
        codigo = st.selectbox('Columna del código del mayorista', columnas,
                              index=indice({'PROVIDER_CODE', 'SKU', 'CODIGO', 'CÓDIGO'}))
        nombre = st.selectbox('Nombre del producto (opcional)', ['Sin nombre'] + columnas)
        if pn == codigo:
            st.warning('Elige columnas diferentes para PN y código del mayorista.')
            return
        base = pd.DataFrame({'provider': CATALOGOS[proveedor][0],
                             'provider_code': tabla[codigo].str.strip(),
                             'mpn': tabla[pn].str.strip(),
                             '_name': '' if nombre == 'Sin nombre' else tabla[nombre].str.strip()})
        base = base.loc[base['mpn'].ne('') & base['provider_code'].ne('')].drop_duplicates()
        st.write(f'{len(base):,} equivalencias listas')
        st.dataframe(base.head(100), hide_index=True)
        st.caption('Solo se conservan mayorista, PN, código y nombre opcional. Los PN con varios códigos requieren revisión al convertir.')
        if st.button('Usar esta base', type='primary', disabled=base.empty):
            st.session_state.setdefault('bases_codigos', {})[proveedor] = base
            st.session_state.pop('lote', None)
            st.success('Base activa para las conversiones de esta sesión.')
        st.download_button('Descargar base para guardar', base.to_csv(index=False).encode('utf-8-sig'),
                           file_name=f'{proveedor}.csv', mime='text/csv')
        st.link_button('Guardar permanentemente en GitHub',
                       f'https://github.com/alexanderosorio-art/Centrale/upload/main/PriceListNormalizer/catalogs/{proveedor}')
        st.caption('Para conservarla al cerrar la app: descarga el CSV y súbelo en el enlace de GitHub. Usa siempre el mismo nombre para reemplazar la versión anterior. La app pública no permite que otros visitantes sobrescriban tus bases.')
    except Exception as error:
        st.error(f'No se pudo preparar la base: {error}')

