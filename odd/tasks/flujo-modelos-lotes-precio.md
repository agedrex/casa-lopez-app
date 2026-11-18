# Flujo modelos → lotes → precio (QA en staging)
Rama feat/flujo-modelos-lotes-precio. Origen: QA con ego-browser en staging (2026-11-18). Todo termina desplegado en staging, nunca production.

## Specs
- S1 (A) Plantilla de la hoja de consumos: sacar la fila "DESPERDICIO 30%": "ya no aplica eso, debe poner el consumo real de todo". Las filas de horas/mano de obra/corte/empaque no pueden decir "(m²)".
- S2 (A) "la ficha que tenemos hoy en día sea como el template que se crea por defecto, pero que, al enviarlo, tenga la opción de cambiarlo o editarlo si quisiera". El admin ve toda la plantilla, agrega/quita/renombra filas y la edita; la hoja nace en BORRADOR y se envía con un botón explícito; también editable en revisión (COMPLETADO).
- S3 (B) Al validar, si una fila (forro, herrajes, etc.) no se aplica al modelo por no coincidir con un material, avisar qué filas no se aplicaron; revisar que "FORRO / TELA" y "CIERRE N5" coincidan cuando existe el material.
- S4 (C) Gerente: "en base a los lotes que ya se hicieron debe definir un precio tomando en cuenta el margen que dijimos que el debe escoger, sobre ese precio se deben aplicar los impuestos que tenga cargado el usuario". Margen sobre el precio (precio_venta.margen, fracción del precio). Mostrar en la ficha de producto: costo real por lote, margen elegido, precio neto, precio con impuestos.
- S5 (D) "Desde que se termina y el taller ya terminó" cuenta una unidad como producida. Unificar panel y pantalla Unidades con ese criterio; que cada lote muestre cómo mueve el costo variable.
- S6 (E) El chequeo de cuero al crear el lote debe descontar lo reservado por otros lotes (hoy dice "Sí, alcanza" y luego "Falta").
- S7 (F) Selector de modelo en Nuevo producto: lo mostrado y lo guardado coherente; botones no tapados por la barra inferior; limpiar datos QA/basura de staging (autorizado por el usuario).

## Tasks
- T1 S1,S2,S3 — worker — commit: abacf67, a6b70d9
- T2 S4 — worker — commit: feat(precio) + feat(front) (ver git log)
- T3 S5,S6 — worker — commit: feat(lotes) + feat(front) (ver git log)
- T4 S7 — inline — commit: fix(front) alta de modelo y selector; limpieza de datos QA en staging pendiente
- T5 deploy a staging y verificación con ego-browser — inline — pendiente

## Log
L1 (usuario, original): ver conversación: "Quiero que trabajemos lo siguiente: ... pruebes el caso ... precio ... desperdicio del 30% ... hasta dejarlo todo en staging".
L2: "1.- Desde que e termina y el taller ya termino 2.- Claro, 3.- Si te confirmo A-F. Haz todo hasta que este todo en staging"
