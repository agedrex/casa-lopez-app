# La fase de revisión

## Propósito

Correr una revisión completa, aislada del trabajo de implementación día a día. La revisión chequea
el cambio contra el work order, sus requirements y blueprints enlazados, los contratos del repo, los
tests y el estado del build — y devuelve un veredicto único.

**La revisión es por lote**, no work order por work order: se manda el diff completo de un conjunto
de WOs ejecutados a un review delegate (`wo-reviewer`), que lee y verifica pero **no modifica
código**.

## Cómo se escala el diff

Se revisa **solo el trabajo del rango que corresponde**: desde el merge-base del lote hasta la punta
de cada branch de ejecutor, contra la branch del lote a la que van a integrarse. Si el lote tiene
varios WOs en paralelo (varios worktrees), cada uno aporta su propio rango de commits — el reviewer
recibe el scope completo del lote de una vez, no WO por WO.

## Dimensiones de revisión

Cada finding se etiqueta con la dimensión a la que pertenece:

- **Requirements** — los AC de los work orders del lote, uno por uno: ¿cada criterio de aceptación
  queda satisfecho, o explícitamente fuera de alcance con motivo?
- **Blueprints** — ¿los componentes, contratos, flujo de datos y límites coinciden con lo que
  describen los blueprints enlazados?
- **Contratos del repo** (no negociables, ver `CLAUDE.md`):
  - **Una sola capa de servicios** — nada de lógica de negocio en un router o en una tool MCP que no
    esté también en `app/services/`.
  - **Toda mutación audita** (`services/audit.record_audit`) y, si cambia contenido, versiona
    (`record_version`).
  - **Nada se borra**, se archiva.
  - **Referencias legibles**, nunca UUIDs, en toda superficie pública.
  - **Respuestas del MCP compactas** — sin dato, sin campo.
  - **Errores de dominio** de `app/errors.py` en los servicios, nunca `HTTPException`.
- **Convenciones** — texto visible en español; migraciones Alembic revisadas a mano (autogenerate
  no ve `CHECK` en tablas existentes ni defaults para filas ya cargadas); Tailwind v4 sin `@apply`
  de clases propias, solo utilidades.
- **Tests y build** — ¿los tests nuevos tienen evidencia de rojo real? ¿Corre el build de frontend
  (`tsc -b && npm run build`)? Documentar fallas preexistentes de baseline en vez de esconderlas.
- **Correctness** — bugs reales con **escenario de fallo concreto**: qué entrada, qué estado,
  qué sale mal. Nada de comentarios de estilo disfrazados de bug.

## Cómo se registra

Cada finding: severidad (`blocking` o `advisory`), archivo o área, dimensión, y el problema con su
escenario de fallo. El reviewer es escéptico de verdad, pero no inventa: todo `blocking` necesita un
escenario reproducible, no una sospecha.

Formato de respuesta exacto del reviewer:

```
VEREDICTO: APPROVED | CHANGES_REQUESTED
FINDINGS:
- [blocking|advisory] archivo:línea — dimensión — problema concreto y escenario de fallo
(o "sin findings")
```

Al final, una línea de "Verificado sin findings: …" con lo que se revisó y quedó limpio — para que
quede constancia de que se miró, no solo de lo que falló.

## Qué pasa con el veredicto

- **`APPROVED`** — sin blocking findings: el lote sigue el flujo normal (el WO puede pasar de
  `in_review` a `completed`, según decida quien orquesta).
- **`CHANGES_REQUESTED`** — se corrige cada blocking, y se corre **otra ronda completa de revisión**
  (con el reviewer leyendo el diff actualizado, no solo el parche del fix).

Si un finding necesita criterio de producto o una decisión de negocio (no una corrección técnica),
no se itera solo: se corta el loop y se lleva la pregunta a quien pidió el trabajo.

## Reglas

- El review delegate no modifica código: si algo hay que arreglar, se lo devuelve al ejecutor o a
  quien orquesta.
- Cada ronda se agrega con `sf_dossier(action="update", expected_version=N,
  append_review="...")`, no reemplaza a la anterior — queda historial de qué se pidió y qué se
  corrigió. Una versión vieja obliga a releer y reconciliar.
- Un finding sin escenario de fallo no es `blocking`: a lo sumo es `advisory`.

## Fuente

Adaptación al español de `reference/plugin-8090/software-factory/execution/review-phase.md`, con las
dimensiones y el formato de veredicto reales de este repo en vez de los genéricos de 8090.
