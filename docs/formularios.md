# Formularios de consumos y herrajes

La planilla de papel de consumos y herrajes de cada artículo nuevo, hecha digital. **No calcula nada**: no hay costos, totales ni dólar. Las cantidades son exactamente lo que escribió una persona (`0,25` o `0.25`, hasta 6 enteros y 6 decimales). No toca `modelo`, `receta_linea` ni el motor de costeo. Nada se borra.

Código: `backend/src/backend/formulario.py` (reglas y API, el docstring del módulo es la referencia) y, en el frontend, `front/components/formulario-consumos.tsx` (la hoja), `front/app/(app)/formularios/` (pantallas y acciones) y `front/lib/formulario.ts` (reglas puras).

## Pantallas

| Ruta | Quién | Qué hace |
|---|---|---|
| `/formularios` | admin, taller | Lista con búsqueda (`q`: código, artículo, producto o taller) y filtro de estado. El taller solo ve `ENVIADO` y `COMPLETADO`. El admin abre "Nuevo formulario": artículo, taller (opcional) y código de producto (opcional). |
| `/formularios/<código>` | igual | La hoja con ARTÍCULO y las tablas CONSUMOS (`M2`) y HERRAJES (`CANTIDAD`), cada una con `COMENTARIOS / MODIFICACIONES`. Celdas editables, "Agregar fila" y "×" por fila; ninguna fila es obligatoria. |
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
