"""Exportación Excel y portapapeles, independiente del proveedor."""
import pandas as pd
import re
import json
from datetime import datetime
from io import BytesIO
from html import escape
import streamlit.components.v1 as components

def generar_excel(df):
    buffer = BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Lista"
        )

        hoja = writer.book["Lista"]

        # Columna D = expiry_date: texto con prefijo de apóstrofe de Excel.
        for celda in hoja["D"][1:]:
            celda.number_format = "@"
            celda.quotePrefix = True
        hoja.column_dimensions["D"].width = 23

    buffer.seek(0)

    return buffer


def formatear_datos_copia(df):
    """Formatea solo las filas de datos para el portapapeles de Excel."""
    datos = df.copy()
    columnas_numericas = {
        'currency_unaware_cost_neto', 'quantity', 'condition',
        'working_days_to_deliver'
    }

    def formatear(columna, valor):
        if pd.isna(valor):
            return ''
        if columna == 'expiry_date':
            if isinstance(valor, datetime):
                fecha = valor
            else:
                texto_fecha = re.sub(r'\s+', ' ', str(valor).strip().lstrip("'"))
                fecha = None
                for formato in (
                    '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M',
                    '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
                    '%d-%m-%Y', '%Y-%m-%d',
                ):
                    try:
                        fecha = datetime.strptime(texto_fecha, formato)
                        break
                    except ValueError:
                        continue
            if fecha is not None:
                return fecha.strftime('%d-%m-%Y  %H:%M')
            return str(valor).strip().lstrip("'")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if float(valor).is_integer():
                return str(int(valor))
        texto = str(valor).strip()
        if columna in columnas_numericas and re.fullmatch(r'[+-]?\d+\.0+', texto):
            return texto.split('.', 1)[0]
        if (
            columna == 'currency_unaware_cost_neto'
            and re.fullmatch(r'[+-]?\d+\.\d+', texto)
        ):
            # El Excel del usuario usa coma decimal. Un punto seguido por muchos
            # dígitos se interpreta al pegar como separador de miles.
            return texto.replace('.', ',')
        return texto

    for columna in datos.columns:
        datos[columna] = datos[columna].map(
            lambda valor: formatear(columna, valor)
        )

    return datos


def generar_tsv(df):
    """Genera texto tabulado sin encabezados y sin apóstrofe visible."""
    datos = formatear_datos_copia(df)

    return datos.to_csv(
        sep="\t",
        index=False,
        header=False,
        lineterminator="\n",
        na_rep="",
    )


def generar_html_copia_excel(df):
    """Copia fechas con el prefijo de texto interno de Excel."""
    datos = formatear_datos_copia(df)
    filas = []
    for valores in datos.itertuples(index=False, name=None):
        celdas = []
        for columna, valor in zip(datos.columns, valores):
            contenido = escape(str(valor))
            if columna == 'expiry_date':
                # x:str pasa el apóstrofe como prefijo de Excel, no como texto
                # visible. El contenido de la celda conserva solo la fecha.
                valor_excel = escape("'" + str(valor), quote=True) if valor else ''
                celdas.append(
                    f'<td x:str="{valor_excel}"><pre style="margin:0; font-family:inherit">{contenido}</pre></td>'
                )
            else:
                celdas.append(f'<td>{contenido}</td>')
        filas.append('<tr>' + ''.join(celdas) + '</tr>')
    return '<html xmlns:x="urn:schemas-microsoft-com:office:excel"><head><meta charset="utf-8"></head><body><table xmlns:x="urn:schemas-microsoft-com:office:excel"><tbody>' + ''.join(filas) + '</tbody></table></body></html>'


def boton_copiar_excel(df):
    html = json.dumps(generar_html_copia_excel(df), ensure_ascii=False).replace("</", "<\\/")
    components.html(
        f"""
        <button id="copiar-excel" type="button" style="
            width:100%; min-height:42px; padding:0.4rem 0.75rem;
            border:1px solid rgba(250,250,250,.2); border-radius:.5rem;
            background:#262730; color:#fafafa; font:inherit; cursor:pointer;
        ">Copiar para Excel</button>
        <script>
            const html = {html};
            const boton = document.getElementById('copiar-excel');
            function copiarHtmlAlternativo() {{
                const bloque = document.createElement('div');
                bloque.innerHTML = html;
                bloque.contentEditable = 'true';
                bloque.style.position = 'fixed';
                bloque.style.left = '-10000px';
                document.body.appendChild(bloque);
                const rango = document.createRange();
                rango.selectNodeContents(bloque);
                const seleccion = window.getSelection();
                seleccion.removeAllRanges();
                seleccion.addRange(rango);
                const copiado = document.execCommand('copy');
                seleccion.removeAllRanges();
                bloque.remove();
                return copiado;
            }}
            boton.addEventListener('click', async () => {{
                try {{
                    if (navigator.clipboard.write && window.ClipboardItem) {{
                        const contenido = new ClipboardItem({{
                            'text/html': new Blob([html], {{ type: 'text/html' }})
                        }});
                        await navigator.clipboard.write([contenido]);
                    }} else {{
                        if (!copiarHtmlAlternativo()) throw new Error('HTML clipboard unavailable');
                    }}
                }} catch (error) {{
                    try {{
                        if (!copiarHtmlAlternativo()) throw new Error('HTML clipboard unavailable');
                    }} catch (errorAlternativo) {{
                        boton.textContent = 'Error: descarga el Excel';
                        setTimeout(() => boton.textContent = 'Copiar para Excel', 3500);
                        return;
                    }}
                }}
                boton.textContent = '¡Copiado!';
                setTimeout(() => boton.textContent = 'Copiar para Excel', 2000);
            }});
        </script>
        """,
        height=50,
    )
