# Formularios de consumos y herrajes

La planilla de papel de consumos y herrajes de cada artículo nuevo, hecha digital. **No calcula nada**: no hay costos, totales ni dólar. Las cantidades son exactamente lo que escribió una persona (`0,25` o `0.25`, hasta 6 enteros y 6 decimales). No toca `modelo`, `receta_linea` ni el motor de costeo. Nada se borra.

Código: `backend/src/backend/formulario.py` (reglas y API, el docstring del módulo es la referencia) y, en el frontend, `front/components/formulario-consumos.tsx` (la hoja), `front/app/(app)/formularios/` (pantallas y acciones) y `front/lib/formulario.ts` (reglas puras).

## Cómo nace: el modelo nuevo

Lo que llega al taller son **modelos**, no productos. Crear un modelo es una sola cosa (pantalla "Nuevo modelo", `/productos/modelos/nuevo`; `/productos/nuevo` muestra el mismo formulario como atajo): **nombre**, **categoría**, tamaño (opcional) y **notas** (opcional, `modelo.nota`). No se piden consumos. `POST /productos/nuevo` (admin) crea en una transacción el modelo (`validado = false`, consumos en NULL) y su formulario ya `ENVIADO` con ese `modelo_id`; el nombre va a `articulo` (en MAYÚSCULAS) y las notas se copian a la nota del formulario, que el taller lee arriba de la hoja y no puede editar. El taller completa las filas y el admin valida: ahí las medidas y los insumos pasan al modelo y quedan como su receta. Después se crea el producto (cuero y color).

La ficha del modelo (`/productos/modelos/<código>`, admin) lista sus formularios con el estado (`GET /formularios?modelo=MOD-NNNN`). Los modelos viejos (del Excel) siguen con sus consumos y no tienen formulario. SUPUESTO (validar): la categoría es obligatoria al crear; si el taller necesita otro dato del modelo, va en las notas.

El alta completa con todos los consumos (`POST /modelos`) sigue en la API pero ya no tiene pantalla.

## Pantallas

| Ruta | Quién | Qué hace |
|---|---|---|
| `/formularios` | admin, taller | Lista con búsqueda (`q`: código, artículo, producto o taller) y filtro de estado. El taller solo ve `ENVIADO` y `COMPLETADO`. El admin abre "Nuevo formulario": artículo, taller (opcional) y código de producto (opcional). |
| `/formularios/<código>` | igual | La hoja con ARTÍCULO, las notas del modelo (si las hay) y las tablas CONSUMOS (`M2`) y HERRAJES (`CANTIDAD`), cada una con `COMENTARIOS / MODIFICACIONES`. Celdas editables, "Agregar fila" y "×" por fila; ninguna fila es obligatoria. |
| Ficha del producto | admin | Si el producto tiene un formulario `VALIDADO`, la sección "Formulario de consumos" lo muestra de solo lectura, sin las filas vacías, con un link al formulario. |

Menú: "Formularios" en Producción para admin y taller. Al taller el formulario no le muestra costos, y el código del producto aparece como texto, sin link a la ficha.

## Flujo y botones

`BORRADOR` → (admin envía) `ENVIADO` → (taller completa) `COMPLETADO` → (admin valida) `VALIDADO`, o el admin lo devuelve a `ENVIADO` con un comentario que el taller ve arriba de la hoja.

| Botón | Quién | Cuándo |
|---|---|---|
| Guardar | admin; taller | admin hasta `COMPLETADO`; taller solo en `ENVIADO` (solo las filas) |
| Enviar / Reenviar al taller | admin | `BORRADOR` / `ENVIADO` |
| Completar | taller (y admin) | `ENVIADO` |
| Devolver con comentario | admin | `COMPLETADO` |
| Validar | admin | `COMPLETADO` |
| Duplicar | admin | siempre; copia filas, cantidades y comentarios a un borrador nuevo |
| Imprimir | todos | abre el diálogo del navegador: "Guardar como PDF" da el PDF con el formato de la planilla |

Los botones de estado guardan primero lo que se escribió si cambió algo, así "Completar" no pierde cambios. Un formulario `VALIDADO` es de solo lectura para todos: para cambiarlo se duplica.

SUPUESTO (validar): el rol `taller` no está atado a un taller concreto; cualquier usuario `taller` ve los formularios `ENVIADO` y `COMPLETADO`.
