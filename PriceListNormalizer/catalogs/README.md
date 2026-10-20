# Bases públicas de códigos

Estas bases sirven para recuperar `provider_code` cuando una lista de precios
trae PN o nombre, pero no el código del mayorista.

Cada proveedor usa su carpeta y uno o más archivos CSV. Las únicas columnas
permitidas son:

```text
provider,provider_code,mpn,_name
```

- `provider`: nombre del proveedor, por ejemplo `INGRAM MICRO`.
- `provider_code`: código oficial del mayorista.
- `mpn`: número de parte.
- `_name`: nombre opcional para ayudar a encontrar coincidencias.

No agregar precios, stock, clientes, imágenes ni otros datos comerciales.
Para actualizar una base, reemplaza o agrega un CSV dentro de la carpeta del
proveedor. Si un PN tiene más de un código, la aplicación no elige uno: lo deja
pendiente para revisión. Usa `plantilla.csv` como punto de partida.

