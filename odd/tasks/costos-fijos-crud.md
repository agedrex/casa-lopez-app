# Costos fijos: grilla simple con CRUD sin perder historia
Objetivo: registrar costos fijos más rápido, con menos texto, y poder crear, leer, editar y anular en la grilla. Rama: feature/costos-fijos-crud. Entrega: ask-on-risk. Tests: `uv run --directory backend pytest -q`, `cd front && corepack pnpm lint && corepack pnpm build`.

## Specs
- S1. "que la grilla se pueda actulizar": en la grilla de costos fijos se edita cualquier celda de una fila guardada (concepto, es de, categoría, monto, persona, nota), no solo las de hoy.
- S2. "tantos los datos de Costos Fijos y Variables sean CRUD": costos fijos tiene crear, leer, editar y borrar desde la grilla. Costos variables (precios de materiales y confección) quedan para la siguiente vuelta (decisión del usuario).
- S3. Editar y borrar sin perder historia (decisión del usuario): editar agrega una fila que reemplaza a la anterior; borrar marca la fila como anulada (columna `anulado`, migración 0009 con downgrade). Una fila anulada no cuenta en totales, listas, copiar mes ni exportación. Respeta reglas de oro 10 y 11.
- S4. "algo mas simple sin tanto texto": la pantalla pierde los párrafos explicativos y la sección de formulario suelto; queda período, filtro, totales y grilla. SUPUESTO: la grilla con «Gasto nuevo» reemplaza al formulario suelto.
- S5. Los totales los calcula solo el backend (regla 8).

## Tasks
- [x] T1 (S3) migración 0009 `anulado` + modelo + `_gastos_vigentes` + test. Ruta: inline. Risk item 1.
- [x] T2 (S1,S3) backend lote: editar persona/nota, `anulados`. Ruta: inline.
- [x] T3 (S1,S2,S4) grilla y pantalla: borrar fila, columnas editables, menos texto. Ruta: inline.
- [x] T4 docs: `docs/der-v3.md`, AGENTS.md.

## Log
- L1 (2026-11-11): "Vamos a mejorar como se hacen los registros en Costos Fijos y Variables. Quiero algo mas practico y que lo vayamos mejorando. Es muy complejo y necesto algo mas simple sin tanto texto y que la grilla se pueda actulizar y que tantos los datos de Costos Fijos y Variables sean CRUD"
- L2: costos variables = costos del producto (materiales y confección); se hacen después. Editar/borrar sin perder historia (opción recomendada).
- L3: worker de backend tardó por un bucle infinito en un test genérico de roles (ruta sin body + MagicMock + `_gasto_actual_de`). Se agregó un stub en test_api.py. Suite backend: 1889 pasaron, 299 saltados (integración sin Postgres).
