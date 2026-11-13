# Importar los productos del Excel

Pasa la **lista de productos** del Excel de costos (hoja `Marroquineria1`, filas 22 a 347) a la tabla `producto` de la base. No importa precios, costos ni cotizaciones: solo los productos, con su modelo, cuero, color y notas.

El Excel se trata como dato no confiable: `openpyxl` no es dependencia del backend, se pasa con `--with`, y el script lo usa solo para leer.

## Probar sin escribir (dry-run, es lo que hace por defecto)

```bash
uv run --with openpyxl python -I backend/scripts/importar_productos.py "/ruta/COSTOS1 en vigencia al 01-09-2026.xlsx"
```

Lee el Excel e imprime el resumen. Sin `DATABASE_URL` dice **"sin verificar contra la base"** (no sabe cuántos se crearían ni cuáles no tienen modelo). Con `DATABASE_URL` (desde `backend/`) también cuenta contra la base, pero igual **no escribe**.

## Escribir en staging

```bash
cd backend
DATABASE_URL=... uv run --with openpyxl python -I scripts/importar_productos.py "/ruta/COSTOS1 ....xlsx" \
  --entorno staging --confirmar
```

- Hacen falta **los dos avisos juntos**. Con uno solo, se rechaza.
- `--entorno` acepta exactamente `staging` o `production` (en minúsculas, cualquier otro valor se rechaza).
- Regla de coincidencia: si existe `RAILWAY_ENVIRONMENT_NAME`, tiene que ser **igual** al valor de `--entorno`. Si no coincide, se rechaza antes de conectarse a la base y sin mostrar el valor.
- Sin `RAILWAY_ENVIRONMENT_NAME` (corrida local) solo se acepta `--entorno staging`; `--entorno production` se rechaza.
- Nunca imprime la URL ni las credenciales. El resumen final nombra el entorno solo si lo pasaste vos con `--entorno`.
- Nada se borra ni se actualiza: solo se agregan productos (y el color `Arena` si no existe).

## Escribir en production

Solo se escribe **desde dentro del contenedor de production**, nunca desde tu máquina. Antes de correr:

1. Tener un **backup verificado** de la base de production.
2. Verificar que `alembic current` da `0007_proveedores_documentos` (0007).

```bash
railway ssh -e production -s backend
# ya adentro del contenedor, desde backend/:
uv run --with openpyxl python -I scripts/importar_productos.py "/ruta/COSTOS1 ....xlsx" \
  --entorno production --confirmar
```

- `--entorno production` dentro de un contenedor de staging (o `--entorno staging` dentro de uno de production) se rechaza siempre.
- En production las filas entran igual que en staging, con sus marcas `REVISAR` (ver más abajo).

## Qué hace con cada fila

- Un producto por fila con nombre. Lo enlaza a su `modelo` por `modelo.fila_excel_viejo` = fila del Excel. **Si la fila no tiene modelo en la base, no se crea** y queda en el resumen como "sin modelo" (hoy: la fila 94, que no tiene nombre y cuyo modelo 1915 no está en el seed).
- `nombre_propio` = texto de la columna F con `strip()`, sin corregir nada.
- Cuero según la columna H (1 → `MAT-CU01` … 6 → `MAT-CU06`). Color: solo si el texto del cuero termina en `- C <Color>)` (hoy `Arena`); si no, queda vacío. Si el color no existe se crea.
- Estado `EN_DEFINICION`, `es_kit = false`, `quien_lo_confecciona` y `fecha_de_alta` vacíos (la columna E parece fecha de cotización: **supuesto, validar con Gerardo**).
- Todo pasa por `servicios.crear_producto` (el código `PRD-nnnn` lo asigna ese servicio).
- **Se puede correr dos veces**: cada producto lleva `IMPORTADO-EXCEL fila <N>` en la nota y la segunda corrida lo saltea.

## La `nota` del producto

Texto separado por ` | `, en este orden: `IMPORTADO-EXCEL fila <N>`, marcas `REVISAR`, columnas sin encabezado `B=`, `D=`, `C=` (solo si tienen valor), `E=<fecha>` y los comentarios de celda (`Comentario AE53: ...`). Son **notas de texto, nunca precios vigentes**: los comentarios son pagos a talleres de 2016-2017.

