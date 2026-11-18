# Lanzamiento listo (2026-11-17)
Dejar la app lista para usar mañana: altas inline, vista de lote del taller, menú mobile, prueba end to end.

## Specs
- S1: "tanto en categorías como en cuero y todo lo que hay, necesito que, de alguna forma, el usuario, cada vez que entra a un campo de este tipo, pueda cargar más opciones si es que las tiene"
- S2: "el menu en la version mobile no esta optimizado con el nuevo orden"
- S3: "queriendo ir al taller, ¿se puede averiguar un resumen de los lotes que tiene, el cuero que tiene disponible y cuánto se va a usar?"
- S4: "al realizar cada uno de los productos que se vayan haciendo, lo que realmente seleccione sea el producto en sí y no otra cosa, y tenga los montos correctos"
- S5: "probar end to end la app" (caso de uso del administrador) y optimizar mobile.

- S6: "En un bloque o en un lote, en realidad, pueden haber varios productos y de ese producto más de uno. Sí que no debería bloquear. Se puede hacer un lote con tres productos de un tipo y tres de otro."
- S7: "Agregemos eso pero solo para el admistrador" (cambiar la cantidad o quitar un renglón de un lote)
- S8: "El costo va a ser el que tome los productos que se cargaron y cómo se subieron en realidad. Así que no habría que actualizarlo ni nada. Sino que toma el cuero y todos los valores del momento en que se hizo. O sea, una vez que se cierra un lote y se dice qué se va a hacer, se hace al costo que dice, en base, obviamente, al precio que costó el producto en sí. Luego se calcula con el dólar del día obviamente."
- S9: "Haz una simulacion usanod las funciones del codigo"
- S10: "En cada lote debería poder ver, obviamente, qué productos están siendo y luego, obviamente, poder ver cuánto consume de cada producto. Pero sí igual estaría bueno que se vea al final cuánto consume de x cantidad de cada producto, de cada insumo en sí, el lote y, en total, cuánto es el costo de ese lote."
- S11: "el taller tiene que tener visibilidad, obviamente muy clara, de qué lotes se tienen que hacer o se están haciendo y en qué estado están. Obviamente lo del taller: tener la opción de ir actualizando el estado en base a cómo viene todo"
- S12: "Si el administrador puede hacer el seguimiento y ver desde el día que se creó hasta el día que se terminó ese lote"
- S13: "una vez que marches todo a main, que llegue a staging para que empieces a probarlo."

## Tasks
- [x] T1 (S1) altas inline: material en pedido, cuero en producto, taller en lote — feat(altas) commit
- [x] T2 (S2) menú mobile = orden desktop — feat(nav) commit
- [x] T3 (S3) resumen de cuero por lote para el taller (GET /ordenes/{codigo}/cuero) — feat(lotes) commit
- [x] T4 (S4, S5) suite backend con Postgres local: 3127 passed; front tsc, biome, 107 tests, build OK. Recorrido manual por UI NO hecho

- [x] T5 (S6, S7) worktree feat/lote-editar-items: admin edita cantidad / quita renglón — PUT y DELETE /ordenes/{codigo}/items/{item}, sin migración (ver L5-L7)
- [ ] T6 (S8, S10) worktree feat/lote-costo-consumo: costo congelado a la fecha del lote + consumo por producto, por insumo y costo total
- [ ] T7 (S11, S12) worktree feat/taller-estados: el taller ve sus lotes por estado y actualiza el estado; el admin ve el seguimiento de creación a fin
- [ ] T8 (S9) simulación end to end con las funciones del código
- [ ] T9 (S13) merge a main y llegada a staging

## Log
L1: pedido original del usuario (ver mensaje 2026-11-17: "Tengo que tomar una ducha...").
L2: bloquear duplicados en un lote NO se hizo: test_items_can_be_added_to_an_existing_lot agrega el mismo producto dos veces a propósito; decisión de producto pendiente.
L3: respuesta del usuario 2026-11-17 a los pendientes (ver S6-S13, verbatim arriba). Duplicados: NO se bloquean (cierra el L2).
L4: SUPUESTO mío para S8: el costo de un lote usa precios y dólar vigentes en la fecha de creación del lote (fecha_de_envio, automática), por lo que no cambia después. Validar con el usuario.
L5: T5 decisión: "quitar" NO borra (regla de oro 11). El renglón queda con cantidad 0 y la marca `[QUITADO]` en su `nota`, más una línea de historial (fecha, cantidad anterior → nueva, id de usuario). Cada cambio de cantidad agrega otra línea. Se eligió esto porque las migraciones están fuera del alcance de T5 y una columna `quitado` obliga a filtrar cada consulta de renglones (los worktrees T6/T7 agregan consultas nuevas). Toda suma ya ignora un renglón en 0; las consultas que cuentan renglones (`_cargar_items`, unidades por producto, historial de precios del taller, resumen de cuero del lote, corte) filtran con `models.renglon_quitado()`. REGLA para T6/T7: toda consulta nueva sobre `OrdenItem` que cuente renglones o los liste tiene que filtrar `~renglon_quitado()`. Mejora futura: columna `quitado` + migración. Riesgo item 1: sin migración, pero se edita en el lugar `orden_item.cantidad` y `nota` de datos guardados (el valor previo queda solo en la nota).
L6: SUPUESTO (validar con Robert): editar cantidad y quitar se permiten en todos los estados menos CERRADA (409), aunque el corte ya haya empezado; un renglón con cortes de cuero registrados (`movimiento_cuero` CORTE) no se puede quitar (409) pero sí cambiar su cantidad. Repetir la misma cantidad es 409 (doble clic = una sola línea de historial). Cantidad > 0 (422); no se bloquean repetidos (S6). Quitar el último renglón se permite (queda un lote vacío).
L7: solo admin (`ESCRITURA`/`SoloAdmin`; en la matriz de `test_roles.py`); el taller y el gerente reciben 403. La pantalla del lote (admin) tiene "Cambiar o quitar productos": campo de cantidad + Guardar, y Quitar pide confirmación en línea; controles de 44 px de alto; lista plegable "Productos quitados" con su historial.
