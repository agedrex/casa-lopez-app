# Insumos por modelo y costeo con precio unitario (paso 2)
Objective: que el costo use los precios unitarios de los pedidos de proveedor. Branch: main. Delivery: ask-on-risk. Runner: `uv run --directory backend pytest -q` (con `TEST_DATABASE_URL`); front: `cd front && corepack pnpm lint && corepack pnpm exec tsc --noEmit && corepack pnpm build && corepack pnpm test`.

## Specs
- S1: Tabla `modelo_insumo` (código `MIN-nnnn`, modelo_id, material_id, cantidad_por_unidad NUMERIC(12,6) > 0, único por modelo + material), migración 0019 con downgrade. La cantidad está en la unidad de consumo del material.
- S2: Motor: cada insumo del modelo es una línea de costo `cantidad × precio unitario vigente a la fecha de la cotización` (misma regla de precio, color NULL/genérico, USD × dólar de la fecha, ARS tal cual, sin precio o sin dólar = cotización incompleta con aviso, igual que las líneas de material actuales). El monto va a la etapa del material (HERRAJES, HILO_CEMENTO, etc.).
- S3: Sin doble conteo: si un modelo tiene insumos en la etapa HERRAJES, esos reemplazan a `herrajes_usd_por_unidad` para ese modelo; si tiene en HILO_CEMENTO, reemplazan a `hilo_y_cemento`. Un modelo sin insumos se costea exactamente igual que hoy (los tests existentes del motor no cambian).
- S4: Al VALIDAR la hoja del taller (`formulario.cambiar_estado` -> `_aplicar_medidas`), cada fila de la sección HERRAJE con cantidad, y las filas de CONSUMO "FRISELINA", "CARTÓN FIBRA", "CARTULINA", "MOIRE" con cantidad, cuyo nombre coincida (sin distinguir mayúsculas, acentos ni espacios repetidos) con el `nombre` o `nombre_corto` de un material cotizable, se guardan como `modelo_insumo` del modelo (solo si el modelo no estaba validado, igual que las medidas). Las filas con cantidad que no coincidan con ningún material NO se guardan y se devuelven en la respuesta de validar como `sin_material: [nombre, ...]` (campo nuevo opcional del detalle del formulario).
- S5: El detalle del modelo (`GET /modelos/{codigo}`) lista sus insumos (material, unidad, cantidad, precio unitario vigente si hay). El front lo muestra en la ficha del modelo y avisa en la hoja validada qué filas quedaron `sin_material`.
- Supuestos (SUPUESTO, validar): el match por nombre es una convención nuestra; los insumos por modelo no tienen UI de edición en esta tanda (solo se llenan al validar la hoja); sin stock.
- Fuera: stock, edición manual de insumos, abrir la ficha de proveedores al gerente.

## Tasks
- T1 (S1-S4) backend: migración 0019, modelo, motor, formulario, tests, docs. Route: delegated (toca el motor; verifier independiente). DONE (ff04348; suite 2607 passed, 6 skipped; verifier: sin blockers, comparación de 1300 cotizaciones idéntica a la base).
- T2 (S5) front: ficha del modelo + aviso `sin_material`. Route: delegated. DONE.

## Log
- L1 (2026-11-13): "avanza con todo lo que quede y lleguemos a staging". Paso 2 del plan aprobado ("si", 2026-11-13).
- L2 (2026-11-13): verifier advisories (no se corrigen ahora): insumos viejos no se borran al revalidar; la ficha del modelo busca precio a date.today() y el costo a la fecha del dólar más nuevo; el desperdicio aplica también a insumos (hoy 0); duplicar_formulario no copia modelo_id. Se agregaron 2 tests de regresión en test_receta.py.
