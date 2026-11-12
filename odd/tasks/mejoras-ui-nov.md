# mejoras-ui-nov — 10 mejoras de UI/producto (2026-11-12)
Branch por flujo en worktrees (herdr): feature/panel, feature/costos-fijos, feature/proveedores-talleres, feature/shell. Todos se mergean a main. Delivery: ask-on-risk. Tests: pytest backend / pnpm lint+build front.

## Specs
- S1 Panel: sacar "Dólar 1.625,00 · 03/11/2026"; sacar "Total de la fábrica, sueldos incluidos", "Lo que costó fabricar lo producido", "Lo producido en el mes, no lo vendido"; sacar el cuadro "Estructura del costo" (queda "Precios de materiales").
- S2 Tipo de cambio: "solo un cuadro que muestre la cotización del día de manera automática"; sin historial.
- S3 Quitar el cuadro "Costo por unidad, mes a mes".
- S4 Alertas, parámetros sin confirmar y "cosas que faltan" en una sola sección, con filtro; "algo mucho más resumido".
- S5 Costos fijos (mano de obra y servicios básicos): sin la grilla gris vacía; solo grillas completas y al final el botón "Agregar item".
- S6 Evaluar si Modelos y Productos van separados o juntos (solo evaluación).
- S7 Proveedores y talleres: historial de productos/precios por proveedor, y de lo pagado a cada taller por cantidad de productos, en el tiempo.
- S8 Evaluar "Grilla completa"; probablemente eliminarla.
- S9 Administración con interfaz tipo SaaS; va encima de Panel, no al final.
- S10 Desktop: botón de voz chico al lado del nombre de usuario (graba al apretar); mobile queda igual.

## Tasks
- T1 S1,S2,S3,S4 — worktree panel — delegated — pending
- T2 S5 — worktree costos-fijos — delegated — pending
- T3 S7 — worktree proveedores-talleres — delegated — pending
- T4 S8,S9,S10 — worktree shell — delegated — pending
- T5 S6 — evaluado: DER separado, UI unificada (Productos en el menú; bloque Modelo en la ficha; catálogo de modelos dentro de Administración). Implementar tras mergear feature/shell (toca nav.ts) — pending

## Log
L1 (2026-11-12) Pedido original del usuario: ver los 10 puntos arriba (resumidos en Specs).
Route: 4 writers en paralelo (unidades independientes, superficies disjuntas, varias horas de trabajo cada una).
L2 (2026-11-12) Usuario: "si hagamos eso que dices del punto 6" (aprueba unificar la UI de Modelos dentro de Productos, sin fusionar tablas).
