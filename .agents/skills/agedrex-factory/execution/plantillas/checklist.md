<!--lint disable no-undefined-references strong-marker-->

# Checklist de ejecución: {{WORK_ORDER_REF}}

**Work order:** {{WORK_ORDER_REF}} — {{WORK_ORDER_TITLE}}
**Iniciado (UTC):** {{INICIADO_EN}}

Esta plantilla se guarda en `sf_dossier.checklist` para {{WORK_ORDER_REF}}; actualizala con
`expected_version` leído del dossier. No uses el archivo local como registro canónico.

Cada ítem termina en `[x]` o en `[SKIP]` con motivo. Un ítem sin marcar es una falla de ejecución,
no un TODO pendiente.

## Fase 1: Contexto

- [ ] `sf_board` / `sf_context(wo="{{WORK_ORDER_REF}}")` traído y leído completo
- [ ] Requirements enlazados leídos, con sus AC extraídos
- [ ] Blueprints enlazados leídos, con su ruta de arquitectura identificada (componentes,
      contratos, composición)
- [ ] Código análogo existente explorado antes de inventar estructura nueva
- [ ] **Certificación: Fase 1 completa. Se pasa a la Fase 2.**

## Fase 2: Plan e implementación

- [ ] Plan de implementación persistido en `sf_dossier.implementation_plan` (o su equivalente corto para
      un WO fácil) **antes** de tocar código
- [ ] Sección de testing del plan documentada
- [ ] Cambios implementados acotados al alcance del work order
- [ ] Tests agregados o actualizados para todo comportamiento nuevo
- [ ] Cada test nuevo con evidencia de rojo: se mutó el cambio propio, se confirmó que el test
      fallaba, se restauró, se confirmó que vuelve a pasar
- [ ] Documentación, fixtures, migraciones o config actualizados donde corresponda
- [ ] **Certificación: Fase 2 completa. Se pasa a la Fase 3.**

## Fase 3: Revisión y verificación

- [ ] Revisión corrida según `execution/review.md` (por lote), con veredicto
- [ ] Todos los criterios de aceptación del WO y de los requirements enlazados están satisfechos
- [ ] Arquitectura alineada con los blueprints enlazados, o el drift está documentado y aceptado
- [ ] Verificación exploratoria de comportamiento visible al usuario cuando aplica (no solo tests
      automáticos)
- [ ] El último veredicto de `sf_dossier.review_log` es `APPROVED`
- [ ] Run del ejecutor registrado (`sf_run` o registro manual, ver `execution/registrar-runs.md`)
- [ ] **Certificación: Fase 3 completa. Se pasa al cierre.**

## Cierre

- [ ] Todas las certificaciones de fase de arriba están completas
- [ ] El checklist está completo con evidencia
- [ ] `sf_dossier.review_log` está completo
- [ ] `sf_dossier.implementation_plan` refleja lo que efectivamente se implementó
- [ ] Todos los archivos previstos están en el working tree
- [ ] Handoff de Git según las instrucciones de quien pidió el trabajo (sin commit si lo prohibió)
- [ ] Estado del work order actualizado a `in_review` (`sf_update`)
