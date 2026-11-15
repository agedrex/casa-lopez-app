# Ventas, transferencias y stock de producto terminado

Objective: close the product cycle (lote -> producto terminado -> transferencia a la tienda -> venta -> margen real). Branch: feat/ventas-stock (stacked on feat/cvu-fabrica-tienda, PR #41/#42). Delivery: ask-on-risk. Test runner: `uv run --directory backend pytest -q`; front `corepack pnpm lint && corepack pnpm build`.

## Specs

- S1 "ventas reales": tabla append-only `venta` (producto o Mercadería, fecha, unidades, precio unitario cobrado, canal opcional, nota). Carga MANUAL primero; importación después. SUPUESTO: la tienda hoy no tiene ventas cargadas en la app; validar cómo las registra.
- S2 "transferencia a la tienda": tabla append-only `transferencia` (producto, fecha, unidades) que congela el costo de fábrica y el precio de transferencia (con el margen) de ESE momento.
- S3 Stock derivado, nunca editado: fábrica = producido (lotes) - transferido; tienda = transferido - vendido. Mercadería: comprado - vendido.
- S4 Cada venta congela costo y precio de transferencia de ese momento para el margen real; no se recalculan con el dólar de hoy.
- S5 Margen real de fábrica, de tienda y consolidado por mes; el consolidado no suma dos veces el margen de transferencia. SUPUESTO: validar con el contador.
- S6 Pantallas admin: cargar ventas y transferencias, ver stock y margen real. El front no calcula plata.

## Tasks

- [x] T1 mapa de lotes/producción/stock existente (explorer, read-only)
- [x] T2 (S1-S4) modelos + migración 0022 + servicios + endpoints + tests
- [x] T3 (S5) margen real por mes + endpoint + tests
- [x] T4 (S6) pantallas
- [x] T5 verificación y PR

- Slice: PR #43 stacked on #42 (backend 284ac6d + front screen). Not rendered against the real API.

## Log

- L1 (2026-11-15) "que mas mejorarias del sistemas para que ya lleve el seguimiento total de todos los productos end-end y sea un sistema que realmente sirva para llevar los costos del negocio" -> propuesta aceptada: "okey, hagamos eso" (ventas reales y stock primero).