## Marcas `REVISAR`

| Marca | Cuándo | Qué hacer |
|---|---|---|
| `error en origen (<columnas>)` | Alguna celda A:AI de la fila dice `#VALUE!`, `#REF!`, etc. | Revisar la fila en el Excel. |
| `sin nombre` | La columna F está vacía (fila 94). | Preguntar a Gerardo qué producto es. |
| `cuero <lagarto o yacaré> no cotizable (pendiente Gerardo)` | Cuero 3 o 4: están en USD por cm y bloqueados. El producto se crea **sin cuero**. | Esperar la regla de Gerardo. |
| `sin tipo de cuero` | H vacío o con error. Cuero vacío. | Elegir el cuero a mano. |
| `tipo de cuero desconocido (<valor>)` | H tiene un valor fuera de 1 a 6. Cuero vacío. | Revisar la fila. |
| `modelo repetido` | El código de modelo (columna G) aparece más de una vez (514, 739, 915, 1525, 1729, 2296, 2413, 2493, 2509, 2670). | Que Gerardo decida si es el mismo modelo. |
| `posible kit o costeo por varias unidades` | El nombre tiene "Kit" o "costo x" (filas 298 y 310). No se arman componentes. | Decidir si es un kit. |

## El resumen que imprime

Filas leídas y con nombre, productos por cuero y por color, filas `REVISAR` por motivo (una fila puede tener varios), cuero vacío por motivo, modelos repetidos, y (con base) cuántos se crean, cuántos ya existían y cuáles no tienen modelo.

## Datos de demo de staging (`cargar_demo.py`)

No importa nada del Excel: completa la demo de staging con datos **ficticios** para ver la interfaz final. Se corre **después** de `cargar_ejemplo.py` (usa sus productos `EJEMPLO producto 1` a `8` y los talleres del seed; lo que no encuentra lo saltea y lo avisa) y **después** de `recortar_staging.py`, que borra todos los formularios de consumos.

```sh
# desde el checkout principal, solo con autorización de Agustin (la ruta /app sale de docs/produccion.md; sin verificar)
railway ssh -e staging -s backend -- sh -c 'cd /app && test "$RAILWAY_ENVIRONMENT_NAME" = staging && /app/.venv/bin/python scripts/cargar_demo.py --entorno staging'              # solo muestra qué crearía
railway ssh -e staging -s backend -- sh -c 'cd /app && test "$RAILWAY_ENVIRONMENT_NAME" = staging && /app/.venv/bin/python scripts/cargar_demo.py --entorno staging --confirmar'  # escribe
```

- Sin `--entorno staging` (o con `RAILWAY_ENVIRONMENT_NAME` distinto de `staging`) se niega con código 2. Sin `--confirmar` no escribe. Nunca imprime la URL ni las credenciales, solo `host:puerto/base`.
- Carga: 5 proveedores (PRV-0001 y PRV-0002 con esos códigos, los que ya nombran los precios del seed) con 5 a 8 productos cada uno y algunas filas de precio anterior; 2 pedidos de proveedor al precio vigente de hoy (no mueven ningún costo); 9 cotizaciones guardadas de 6 productos en fechas distintas (cada una con el dólar de su fecha; los productos 7 y 8 quedan sin cotizar); 4 lotes (PLANIFICADA, EN_CORTE, EN_CONFECCION, LISTA); 5 formularios de consumos (un modelo nuevo ENVIADO para practicar, uno COMPLETADO, uno devuelto con comentario, un BORRADOR y uno VALIDADO).
- Todo pasa por `servicios`, `proveedores` y `formulario`. Cada fila lleva `EJEMPLO` en su `nota`; la cotización no tiene nota y se reconoce por (producto, tipo). Se puede correr dos veces: la segunda no crea nada y un formulario que alguien ya avanzó no se toca.
- SUPUESTO: validar. Los precios, medidas y nombres de proveedores son inventados; solo sirven para la demo.
