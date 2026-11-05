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
               'Inventario de marca con P.Lista', 'Aruba Precios Referenciales'],
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


def mostrar_estadisticas():
    st.subheader('Estadísticas')
    historial = pd.DataFrame(st.session_state.get('historial_procesos', []))
    correctos = historial.loc[historial['Estado'].eq('Procesado')] if not historial.empty else historial
    a, b, c = st.columns(3)
    a.metric('Listas procesadas en esta sesión', len(correctos))
    b.metric('Familias de formatos reconocidas', sum(map(len, FORMATOS.values())))
    c.metric('Mayoristas compatibles', len(FORMATOS))
    st.caption('Una lista corresponde a un archivo procesado correctamente. Reprocesar un archivo cuenta otra vez. El historial se conserva durante esta sesión; no existe un total histórico anterior registrado.')
    st.subheader('Formatos por mayorista')
    st.caption('Catálogo de familias implementadas, no de archivos probados ni garantía de cualquier diseño. Variantes de encabezados de una misma familia cuentan como un solo formato.')
    st.dataframe(pd.DataFrame([{'Mayorista': p, 'Tipos de lista': len(tipos),
                               'Formatos': ' · '.join(tipos)} for p, tipos in FORMATOS.items()]),
                 hide_index=True, use_container_width=True)
    st.subheader('Historial de esta sesión')
    if historial.empty:
        st.info('Procesa una lista para comenzar el conteo.')
    else:
        st.dataframe(historial, hide_index=True)
        st.download_button('Descargar historial CSV', historial.to_csv(index=False).encode('utf-8-sig'),
                           file_name='Historial de procesos.csv', mime='text/csv')

