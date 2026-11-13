# modelos-lotes-proveedores-nov — cambios pedidos 2026-11-13
Branch: feature/modelos-lotes-proveedores. Delivery: ask-on-risk. Tests: pytest backend + pnpm lint/build front.

## Specs
- S1 Costos fijos: sin el formulario "¿Cómo quiere copiarlos?"; el mes nuevo arranca con la grilla lista; Mano de obra se mantiene mes a mes (sin preguntar).
- S2 Grilla de productos (Mercadería): sin la fila gris extra; "aumentamos la grilla y listo".
- S3 Alta de modelo: solo nombre y algunos detalles (notas) y se envía al taller para que cargue los consumos; al validar queda como receta.
- S4 Lotes: buscar productos de toda la base, agregar varios, elegir fábrica o taller.
- S5 Proveedores: lista de productos que venden (unidad, cantidad, precio referencial).
- S6 Productos: margen neto (%) editable que genere el precio final como campo de la grilla.
- S7 Materiales: directamente la grilla de materiales, agrupada por categoría; sin el formulario aparte.

## Tasks
- T1 S1 — inline — done (sin commit aún)
- T2 S2 — inline — done
- T3 S3 — pending
- T4 S4 — pending
- T5 S5 — pending (requiere tabla nueva + migración)
- T6 S6 — pending
- T7 S7 — pending

## Log
L1 (2026-11-13) Pedido original del usuario: "Cambios que quiero que hagamos: ..." (ver S1-S7).
