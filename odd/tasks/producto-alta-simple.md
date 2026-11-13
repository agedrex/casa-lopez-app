# Alta de producto solo con nombre, taller mide, admin valida
Objective: tanda 1 de la mejora del flujo producto -> taller -> validación. Branch: main. Delivery: ask-on-risk. Runner: `uv run --directory backend pytest -q`; `cd front && corepack pnpm lint && corepack pnpm build`.

## Specs
- S1: "Al crear un nuevo producto solo se debería definir el nombre." El ID (códigos `PRD-`/`MOD-`/`FCO-`) se genera solo.
- S2: "En automático debería ponerse todo en mayúsculas siguiendo la misma nomenclatura en lo posible." Nombre normalizado: espacios colapsados + mayúsculas. Un nombre repetido (sin distinguir mayúsculas) es un conflicto.
- S3: "Y de eso tiene que llegar a la parte de taller, donde en taller ya tiene que empezar a sacar todas las medidas." El alta crea modelo + producto + formulario de consumos ya ENVIADO al taller, en una sola transacción.
- S4: "Luego el administrador debería validar eso." Al VALIDAR el formulario, las medidas pasan al modelo del producto (CUERO, FLEX, GOMA EVA; FORRO no se copia porque el modelo también necesita elegir el material) y el modelo queda `validado` con origen `MEDIDO`. Solo si el modelo aún no estaba validado. Herrajes no se pasan (son cantidades, no USD).
- Supuestos (SUPUESTO, validar): `quien_lo_confecciona` = EXTERNA por defecto; el formulario se envía solo (sin paso manual del admin); categoría y tamaño quedan vacíos hasta completarlos.
- Fuera de esta tanda: lotes, unidades producidas, resumen por taller, insumos con precio unitario (hilo, botones).

## Tasks
- T1 (S1-S3) backend: servicio + `POST /productos/nuevo` solo admin + tests. Route: inline. DONE (2535 passed, 6 skipped con Postgres).
- T2 (S4) backend: aplicar medidas al modelo al validar + tests. Route: inline. DONE.
- T3 (S1-S3) frontend: alta con un solo campo; el formulario viejo queda en "avanzado". Route: inline. DONE (lint, tsc, build limpios; sin prueba en navegador).

## Log
- L1 (2026-11-12): "A la hora de crear un nuevo producto, el ID y todo eso se debería generar en automático. Al crear un nuevo producto solo se debería definir el nombre. En automático debería ponerse todo en mayúsculas siguiendo la misma nomenclatura en lo posible. Y de eso tiene que llegar a la parte de taller, donde en taller ya tiene que empezar a sacar todas las medidas. [...] Y que el taller, una vez que ya llenan los datos de todo lo que se está usando, debería ser preciso. Luego el administrador debería validar eso." Tanda 1 acordada con "si".
- L2 (2026-11-13): "lo que se tiene que crear es el modelo porque el producto puede ser de diferente color [...] tienes que sacar las medidas y todo eso y luego se saca el producto." Cambio: el alta crea modelo + hoja (migración 0017 `formulario_consumo.modelo_id`), no crea producto; tras validar, link a crear el producto del modelo (cuero y color).
- L3 (2026-11-13): "unides producidas el calndaria ya deberia estar por defecto en el mes que toca" -> /unidades abre en el mes actual; `?periodo=todo` muestra todo.
