# De una Etapa a una entrega

La Etapa es un microproyecto dentro de un proyecto. Tiene un objetivo, fechas y plan propios, además de FRDs, Blueprints y Work Orders enlazados. El proyecto conserva el contexto fundacional compartido.

1. **Crear o elegir la Etapa** con `sf_stage` o desde la pantalla Etapas. Describir el resultado esperado antes de abrir trabajo.
2. **Escribir el FRD** en esa Etapa: `sf_write(kind="requirement", doc_type="feature", stage=N, ...)` persiste un Document (no una entidad nueva). Define problema, `REQ-*` y `AC-*` observables. La creación desde REST puede generar un Feature Blueprint vinculado por `satisfies`; `sf_write` MCP **no** lo genera automáticamente.
3. **Crear o completar el Blueprint**: si usaste `sf_write`, creá un Blueprint FEATURE en la misma Etapa y vinculalo al FRD con la operación de links disponible en REST; no afirmes que MCP enlazó automáticamente. Detallá componentes, contratos y decisiones que satisfacen el FRD. Leer los Component Blueprints que mencione, sin copiar sus definiciones.
4. **Crear las Work Orders** en la misma Etapa, enlazando el FRD y los Blueprints que usan. Cada WO delimita una entrega, sus criterios y lo que queda afuera. Si reutiliza un documento de otra Etapa, enlazarlo explícitamente.
5. **Priorizar en Backlog** y cerrar la planificación de la Etapa cuando el alcance previsto esté listo. Las WOs nuevas posteriores son emergentes.
6. **Ejecutar en Kanban** desde Ready hasta Done y Released. Usar `sf_context` para leer documentos fuente y `sf_dossier` para persistir checklist, contexto, plan y review log por WO. Verificar los `AC-*` antes de cerrar.

El estado de una WO determina si aparece en Backlog o Kanban; su `stage_id` determina a qué microproyecto pertenece. Ambos datos se conservan en REST y MCP.

Para los formatos exactos, seguir [requirements.md](requirements.md), [blueprints.md](blueprints.md) y [work-orders.md](work-orders.md). El flujo de producto también está resumido en `docs/FLUJO_DE_TRABAJO.md` del repositorio.
