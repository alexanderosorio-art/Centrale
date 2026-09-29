# Price List Normalizer — estructura del código

La interfaz y las reglas de lectura están separadas. Esta reorganización conserva
los mapeos, filtros, monedas y formatos existentes; no deduce datos nuevos.

```text
app.py                 Interfaz Streamlit y revisión de duplicados
providers/             Un módulo por mayorista
  __init__.py          Registro y orden de los proveedores
  intcomex.py          Lista estándar, ASUS Business y WD
  kepler.py            Plantillas Kepler y aviso de preventa
  ingram.py            Encabezados y lectura de hojas seleccionadas
  tecnoglobal.py       Reglas Tecnoglobal
  coimco.py            Reglas Coimco
  fujicorp.py          Reglas Fujicorp y selección de ofertas
  nexsys.py            Reglas Nexsys y confirmación de PN como código
  solutionbox.py       Plantillas SolutionBox y disponibilidad
  demco.py             Código Interno, Precio Neto y stock numérico
  facciatech.py         Pendiente de configurar
  gtc_ribbon.py         Pendiente de configurar
  otro.py              Pendiente de configurar
table_reader.py        Motor de tablas configurado por cada proveedor
file_readers.py        Lectura de archivos, encabezados y límites de Excel
common.py              Limpieza, fechas, esquema CRM y duplicados
processing.py          Lotes, detección por nombre y resumen de errores
exports.py             Descarga Excel y copiado para Excel
tests/                 Pruebas sintéticas sin información comercial privada
```

## Agregar o corregir un mayorista

1. Modificar únicamente su módulo dentro de `providers/` cuando la regla sea
   específica de ese mayorista. Los módulos no se importan entre sí.
2. Para uno nuevo, exponer `NOMBRE`, `PATRON` (regex del nombre de archivo),
   `MONEDA` (valor predeterminado) y la función:
   `leer(archivo, fecha, moneda, permitir_pn=False, hojas_seleccionadas=None)`.
3. `leer` devuelve `(dataframe_crm, filas_leidas, detalle)`. Puede reutilizar
   `ReglasTabla` y `leer_tablas`, o implementar un lector propio. La función
   `normalizar_productos` recibe el esquema intermedio histórico
   `SKU`, `venta neto usd`, `stock actual`; los encabezados del archivo real
   deben mapearse en el proveedor antes de llamar a esa función.
4. Registrar el módulo en `providers/__init__.py` y su posición en el selector.
   Si todavía no hay una lista revisada, usar `leer = None` para impedir que se
   procesen datos con reglas supuestas.
5. Agregar pruebas con archivos sintéticos. No subir listas de proveedores,
   credenciales ni datos del CRM al repositorio público.

Las fechas, el portapapeles y los filtros comunes se mantienen en un solo lugar.
La moneda elegida por el usuario se aplica en `processing.py` sin convertir precios.
La interfaz conserva sus avisos y controles particulares de hojas y confirmaciones.

## Ejecutar y verificar

Desde la raíz del repositorio:

```powershell
python -m streamlit run PriceListNormalizer/app.py
python -m unittest discover -s PriceListNormalizer/tests -v
```

El archivo de entrada en Streamlit Community Cloud sigue siendo
`PriceListNormalizer/app.py`. No cambian las dependencias ni la URL.
