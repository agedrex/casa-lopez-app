# Ejecutar un work order

## Política de modelos: orquestar no es ejecutar

**El modelo grande de la sesión abierta orquesta y no ejecuta work orders inline.** Cuando hay un WO
para implementar, no se codea en la sesión principal: se delega a un agente ejecutor, elegido según
la dificultad del WO:

| Dificultad | Agente | Cuándo |
|---|---|---|
| Fácil | `wo-executor-easy` | Cambio mecánico y bien especificado: un campo de punta a punta, un endpoint espejo, copy/UI menor, config, docs, scripts. |
| Media | `wo-executor-medium` | El default para la mayoría de los WOs: implementación acotada con blueprint claro, 2-6 archivos, UI compleja, servicio nuevo. |
| Difícil | `wo-executor-hard` | Migración de esquema con datos existentes, cambio que atraviesa servicio + REST + MCP + tests a la vez, regla de validación con impacto en toda la suite, o diseño abierto que el blueprint no resolvió. |

Si el orquestador autoriza aislamiento, el ejecutor puede trabajar en un **worktree git aislado**; recibe el WO
completo en el prompt (alcance, requirements, blueprints) y devuelve al orquestador: branch, path
del worktree, archivos tocados, resultados de verificación, decisiones y limitaciones. El
orquestador no vuelve a leer el diff línea por línea antes de mandarlo a revisión — para eso está el
paso de review.

**La revisión es por lote, no work order por work order.** Después de ejecutar varios WOs (un
"lote"), se manda el rango de commits/diff completo a `wo-reviewer`, que lee, corre verificaciones
de solo lectura y devuelve un veredicto único para el lote. El reviewer nunca modifica código.

## El flujo sobre el MCP

Nombres reales de las tools del servidor MCP de la Fábrica:

1. **`sf_board(project=?)`** — abre la sesión: panorama del proyecto (Etapas, WOs por estado, en
   curso, próximos, actividad reciente). Es el primer llamado del día, no por WO.
2. **`sf_context(wo="WO-N", project=?)`** — trae en una sola llamada el WO completo (Contexto, Caso
   de uso, Alcance, Criterios de aceptación, Entrega, Fuera de alcance), los REQ/AC que le tocan y
   las secciones relevantes de sus blueprints. Reemplaza las 5-6 llamadas sueltas del proceso
   original de 8090. Si algo viene recortado (`truncated: true`), `sf_read(refs=[...], project=?)`
   trae el documento completo.
3. **`sf_dossier(wo="WO-N", action="read", project=?)`** — leer el dossier persistido o crearlo
   una vez con `action="create"`. Guardar checklist, contexto y plan mediante
   `action="update", expected_version=N`. Ver [dossier.md](dossier.md).
4. **`sf_update(refs=["WO-N"], status="in_progress", project=?)`** — recién ahí arranca la
   implementación. No se toca código con el WO todavía en `backlog` o `ready`.
5. **Implementar solo el alcance del WO.** Ver `plan-de-implementacion.md` para cómo se planea antes
   de tocar código.
6. **Tests con evidencia de rojo** por cada comportamiento nuevo: mutás tu propio cambio, confirmás
   que el test falla, restaurás, confirmás que vuelve a pasar. Sin esto, un test que nunca pudo
   fallar no prueba nada.
7. **`sf_run(...)`** (o el registro manual del run — ver `registrar-runs.md`) — se registran los
   tokens y la duración del ejecutor antes de pasar a revisión. Sin esto no hay forma de calibrar
   estimaciones futuras.
8. **`sf_update(refs=["WO-N"], status="in_review", project=?)`** — recién acá, no antes.
9. Si hay algo que contar que no es un campo estructurado (una decisión, un hallazgo, la entrega
   real) — `sf_comment(action="add", ref="WO-N", body="...", project=?)`. `sf_update` no edita texto
   libre del WO.

Otras tools disponibles cuando hacen falta: `sf_read` (leer por referencia, con `mode="outline"`
para estructura sin texto, o `section=` para una sección puntual), `sf_search` (buscar por texto),
`sf_write` (crear o reemplazar contenido de un documento/WO), `sf_history` (versiones anteriores).

## Protocolo de checklist (heredado de 8090, con nuestras reglas)

Persistí cada transición en el campo `checklist` del dossier con la versión vigente. El archivo
local de plantilla no reemplaza este registro MCP.

Cada fase de ejecución termina en una certificación explícita, y **cada ítem del checklist termina
en `[x]` o en `[SKIP]` con motivo** — nunca queda sin marcar:

```markdown
- [SKIP] Migración probada con downgrade
  Motivo: este WO no toca el esquema.
```

Un ítem sin marcar es una falla de ejecución, no un TODO implícito. Fases típicas: (1) contexto —
leer WO, REQ/AC, blueprints, código análogo existente; (2) plan e implementación — el plan escrito
antes de tocar código, cambios acotados al alcance, tests con evidencia de rojo; (3) revisión y
verificación — veredicto de review, criterios de aceptación cumplidos, build/tests en verde.

## Handoff de git: lo dirige quien pide

**El handoff de control de versiones lo decide quien pidió el trabajo, no el ejecutor por su
cuenta.** No asumir commit, push, PR, merge ni worktree si el pedido los prohíbe o reserva al
orquestador.

## Reglas duras que no dependen de la dificultad del WO

- Todo texto visible al usuario en **español**; identificadores de código en inglés.
- Una sola capa de servicios: REST, MCP e importador llaman a los mismos `app/services/`. Los
  servicios levantan errores de dominio (`app/errors.py`), nunca `HTTPException`.
- Toda mutación audita (`services/audit.record_audit`) y, si cambia contenido, versiona
  (`record_version`). Nada se borra: se archiva.
- Referencias legibles en toda superficie pública — nunca UUIDs.
- Respuestas del MCP compactas: sin dato, sin campo.
- Nunca: pushear a remoto sin que lo pidan, tocar producción, tocar archivos marcados como ajenos en
  el prompt del WO.

El detalle operativo de cómo correr tests dirigidos, migraciones y build en este repo puntual lo
completa el `CLAUDE.md` del proyecto y el prompt del ejecutor — no esta skill, que es portable entre
proyectos gestionados por la Fábrica.
