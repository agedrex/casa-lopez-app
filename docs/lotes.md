# Lotes: estados y reglas (QA de staging, 2026-11-17)

Reglas de `orden_fabricacion` que se agregaron después del QA manual de staging (`odd/tasks/mejoras-qa-staging.md`, S3 y S4).
Todas viven en el backend; el front muestra el mensaje que devuelve.

## Estados: uno por uno

El ciclo es `PLANIFICADA` → `EN_CORTE` → `CORTADA` → `EN_CONFECCION` → `LISTA` → `CERRADA` (`LOT_STATES` en `models.py`).

- `POST /ordenes/{codigo}/estado` (solo admin) acepta únicamente el estado **siguiente**. Saltear uno (Planificada → Lista)
  o volver atrás responde 409 con un mensaje como "El lote LOT-0001 está en Planificada: el siguiente estado es En corte. No se
  puede pasar a Lista." La negativa no deja fila en el historial.
- `POST /ordenes/{codigo}/avanzar` (taller) ya avanzaba solo al siguiente y se detiene en `LISTA`: cerrar es del admin.
- `POST /ordenes/{codigo}/estado/deshacer` (admin y taller) vuelve un estado atrás, solo si el último cambio lo hizo el mismo usuario hace menos de 10 minutos. Agrega una fila al historial (no borra nada), no sirve en lotes cerrados ni en `PLANIFICADA`, ni si ya se cortó cuero de un lote en `EN_CORTE` o `CORTADA`, y no se puede encadenar.
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

## Cuero reservado por otros lotes (derivado, informativo)

QA S2: dos lotes "alcanzaban" con los mismos 3 m². `GET /ordenes/{codigo}/cuero` (`cueros.resumen_de_lote`) ahora resta del stock lo
que **otros lotes abiertos** todavía tienen que cortar del mismo cuero (material + color). No hay migración ni tabla nueva: la
reserva se calcula en cada lectura.

- **Stock**: el de siempre (`_opciones_disponibles`, piezas no cerradas con m² a favor). Lo ya cortado salió del stock por sus
  movimientos `CORTE`, así que de otro lote solo se reserva `consumo × cantidad − ya cortado` por renglón (nunca menos de 0): no se
  cuenta dos veces. Mismo criterio de consumo que el resumen: sin desperdicio, sin renglones quitados (`~renglon_quitado()`).
- **Otros lotes abiertos** = estado distinto de `CERRADA` (incluye `PLANIFICADA`). Un lote cerrado no reserva.
- **Campos nuevos por cuero**: `reservado_por_otros` (m²), `reservado_por` (códigos de lote), `libre` (stock − reservado, mínimo 0) y
  `mensaje` (español, `null` si alcanza). `disponible` sigue siendo el stock total; `alcanza`, `faltante` y `sobrante` se calculan
  contra `libre`. Con un solo lote abierto el resumen no cambia (reservado 0).
- Ejemplo: 3 m² de stock y dos lotes de 2 m² cada uno → cada uno ve `reservado_por_otros = 2`, `libre = 1`, `alcanza = false` y
  "No alcanza: faltan 1 m² de Estándar. Hay 3 m² en stock y LOT-0001 tiene reservados 2 m²."
- **No bloquea nada**: crear, cambiar o avanzar un lote sigue igual. Es una advertencia. Solo m², sin plata (lo lee el taller).
- Front: `/fabricacion/[codigo]` y la vista del taller muestran `reservado_por_otros`, los códigos y el `mensaje` que devuelve la API;
  no suman ni restan.

SUPUESTO: validar con Robert. (1) Se reserva desde que el lote existe, no recién al planificarlo (estado `EN_CORTE`). (2) La reserva
es simétrica: cada lote ve lo que necesitan todos los otros, sin orden de llegada, así que con 3 m² y dos lotes de 2 m² **ninguno**
dice "alcanza". Alternativa: reservar solo lo de lotes más viejos (el primero alcanza, el segundo no). (3) La reserva solo informa, no
bloquea crear ni avanzar. (4) El texto del mensaje.

## Front

La pantalla del lote (`/fabricacion/[codigo]`) ofrece en "Cambiar el estado" solo el estado siguiente, y los botones de cambio de
estado (admin) y "avanzar" (taller) muestran tal cual el mensaje 409 del backend (cerrado, estado que corresponde, falta cortar cuero).
