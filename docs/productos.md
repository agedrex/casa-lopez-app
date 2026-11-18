# Productos: estado del ciclo derivado

> Spec S8 de `odd/tasks/flujo-modelos-lotes-precio.md`. **SUPUESTO: validar con Robert** (pedido de QA para la demo, 2026-11-18).

## Qué pasaba

`producto.estado_del_ciclo` es una columna guardada y nada la hacía avanzar: un producto con precio de venta guardado y lotes terminados seguía diciendo "En definición" en la ficha y en la lista.

## Regla

El estado que muestran la lista, el filtro `estado` y la ficha se **deriva al leer** y nunca se escribe. Es el más alto de estos (orden: `EN_DEFINICION` < `COTIZADO` < `EN_PRODUCCION` < `PRODUCIDO`):

| Hecho | Estado |
|---|---|
| El valor guardado en la columna | el que sea |
| Tiene al menos una fila en `precio_venta` | `COTIZADO` |
| Tiene un renglón (`orden_item`) en un lote que **no** está terminado | `EN_PRODUCCION` |
| Tiene un renglón en un lote terminado (`LISTA` o `CERRADA`, `servicios.ESTADOS_TERMINADOS`, el mismo criterio que el costo variable) | `PRODUCIDO` |

- Un renglón quitado de su lote (cantidad 0 y marca `[QUITADO]`) no cuenta. SUPUESTO: validar.
- La columna queda como piso: si alguien guardó `PRODUCIDO`, sigue siendo `PRODUCIDO` aunque no haya lotes.
- Lista, conteo, filtro y ficha comparten las mismas condiciones SQL (`servicios.ciclo_con_precio_sql`, `ciclo_en_lote_abierto_sql`, `ciclo_en_lote_terminado_sql`, `ciclo_efectivo_sql`) y la misma función pura (`estado_del_ciclo_efectivo`), así que siempre coinciden.
- El control de calidad "Falta la fecha de cierre" sigue leyendo el estado **guardado** (`DatosProducto.estado_guardado`): un producto que figura como producido por sus lotes no es un error de carga.

## Pruebas

`backend/tests/test_ciclo_derivado.py` (reglas puras y forma del SQL) y `test_ciclo_derivado_integration.py` (Postgres: lista, filtro, conteo y ficha coinciden).
