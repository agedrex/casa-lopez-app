# Mejoras desde el QA de staging (2026-11-17)
Plan para corregir lo que encontró la prueba manual (admin + taller) del flujo modelo → lote → taller, en carriles paralelos con worktrees.

## Specs
- S1: "modelo vacío se puede validar; hoja vacía se puede enviar/validar; sin tope en consumos (5000 m²)"
- S2: "stock de cuero informativo, sin reserva ni descuento (dos lotes "alcanzan" con los mismos 3 m²)"
- S3: "lote salta estados (Planificada→Lista/Cerrada), taller pasa a Cortada/Lista sin cuero"
- S4: "entrega anterior al envío y fechas 2030 aceptadas; lote cerrado admite agregar productos"
- S5: "producto duplicado modelo+cuero+color permitido"
- S6: "fechas/horas en UTC (18/11 02:11 siendo 17/11 23:11 ART)"
- S7: "mensajes genéricos con nombre de campo (cuero_m2_por_unidad)"
- S8: "mismo cuero+color+fecha no admite 2 pedidos"
- S9: "que luego todo se vaya al merge de main y staging para volver a probarlo"

Fuente: memoria Engram #1201. S2, S5, S8 y los topes de S1/S4 son decisiones de producto: no se implementan hasta que Agustin/Robert las confirmen.

## Carriles (un worktree por carril, base = main después de T0)
| Carril | Worktree / rama | Cubre | Toca (superficie) |
|---|---|---|---|
| A. Lote y estados | `...-worktrees/qa-lote-estados` · `fix/qa-lote-estados` | S3, S4 | `backend/src/backend/lote_estados.py`, endpoints de `/ordenes`, `front/app/(app)/fabricacion`, `taller` |
| B. Cuero y stock | `qa-cuero-reserva` · `feat/qa-cuero-reserva` | S2 | resumen de cuero, `pieza_cuero`/`movimiento_cuero`; **depende de A** y de decisión de producto |
| C. Modelos y formularios | `qa-modelos-validacion` · `fix/qa-modelos-validacion` | S1, S5 | `formulario.py`, validación de modelo, `productos`, `taller/modelos` |
| D. Fechas y mensajes | `qa-fechas-mensajes` · `fix/qa-fechas-mensajes` | S6, S7, S8 | formateo de fechas en `front/lib`, manejo de errores del front, pedidos |

A, C y D son independientes (superficies disjuntas) y corren a la vez. B espera a A porque comparten lógica de lotes.

## Tasks
- [x] T0 (S9) base: dejar `feat/lanzamiento-listo` (11 commits, aún NO en main) en main y verificar que staging despliega; recién ahí crear los worktrees. Limpiar los 5 worktrees viejos ya mergeados.
- [x] T1 (PR #49) (S3, S4) carril A: transiciones válidas en orden, taller no avanza sin cuero, lote cerrado no admite productos, entrega >= envío y rango de fechas razonable
- [x] T2 (PR #50) (S1, S5) carril C: no validar/enviar modelo u hoja vacía, tope en consumos, duplicado modelo+cuero+color
- [x] T3 (PR #48) (S6, S7, S8) carril D: mostrar fechas en America/Argentina/Buenos_Aires, mensajes legibles por campo, error claro en pedido repetido
- [x] T4 (PR #51) (S2) carril B: reserva/descuento de cuero al planificar un lote
- [x] T5 mergeados en main, staging SUCCESS 2026-11-17 23:59 (S9) integración: merge por PR de cada carril a main (orden A, C, D, B), staging despliega con CI verde
- [ ] T6 (S9) re-QA en staging (admin + taller) repitiendo cada hallazgo y borrando los datos de prueba (MOD-0003..0006, PRD-0013..0015, LOT-0002..0005, PED-0003, taller.qa@example.com)

## Log
L1: pedido del usuario 2026-11-17: "Basado en los hallazgos de tu prueba cua que hiciste en la anterior sesión Quiero quedarme con un plan para mejorar la aplicación basado en eso. Crear más diferentes work trees dependiendo de qué es lo que va a hacer cada gente Que vidas bien el trabajo para que cada uno se encargue de algo específico de ser necesario. Y que luego todo se vaya al merge de main y staging para volver a probarlo"
L2: SUPUESTO: el QA corrió contra staging = main, que no tiene `feat/lanzamiento-listo`; algunos hallazgos de estados (S3) pueden estar ya parcialmente cubiertos ahí (`taller-estados`). Verificar en T0 antes de tocar el carril A.
