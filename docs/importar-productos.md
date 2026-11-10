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
- Si existe `RAILWAY_ENVIRONMENT_NAME` y no es `staging`, se rechaza (sin mostrar el valor).
- Nunca imprime la URL ni las credenciales.
- Nada se borra ni se actualiza: solo se agregan productos (y el color `Arena` si no existe).

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
