"""Normalización compartida: no contiene reglas de proveedores."""
import pandas as pd
from datetime import datetime, time, timedelta
from calendar import monthrange

def calcular_expiry_date():
    hoy = datetime.now().date()

    fecha_objetivo = hoy + timedelta(days=14)

    ultimo_dia = monthrange(
        hoy.year,
        hoy.month
    )[1]

    fin_de_mes = hoy.replace(
        day=ultimo_dia
    )

    if fecha_objetivo > fin_de_mes:
        return fin_de_mes

    return fecha_objetivo


def convertir_expiry_date(fecha):
    return datetime.combine(fecha, time(hour=12))


def formatear_expiry_date(fecha):
    return convertir_expiry_date(fecha).strftime("%d-%m-%Y  %H:%M")


def limpiar_numero(valor):
    if pd.isna(valor):
        return None
    if not isinstance(valor, str):
        return valor

    texto = valor.strip()
    negativo = texto.startswith("(") and texto.endswith(")")
    texto = texto.replace("(", "").replace(")", "")
    texto = (
        texto.replace("$", "")
        .replace("USD", "")
        .replace("usd", "")
        .replace("US$", "")
        .replace("+", "")
        .replace(" ", "")
    )
    texto = "".join(c for c in texto if c.isdigit() or c in ",.-")
    entero_con_sufijo = texto.endswith(".-") or texto.endswith(",-")
    if entero_con_sufijo:
        texto = texto[:-2]
        texto = texto.replace(".", "").replace(",", "")

    if not entero_con_sufijo and "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif not entero_con_sufijo and "," in texto:
        decimales = len(texto.rsplit(",", 1)[1])
        texto = texto.replace(",", "" if decimales == 3 else ".")

    if negativo:
        texto = "-" + texto
    return pd.to_numeric(texto, errors="coerce")


def normalizar_productos(df, expiry_date):
    df = df.copy()
    df.columns = [str(columna).strip().lower() for columna in df.columns]
    resultado = pd.DataFrame()

    # Esquema intermedio común (cada proveedor mapea sus columnas antes).
    resultado["provider_code"] = df["sku"]

    resultado["currency_unaware_cost_neto"] = (
        df["venta neto usd"]
    )

    resultado["currency"] = "USD"

    resultado["expiry_date"] = (
        formatear_expiry_date(expiry_date)
    )

    resultado["quantity"] = (
        df["stock actual"]
    )

    # Columnas adicionales requeridas por la estructura CRM
    resultado["mpn"] = ""
    resultado["brand"] = ""
    resultado["name"] = ""
    resultado["condition"] = 0
    resultado["working_days_to_deliver"] = ""

    # Limpiar provider_code
    resultado["provider_code"] = (
        resultado["provider_code"]
        .astype(str)
        .str.strip()
    )

    # Limpiar stock
    resultado["quantity"] = resultado["quantity"].map(limpiar_numero)

    # Limpiar precio
    resultado["currency_unaware_cost_neto"] = (
        resultado["currency_unaware_cost_neto"].map(limpiar_numero)
    )

    # Eliminar stock inválido
    resultado = resultado[
        resultado["quantity"] > 0
    ]

    # Eliminar códigos inválidos
    resultado = resultado[
        resultado["provider_code"].notna()
        & (resultado["provider_code"] != "")
        & (resultado["provider_code"] != "nan")
    ]

    # Eliminar precios inválidos
    resultado = resultado[
        resultado["currency_unaware_cost_neto"].notna()
        & (
            resultado["currency_unaware_cost_neto"] > 0
        )
    ]

    # Orden exacto de columnas CRM
    columnas_crm = [
        "provider_code",
        "currency_unaware_cost_neto",
        "currency",
        "expiry_date",
        "quantity",
        "mpn",
        "brand",
        "name",
        "condition",
        "working_days_to_deliver"
    ]

    resultado = resultado[
        columnas_crm
    ]

    return resultado


def normalizar_columna(valor):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD', str(valor)) if not unicodedata.combining(c)).strip().upper()


def normalizar_texto_columna(valor):
    return ' '.join(normalizar_columna(valor).split())


def consolidar(combinado):
    if combinado.empty:
        return combinado.copy(), combinado.copy(), 0
    columnas = [c for c in combinado.columns if c != 'Archivo de origen']
    unicos = combinado.drop_duplicates(subset=columnas).copy()
    repetidos = len(combinado) - len(unicos)
    conflicto = unicos['provider_code'].duplicated(keep=False)
    return unicos.loc[~conflicto].copy(), unicos.loc[conflicto].copy(), repetidos


def preparar_vista(df):
    vista = df.copy()
    if (
        "expiry_date" in vista.columns
        and pd.api.types.is_datetime64_any_dtype(vista["expiry_date"])
    ):
        vista["expiry_date"] = pd.to_datetime(
            vista["expiry_date"], errors="coerce"
        ).dt.strftime("%d-%m-%Y  %H:%M")
    return vista
