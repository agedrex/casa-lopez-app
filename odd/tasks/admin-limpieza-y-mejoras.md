# Admin limpieza y mejoras
Objetivo: 4 cambios independientes, cada uno en su rama/worktree, luego merge a main. Estrategia: ask-on-risk. Tests: `uv run --directory backend pytest -q`, `cd front && corepack pnpm lint && corepack pnpm build`.

## Specs
- S1 (WO-A1) Quitar la pantalla de resumen de Administración (`/admin`) y la pestaña Parámetros. Los valores de `parametro` siguen en la base y el motor los lee igual.
- S2 (WO-A2) Administración deja solo Usuarios, Impuestos y Google Sheet. "Debería ser solo usuarios": Personas sale de Administración y se gestiona donde se usa (Costos fijos / Mano de obra). Modelos y Catálogos (colores, categorías) salen de Administración y pasan a Productos, sin perder funciones (alta de modelos, validar consumos).
- S3 (WO-B) Impuestos: grilla editable donde se agregan o quitan impuestos y solo se pone el porcentaje. Van sobre el precio de venta designado ("Si es que hay impuestos deberian ir sobre el precio de venta que se designe"), no sobre el costo. El motor de costeo NO cambia. Margen real sobre el precio sin impuestos (SUPUESTO: validar).
- S4 (WO-C) "Quiero que el código de proveedores y taller sea automático, no que lo tenga que escribir el usuario."
- S5 (WO-D) "El inventario de cueros tiene una sección de Por secciones o todo junto. Quiero que quitemos las dos opciones y muestre directamente la grilla como muestran 'todo junto'. Lo mismo en la parte de materiales y precios."

## Tasks
- T1 S1+S2 WO-A (A1 luego A2) — delegada — HECHO (9b5ed63)
- T2 S3 WO-B — delegada — HECHO (2096caf)
- T3 S4 WO-C — delegada — HECHO (8d6e145)
- T4 S5 WO-D — delegada — HECHO (eaf6549, e1bcc11)
- T5 merge a main en orden D, C, A, B — HECHO; más migración 0013 (grilla de impuestos vacía)

## Log
L1 (2026-11-12) pedido original: lista de 3 puntos (ver Specs, textos del usuario). "no crees work orders, solo empieza a trabajar".
L2 impuestos sobre precio de venta, confirmado por el usuario.
Ruta: delegada, razón = unidades independientes en paralelo con superficies disjuntas.
L3 (2026-11-12) usuario: dejar todo lo de impuestos vacío (0013 borra IVA, IIBB, GANANCIAS sembrados); push a main autorizado. Producción NO desplegada.
