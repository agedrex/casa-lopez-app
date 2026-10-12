<!--lint disable strong-marker-->

# Log de revisión: {{LOTE_O_WORK_ORDER_REF}}

**Alcance:** {{LOTE_O_WORK_ORDER_REF}} — {{TITULO}}
**Iniciado (UTC):** {{INICIADO_EN}}

Persistí cada ronda mediante `sf_dossier(action="update", expected_version=N,
append_review="...")`. Cada ronda se agrega; no se pisan las anteriores. Este archivo local es
solo una plantilla opcional.

---

## Ronda 1

### Requirements

**Blocking:**

**Advisory:**

### Blueprints

**Blocking:**

**Advisory:**

### Contratos del repo

_Una sola capa de servicios, toda mutación audita, nada se borra, referencias legibles, respuestas
MCP compactas, errores de dominio en servicios._

**Blocking:**

**Advisory:**

### Convenciones

_Español visible, migraciones revisadas a mano, Tailwind v4 sin `@apply` de clases propias._

**Blocking:**

**Advisory:**

### Tests y build

**Comandos corridos:**

**Blocking:**

**Advisory:**

### Correctness

_Bugs reales con escenario de fallo concreto — nada de estilo._

**Blocking:**

**Advisory:**

### Veredicto de la ronda 1

- Total blocking:
- Total advisory:
- Archivos revisados:
- **Veredicto:** _APPROVED o CHANGES_REQUESTED_

---

<!-- Rondas siguientes: copiar la estructura de arriba e incrementar el número. -->
