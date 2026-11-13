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
- S8 Gerente: "el gerente solo pueda ver productos, modelos y todo lo que es el simulador de escenarios" (solo lectura; sin Panel, Lotes, Formularios, Cueros, Proveedores ni Talleres). Riesgo item 2 (permisos): commit propio + verificador independiente.

## Tasks
- T1 S1 — inline — done (sin commit aún)
- T2 S2 — inline — done
- T3 S3 — delegated (worker, rama feature/modelo-taller) — done (pytest ok con Postgres local, lint ok, build ok; pantalla sin probar en navegador)
- T4 S4 — delegated (worker, rama feature/lotes-buscador) — done (pytest ok, lint ok, build ok; buscador sin probar en navegador)
- T5 S5 — pending (requiere tabla nueva + migración)
- T6 S6 — delegated (worker) — done (pytest 2261 ok, lint ok, build ok; grilla sin probar en navegador)
- T7 S7 — pending
- T8 S8 — pending (esperar al worker de T6: ambos tocan api.py/permisos)


## Delivery
Estrategia: stacked-to-main (elegida 2026-11-13). Slice 1 = d1dcae6 + a0a30e4 (T1, T2, T6; ~1200 líneas, por encima de 400 porque T6 es una unidad coherente). Próximos slices: T8 (permisos, commit propio), luego T3, T4, T5, T7.

## Log
L1 (2026-11-13) Pedido original del usuario: "Cambios que quiero que hagamos: ..." (ver S1-S7).
L2 (2026-11-13) Usuario: "Una cosa más que quisiera ... es que el gerente solo pueda ver productos, modelos y todo lo que es el simulador de escenarios". Usuario confirmó ("si") grilla de Productos editable con Margen % y Precio final.
L3 (2026-11-13) S4: el form de "Nuevo lote" busca en toda la base (server action `buscarProductos` -> `GET /productos?q=`, hasta 20 resultados, solo admin, sin costos ni precios), permite agregar varios productos con cantidad por fila y elige "Fábrica (en casa)" (INTERNA) o un taller (EXTERNA) en un solo select. Sin cambios de backend: el endpoint ya existía y entra en `LECTURA_GENERAL`. SUPUESTO: validar con el usuario que "Fábrica" = `INTERNA` sin persona (la persona sigue opcional en "Más opciones"). El alta de productos a un lote ya creado (`/fabricacion/[codigo]`) sigue con el datalist de 500 productos.
L4 (2026-11-13) S3: un solo alta de modelo (`POST /productos/nuevo`: nombre + categoría + tamaño + notas, sin consumos) crea el modelo y su formulario `ENVIADO`; la nota se copia a la hoja del taller. La ficha del modelo lista sus formularios (`GET /formularios?modelo=`). Sin migración: `modelo.nota` ya existía. `POST /modelos` (con consumos) queda en la API sin pantalla. SUPUESTO: validar que la categoría sea obligatoria.
