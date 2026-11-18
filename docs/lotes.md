# Lotes: estados y reglas (QA de staging, 2026-11-17)

Reglas de `orden_fabricacion` que se agregaron después del QA manual de staging (`odd/tasks/mejoras-qa-staging.md`, S3 y S4).
Todas viven en el backend; el front muestra el mensaje que devuelve.

## Estados: uno por uno

El ciclo es `PLANIFICADA` → `EN_CORTE` → `CORTADA` → `EN_CONFECCION` → `LISTA` → `CERRADA` (`LOT_STATES` en `models.py`).

- `POST /ordenes/{codigo}/estado` (solo admin) acepta únicamente el estado **siguiente**. Saltear uno (Planificada → Lista)
  o volver atrás responde 409 con un mensaje como "El lote LOT-0001 está en Planificada: el siguiente estado es En corte. No se
  puede pasar a Lista." La negativa no deja fila en el historial.
- `POST /ordenes/{codigo}/avanzar` (taller) ya avanzaba solo al siguiente y se detiene en `LISTA`: cerrar es del admin.
- Un lote `CERRADA` no cambia de estado. Repetir el estado actual sigue siendo 409. Cerrar sin fecha de entrega sigue siendo 422.
- Crear un lote con `estado` ya elegido (importaciones, datos de ejemplo) no pasa por esta regla.

## El taller necesita el cuero cortado

SUPUESTO: validar con Robert. Al avanzar a `CORTADA` o `LISTA`, cada renglón del lote que tenga unidades, no esté quitado y cuyo
producto lleve cuero tiene que tener al menos un movimiento `CORTE` (lo escribe la pantalla Corte, `POST /cueros/{codigo}/cortes`).
Si falta, 409 con los productos y renglones sin corte. No se compara el m² cortado con el consumo del modelo (nadie confirmó
que tenga que alcanzarlo) y los productos sin cuero (kits) no piden nada. El admin no tiene esta guarda.

## Un lote cerrado no admite productos

`POST /ordenes/{codigo}/items` responde 409 ("El lote LOT-0001 está cerrado: no se puede agregar un producto.") si el lote está
`CERRADA`, igual que ya hacían cambiar la cantidad (`PUT`) y quitar un renglón (`DELETE`). El costo y la cotización final de un
lote cerrado no cambian.

## Fechas del lote

Se aplican al crear el lote (`fecha_de_envio`, `fecha_de_entrega`) y al cambiar su estado (la fecha del cambio y la de entrega al
cerrar). El rechazo es 422 con un mensaje en español y no guarda nada.

- La fecha de entrega no puede ser anterior a la de envío (el mismo día vale). Al cerrar se compara con la fecha de envío del lote.
- SUPUESTO: validar con Robert. Rango razonable: desde el 01/01/2020 hasta 365 días después de hoy
  (`FECHA_MINIMA_DE_LOTE` y `DIAS_HACIA_ADELANTE_DE_LOTE` en `servicios.py`). Los topes los pusimos nosotros.
