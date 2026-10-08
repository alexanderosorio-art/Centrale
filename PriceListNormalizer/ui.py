"""Presentación y ayudas de la app, sin reglas de procesamiento."""
import streamlit as st

AYUDA_ARCHIVOS = (
    'Puedes subir varios archivos del mismo mayorista: Excel, CSV o PDF. '
    'Los PDF deben contener texto seleccionable; las imágenes escaneadas requieren OCR. '
    'Ingram y SolutionBox permiten seleccionar hojas. Intcomex y Kepler usan la primera hoja; '
    'Facciatech usa Resumen. Los demás proveedores se leen según sus reglas configuradas. '
    'Los productos OPEN BOX y BAD BOX se excluyen. No se inventan datos ausentes.'
)
AYUDA_PROVEEDORES = {
    'Intcomex': 'Se reconocen también archivos identificados como IX. Se usa el SKU de Intcomex, no el PN como reemplazo.',
    'Ingram': 'También identificado como IM. Elige una o varias hojas; ningún nombre de hoja es obligatorio. PN y SKU no se consideran equivalentes.',
    'Tecnoglobal': 'También identificado como TG. En el formato de componentes se usa Precio Volumen, según tu regla confirmada.',
    'Facciatech': 'Solo hoja Resumen. Precio Neto detalle, no precio por mayor. ID como código y Part Number como PN. CLP por defecto.',
    'Demco Ltda.': 'Se revisan todas las hojas. Código Interno como código, Número de Parte como PN y Precio Neto como costo. CLP por defecto.',
    'Gtc ribbon': 'Código GTC y Part Number cuando exista. EAN no reemplaza PN. Se ignoran ofertas condicionadas a volumen. Marca solo desde una columna explícita.',
    'SolutionBox': 'El PN se usa como código y mpn en las plantillas configuradas. Marca solo desde MARCA. Se excluyen productos por encargo o sin cantidad disponible.',
    'Kepler': 'Se usa el precio normal. PN y código son equivalentes según la regla confirmada. Las preventas se identifican con una advertencia.',
    'Nexsys': 'PN y código son equivalentes según la regla confirmada. El catálogo Hardware usa solo hojas autorizadas y productos USD; no convierte importes CLP.',
    'Gerona': 'Precio Lista sin IVA, CodigoSKU como código y Modelo como PN. Stock ausente queda vacío. CLP por defecto.',
    'Coimco': 'Se revisan las hojas compatibles y cantidades con +. CLP por defecto.',
    'Fujicorp': 'Se consideran precios especiales según las reglas del proveedor. CLP por defecto. No se deduce marca desde títulos de hojas.',
    'Otro': 'Puedes pegar una tabla y revisar sus columnas. Los archivos requieren reglas de lectura configuradas.',
}


def iniciar_interfaz():
    st.set_page_config(page_title='Price List Normalizer', page_icon='📋', layout='centered')
    st.markdown('''<style>
    .stApp { background: #0b0d11; color: #f1f0ec; }
    [data-testid="stHeader"] { background: #0b0d11; }
    .block-container { max-width: 1080px; padding-top: 2.5rem; padding-bottom: 4rem; }
    h1, h2, h3 { font-family: Jost, "Trebuchet MS", sans-serif; font-weight: 500; }
    h1 { letter-spacing: -.025em; }
    [data-testid="stCaptionContainer"] { color: #a4adbb; }
    [data-testid="stExpander"] { border-color: #273142; border-radius: 14px; }
    [data-testid="stFileUploaderDropzone"] { background: #161e2a; border-radius: 14px; }
    .stButton button, .stDownloadButton button { border-radius: 10px; min-height: 44px; }
    .stButton button:focus-visible, .stDownloadButton button:focus-visible {
        outline: 2px solid #a9c3ea; outline-offset: 3px;
    }
    .pln-brand { width: 64px; height: 2px; background: #a8834a; margin: 0 0 18px; }
    @media (max-width: 640px) { .block-container { padding-top: 1.5rem; padding-inline: 1rem; } }
    </style>''', unsafe_allow_html=True)
    st.markdown('<div class="pln-brand" aria-hidden="true"></div>', unsafe_allow_html=True)


def ayuda_proveedor(proveedor):
    base = 'El mayorista puede detectarse por el nombre del archivo. Puedes corregirlo aquí. '
    return base + AYUDA_PROVEEDORES.get(proveedor, 'Elige el mayorista de todas las listas que vas a combinar.')
