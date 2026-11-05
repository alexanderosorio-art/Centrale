"""Historial permanente mediante REST; credenciales solo en el servidor."""
import json
import os
from urllib.request import Request, urlopen
from uuid import uuid4
from datetime import datetime, timezone
import streamlit as st


def configuracion():
    def valor(nombre):
        if os.environ.get(nombre):
            return os.environ[nombre]
        try:
            return st.secrets.get(nombre, '')
        except FileNotFoundError:
            return ''
    # Clave publicable: solo permite leer contadores y añadir eventos bajo RLS.
    # No es una clave de administración ni permite borrar/modificar el historial.
    return (valor('USAGE_SUPABASE_URL') or 'https://tbsyzttmuvbflorzgtfe.supabase.co',
            valor('USAGE_SUPABASE_KEY') or 'sb_publishable_4Xcn4Cmywdlktk0MXtAg-w_3nJi7Hle')


def disponible():
    return all(configuracion())


def solicitud(metodo, ruta, datos=None):
    url, clave = configuracion()
    if not url or not clave:
        raise RuntimeError('Historial permanente pendiente de conexión.')
    contenido = json.dumps(datos).encode('utf-8') if datos is not None else None
    headers = {
                      'apikey': clave,
                      'Content-Type': 'application/json',
                      'Prefer': 'resolution=ignore-duplicates,return=minimal',
                  }
    if not clave.startswith('sb_publishable_'):
        headers['Authorization'] = 'Bearer ' + clave
    req = Request(url.rstrip('/') + '/rest/v1/usage_events' + ruta,
                  data=contenido, method=metodo, headers=headers)
    with urlopen(req, timeout=10) as respuesta:
        cuerpo = respuesta.read()
    return json.loads(cuerpo) if cuerpo else None


def crear_eventos(resumen, proveedor):
    ahora = datetime.now(timezone.utc).isoformat()
    # Solo contadores: no se registran nombres de archivo, PN, precios ni usuarios.
    return [{'id': str(uuid4()), 'created_at': ahora, 'provider': proveedor,
             'status': str(fila['Estado']), 'rows_read': int(fila.get('Leídos', 0)),
             'rows_valid': int(fila.get('Válidos', 0)),
             'rows_discarded': int(fila.get('Descartados', 0))}
            for fila in resumen.to_dict('records')]


def guardar_eventos(eventos):
    solicitud('POST', '?on_conflict=id', eventos)


def leer_historial():
    registros = []
    offset = 0
    while True:
        pagina = solicitud('GET', f'?select=*&order=created_at.desc,id.asc&limit=1000&offset={offset}')
        registros.extend(pagina)
        if len(pagina) < 1000:
            break
        offset += len(pagina)
    return registros

