# Lanzamiento listo (2026-11-17)
Dejar la app lista para usar mañana: altas inline, vista de lote del taller, menú mobile, prueba end to end.

## Specs
- S1: "tanto en categorías como en cuero y todo lo que hay, necesito que, de alguna forma, el usuario, cada vez que entra a un campo de este tipo, pueda cargar más opciones si es que las tiene"
- S2: "el menu en la version mobile no esta optimizado con el nuevo orden"
- S3: "queriendo ir al taller, ¿se puede averiguar un resumen de los lotes que tiene, el cuero que tiene disponible y cuánto se va a usar?"
- S4: "al realizar cada uno de los productos que se vayan haciendo, lo que realmente seleccione sea el producto en sí y no otra cosa, y tenga los montos correctos"
- S5: "probar end to end la app" (caso de uso del administrador) y optimizar mobile.

## Tasks
- [x] T1 (S1) altas inline: material en pedido, cuero en producto, taller en lote — feat(altas) commit
- [x] T2 (S2) menú mobile = orden desktop — feat(nav) commit
- [x] T3 (S3) resumen de cuero por lote para el taller (GET /ordenes/{codigo}/cuero) — feat(lotes) commit
- [x] T4 (S4, S5) suite backend con Postgres local: 3127 passed; front tsc, biome, 107 tests, build OK. Recorrido manual por UI NO hecho

## Log
L1: pedido original del usuario (ver mensaje 2026-11-17: "Tengo que tomar una ducha...").
L2: bloquear duplicados en un lote NO se hizo: test_items_can_be_added_to_an_existing_lot agrega el mismo producto dos veces a propósito; decisión de producto pendiente.
