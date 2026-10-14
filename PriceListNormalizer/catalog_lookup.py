"""Cruce opcional de listas sin SKU contra catálogos privados.

Los catálogos no se guardan en el repositorio. Se configuran mediante
``PRICE_LIST_CATALOG_DIR`` o una variable de entorno específica del proveedor.
"""
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from io import BytesIO
from pathlib import Path

import pandas as pd

CATALOGOS = {
    'Intcomex': ('INTCOMEX',),
    'Ingram': ('INGRAM MICRO', 'INGRAM'),
    'Tecnoglobal': ('TECNOGLOBAL',),
    'Nexsys': ('NEXSYS',),
}
_CATALOGOS_TEMPORALES = ContextVar('catalogos_temporales', default={})


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip().upper()


def _catalog_path(provider):
    key = _norm(provider).replace(" ", "_")
    direct = os.environ.get(f"PRICE_LIST_{key}_CATALOG")
    if direct:
        return Path(direct)
    folder = os.environ.get("PRICE_LIST_CATALOG_DIR")
    if not folder:
        return None
    base = Path(folder)
    for suffix in (".xlsx", ".xls", ".csv"):
        candidate = base / f"{provider}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _validar_catalogo(frame, provider):
    """Valida que una base corresponda al proveedor elegido."""
    frame = frame.fillna("")
    provider_col = next((c for c in ("provider", "PROVIDER") if c in frame.columns), None)
    nombres = {_norm(nombre) for nombre in CATALOGOS.get(provider, (provider,))}
    if provider_col and not frame[provider_col].astype(str).map(_norm).isin(nombres).any():
        return None
    if not any(c in frame.columns for c in ("provider_code", "PROVIDER_CODE")):
        return None
    if not any(c in frame.columns for c in ("mpn", "MPN", "pn", "PN")):
        return None
    return frame


def leer_catalogo_subido(provider, archivo):
    """Lee una base temporal. Solo vive en la sesión actual del usuario."""
    nombre = getattr(archivo, 'name', '').lower()
    contenido = archivo.getvalue() if hasattr(archivo, 'getvalue') else archivo.read()
    try:
        frame = (pd.read_csv(BytesIO(contenido), dtype=str) if nombre.endswith('.csv')
                 else pd.read_excel(BytesIO(contenido), dtype=str))
    except Exception as error:
        raise ValueError('No se pudo leer la base privada de códigos.') from error
    if _validar_catalogo(frame, provider) is None:
        raise ValueError(f'La base no contiene provider_code y PN válidos para {provider}.')
    return frame.fillna("")


@contextmanager
def usar_catalogos_temporales(catalogos):
    """Aísla bases cargadas por una persona durante una sola ejecución."""
    token = _CATALOGOS_TEMPORALES.set(catalogos or {})
    try:
        yield
    finally:
        _CATALOGOS_TEMPORALES.reset(token)


def cargar_catalogo(provider):
    """Carga un catálogo configurado, devolviendo ``None`` si no existe."""
    temporal = _CATALOGOS_TEMPORALES.get().get(provider)
    if temporal is not None:
        return _validar_catalogo(temporal, provider)
    path = _catalog_path(provider)
    explicit = bool(path and path.exists())
    candidates = [path] if explicit else []
    # Permite usar exportaciones con nombres como providers.providerproduct (7).
    # Se valida el proveedor dentro del archivo antes de aceptarlas.
    if not candidates:
        folder = os.environ.get("PRICE_LIST_CATALOG_DIR")
        if folder:
            candidates = sorted(Path(folder).glob("*.xlsx")) + sorted(Path(folder).glob("*.csv"))
    for candidate in candidates:
        try:
            frame = (pd.read_csv(candidate, dtype=str) if candidate.suffix.lower() == ".csv"
                     else pd.read_excel(candidate, dtype=str)).fillna("")
            provider_col = next((c for c in ("provider", "PROVIDER") if c in frame.columns), None)
            if not explicit and not provider_col:
                continue
            validado = _validar_catalogo(frame, provider)
            if validado is not None:
                return validado
        except Exception:
            continue
    return None


def resolver_por_catalogo(tabla, provider):
    """Completa códigos solo con coincidencias exactas y únicas.

    Retorna ``(tabla, pendientes, detalle)``. Las filas sin precio ya deben
    haber sido retiradas antes de llamar a esta función.
    """
    if provider not in CATALOGOS or "provider_code" not in tabla.columns:
        return tabla, [], ""
    catalogo = cargar_catalogo(provider)
    if catalogo is None:
        faltantes = tabla.index[tabla["provider_code"].astype(str).str.strip().eq("")].tolist()
        return tabla, faltantes, f"Catálogo privado de {provider} no configurado; no se inventaron SKU."
    code_col = next((c for c in ("provider_code", "PROVIDER_CODE", "provider code") if c in catalogo.columns), None)
    pn_col = next((c for c in ("mpn", "MPN", "pn", "PN") if c in catalogo.columns), None)
    name_cols = [c for c in ("_name", "name", "product", "_description") if c in catalogo.columns]
    if not code_col or not pn_col:
        raise ValueError(f"El catálogo privado de {provider} debe tener provider_code y mpn.")

    indices = {}
    for _, row in catalogo.iterrows():
        code = str(row.get(code_col, "")).strip()
        if not code:
            continue
        claves = {_norm(row.get(pn_col, ""))}
        claves.update(_norm(row.get(c, "")) for c in name_cols)
        for clave in claves - {""}:
            indices.setdefault(clave, set()).add(code)

    resultado = tabla.copy()
    pendientes = []
    resueltos = 0
    ambiguos = 0
    for idx, row in resultado.iterrows():
        if str(row.get("provider_code", "")).strip():
            continue
        referencias = [str(row.get("mpn", "")).strip(), str(row.get("name", "")).strip()]
        candidatos = set()
        for referencia in referencias:
            candidatos.update(indices.get(_norm(referencia), set()))
        nombre = referencias[-1]
        if not candidatos and nombre:
            # La lista puede usar solo el modelo dentro del nombre comercial.
            for clave, codes in indices.items():
                if len(clave) >= 6 and (clave in _norm(nombre) or _norm(nombre) in clave):
                    candidatos.update(codes)
        if len(candidatos) == 1:
            resultado.at[idx, "provider_code"] = next(iter(candidatos))
            resueltos += 1
        else:
            pendientes.append(idx)
            if len(candidatos) > 1:
                ambiguos += 1
    detalle = f"Catálogo {provider}: {resueltos} SKU completados"
    if ambiguos:
        detalle += f"; {ambiguos} filas con varios códigos quedan pendientes"
    if pendientes and not ambiguos:
        detalle += f"; {len(pendientes)} filas sin coincidencia única quedan pendientes"
    return resultado, pendientes, detalle

