# Pedidos de proveedor: materiales recibidos, presentación y precio unitario
Objective: tanda 3, paso 1. Branch: main. Delivery: ask-on-risk. Runner: `uv run --directory backend pytest -q` (con `TEST_DATABASE_URL` a una Postgres descartable); front: `cd front && corepack pnpm lint && corepack pnpm exec tsc --noEmit && corepack pnpm build`.

## Specs
- S1: "cuando se compra a algún proveedor [...] esos datos se llenen desde el proveedor [...] Una vez que se registra un nuevo pedido que llega de algún proveedor, se debieran registrar qué materiales llegaron, cómo llegaron y sus unidades." Pedido (`PED-nnnn`) en la ficha del proveedor: fecha de recepción, remito/factura (texto opcional), documento ya subido (opcional), nota; y líneas: material, cantidad de presentaciones, presentación (texto: CARRETE, CAJA, ROLLO, UNIDAD...), contenido por presentación (en la unidad de consumo del material), precio por presentación, moneda, iva_incluido.
- S2: Al guardar el pedido, cada línea crea el precio del material: precio unitario = precio por presentación / contenido por presentación, en la unidad de consumo del material, `vigente_desde` = fecha de recepción, `proveedor_id` = el proveedor. Se reutiliza `servicios.crear_precio` (misma regla: unidad del precio = unidad de consumo; un precio por material + color + fecha). Todo el pedido es atómico: si una línea falla (por ejemplo ya hay precio de ese material en esa fecha), no se guarda nada y el error dice cuál.
- S3: Los pedidos solo se agregan: no se editan ni se borran (una corrección es un pedido nuevo). La línea guarda el id del precio que creó.
- S4: La lista de unidades cerradas agrega `m` (metro) a `UNITS` y a los CHECK de `material.unidad_de_consumo` y `precio_material.unidad_del_precio` (migración 0018, con downgrade).
- S5: Solo `admin` registra pedidos; `admin` y `gerente` los leen (SUPUESTO: validar). El `taller` no los ve.
- Supuestos (SUPUESTO, validar): el precio unitario se guarda con la precisión de `money()` (4 decimales); sin stock de insumos; sin OCR que precargue el pedido.
- Fuera de esta tanda: `modelo_insumo` y el motor (paso 2), stock.

## Tasks
- T1 (S1-S5) backend: migración 0018, modelos, servicio, API, tests, docs. Route: delegated (context backstop). DONE (dba3d68; suite 2576 passed, 6 skipped).
- T2 (S1, S5) front: formulario de pedido y lista en la ficha del proveedor. Route: delegated, después de T1. DONE (lint, tsc, build, 38/38 tests front; sin prueba en navegador).

## Log
- L1 (2026-11-13): "cuando se compra a algún proveedor [...] esos datos se llenen desde el proveedor o zonas que se compran, desde la capa o parte de proveedores. Una vez que se hace o se registra un nuevo pedido que llega de algún proveedor, se debieran registrar qué materiales llegaron, cómo llegaron y sus unidades." Plan de dos pasos aprobado con "si" (paso 1 ahora).
- L2 (2026-11-13): parent spot check: lint, tsc y tests front 38/38 limpios. El gerente no abre la ficha del proveedor (`requireRole("admin")`), así que hoy solo el admin ve los pedidos.
