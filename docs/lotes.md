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
