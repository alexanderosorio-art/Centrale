"""Estadísticas de sesión y catálogo explícito de familias de plantillas."""
from datetime import datetime
import pandas as pd
import streamlit as st

FORMATOS = {
    'Intcomex': ['Tabla estándar', 'ASUS Business', 'WD Centrale', 'Hikvision',
                'Precios Top', 'HPE Gen11/Gen12', 'Dell', 'HP semanal', 'Logitech CSV',
                'Clientes Estratégicos con Product ID', 'Clientes Estratégicos con SKU (WD/AMD/Sandisk)',
                'Forza Disponible', 'Nexxt Disponible', 'HONOR aportes'],
    'Ingram': ['Tabla estándar con SKU', 'Stock y tránsitos', 'PN/QTY/Precio y consolidado',
               'Inventario de marca con P.Lista', 'Aruba Precios Referenciales', 'Lenovo normal/oferta y Consumo CLP'],
    'Tecnoglobal': ['Tabla estándar y cruce por PN', 'Componentes Precio Volumen', 'Linksys', 'Cyber'],
    'Fujicorp': ['Catálogo con ofertas (Precio/PMIN)', 'ACER llegada'],
    'Coimco': ['Catálogo con stock y precios'],
    'Kepler': ['Tabla estándar', 'Preventa TT'],
    'Nexsys': ['Tabla estándar y cruce por PN', 'Catálogo Hardware multihoja'],
    'SolutionBox': ['Lista de precios'],
    'Demco Ltda.': ['Planilla de precios netos'],
    'Gerona': ['Catálogo sin stock'],
    'Facciatech': ['Resumen Precio Neto detalle'],
    'Gtc ribbon': ['Ofertas con condiciones de volumen'],
    'Compu Soluciones': ['Lista distribuidor y descuento', 'Inventario BenQ Precio Oferta'],
}


def registrar_proceso(resumen, proveedor):
    historial = st.session_state.setdefault('historial_procesos', [])
    ahora = datetime.now().isoformat(timespec='seconds')
    for fila in resumen.to_dict('records'):
        historial.append({'Fecha': ahora, 'Mayorista': proveedor, **fila})
    from usage_history import disponible, crear_eventos, guardar_eventos
    if disponible():
        eventos = crear_eventos(resumen, proveedor)
        try:
            guardar_eventos(eventos)
        except Exception:
            st.session_state.setdefault('eventos_uso_pendientes', []).extend(eventos)
            st.warning('La conversión terminó, pero el historial permanente no se pudo guardar. Puedes reintentar desde Estadísticas.')


def mostrar_estadisticas():
    st.subheader('Estadísticas')
    historial = pd.DataFrame(st.session_state.get('historial_procesos', []))
    from usage_history import disponible, leer_historial, guardar_eventos
    permanente = False
    if disponible():
        pendientes = st.session_state.get('eventos_uso_pendientes', [])
        if pendientes and st.button('Reintentar guardar estadísticas pendientes'):
            try:
                guardar_eventos(pendientes)
                st.session_state['eventos_uso_pendientes'] = []
                st.success('Estadísticas guardadas.')
            except Exception:
                st.warning('No se pudo conectar. Los eventos siguen pendientes en esta sesión.')
        try:
            registros = leer_historial()
            historial = pd.DataFrame(registros).rename(columns={
                'created_at': 'Fecha', 'provider': 'Mayorista', 'status': 'Estado',
                'rows_read': 'Leídos', 'rows_valid': 'Válidos', 'rows_discarded': 'Descartados'})
            historial = historial.drop(columns='id', errors='ignore')
            permanente = True
        except Exception:
            st.warning('El historial permanente no está disponible ahora. Se muestra solo esta sesión.')
    else:
        st.info('Historial permanente pendiente de conexión. Por ahora se muestra el uso de esta sesión.')
    correctos = historial.loc[historial['Estado'].eq('Procesado')] if not historial.empty else historial
    a, b, c = st.columns(3)
    a.metric('Listas procesadas históricas' if permanente else 'Listas procesadas en esta sesión', len(correctos))
    b.metric('Familias de formatos reconocidas', sum(map(len, FORMATOS.values())))
    c.metric('Mayoristas compatibles', len(FORMATOS))
    st.caption('Una lista corresponde a un archivo procesado correctamente. Reprocesar cuenta otra vez. ' +
               ('Se incluye el uso de todos los visitantes desde la activación del historial permanente.' if permanente else
                'El historial actual se conserva durante esta sesión.'))
    if permanente and not historial.empty:
        fechas = pd.to_datetime(historial['Fecha'], utc=True).dt.tz_convert('America/Santiago')
        historial['Fecha'] = fechas.dt.strftime('%Y-%m-%d %H:%M:%S')
        mensual = historial.assign(Mes=fechas.dt.strftime('%Y-%m'))
        st.subheader('Uso por mes')
        st.bar_chart(mensual.groupby('Mes').size().rename('Archivos intentados'))
        st.subheader('Uso por mayorista')
        st.dataframe(historial.groupby(['Mayorista', 'Estado']).size().reset_index(name='Archivos'), hide_index=True)
    st.subheader('Formatos por mayorista')
    st.caption('Catálogo de familias implementadas, no de archivos probados ni garantía de cualquier diseño. Variantes de encabezados de una misma familia cuentan como un solo formato.')
    st.dataframe(pd.DataFrame([{'Mayorista': p, 'Tipos de lista': len(tipos),
                               'Formatos': ' · '.join(tipos)} for p, tipos in FORMATOS.items()]),
                 hide_index=True, use_container_width=True)
    st.subheader('Historial permanente' if permanente else 'Historial de esta sesión')
    if historial.empty:
        st.info('Procesa una lista para comenzar el conteo.')
    else:
        st.dataframe(historial, hide_index=True)
        st.download_button('Descargar historial CSV', historial.to_csv(index=False).encode('utf-8-sig'),
                           file_name='Historial de procesos.csv', mime='text/csv')

