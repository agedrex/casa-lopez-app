# Grillas de costos fijos y variables por modelo
Objetivo: grillas editables en lote (estilo planilla) para consumos por modelo y costos fijos del mes.
Rama: feat/grillas-costos · Entrega: ask-on-risk · Runner: `uv run --directory backend pytest -q`; `cd front && corepack pnpm lint && corepack pnpm build`

## Specs
- S1. Grilla de modelos en `/admin/modelos`: una fila por modelo con cuero, forro, flex, goma EVA, herrajes USD, hilo/cemento, confección estimada, horas y origen; edición en la celda; un solo "Guardar cambios" que envía solo lo modificado.
- S2. Filas con consumo faltante (NULL) resaltadas y filtro "Incompletos".
- S3. Guardar consumos desde la grilla mantiene la regla actual: resetea `validado` y deja log (quién, anterior, nuevo).
- S4. Grilla de costos fijos en `/costos-fijos`: concepto, área, categoría y monto editables; totales fábrica/tienda; agregar fila; copiar mes anterior visible.
- S5. Corregir un gasto sigue creando una fila nueva con `reemplaza_a_id` (no se pisa la anterior).
- S6. Endpoints por lote atómicos (todo o nada), solo admin, sin migración, sin tocar el motor.
- Supuesto: pegar desde Excel se ofrece como mejora de S1 si entra en el slice.

## Tasks
- T1 (S3,S6) Backend lote de consumos + tests · inline · hecho (backend)
- T2 (S5,S6) Backend lote de costos fijos + tests · inline · hecho (backend)
- T3 (S1,S2) Front grilla de modelos · inline · pendiente
- T4 (S4) Front grilla de costos fijos · inline · pendiente

## Log
- L1 (2026-11-11): "quiero que mejoremos las secciones donde se cargan los costos fijos y variables de cada uno, tiene que ser una grilla con un menu mucho mas facil de subir y mantener y con datos mas concretos y faciles de manejar"
- L2: Alcance variables = por producto/modelo (elegido por el usuario). "si seguimos": editar consumos desde la grilla sigue quitando `validado`.
