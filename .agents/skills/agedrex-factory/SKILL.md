---
name: agedrex-factory
description: "El método de trabajo de Agedrex Factory: cómo se organizan Etapas, FRDs, Blueprints y Work Orders, y cómo se ejecuta un Work Order por MCP."
---

# Agedrex Factory

Agedrex Factory es el reemplazo self-hosted de 8090 Software Factory: la base de Requirements
(FRDs), Blueprints y Work Orders de los proyectos de Agedrex, servida por su propio backend y su
propio servidor MCP. Esta skill es el método de la casa — leela primero, después seguí la guía o el
proceso de ejecución que corresponda.

**Fuente de autoridad: las convenciones de La Fábrica, no los modelos de 8090 ni un harness
externo.** Para una entrega, empezá por la Etapa (`sf_stage`), después el FRD (qué hace falta y
por qué), el Blueprint (cómo se construye) y el Work Order (qué se entrega). No se codea contra un pedido suelto, un mensaje de Slack o un "total,
es chico" — si no tiene requirement, blueprint y work order, no está listo para ejecutarse. Un
pedido chico puede tener un FRD y un blueprint cortos, pero los tres registros existen igual.
Los documentos fundacionales del proyecto pueden estar fuera de una Etapa.

## Las tres clases de registro

- **Requirements** (FRDs): describen el sistema desde afuera — qué problema resuelve y qué tiene
  que ser observablemente cierto. Un FRD agrupa uno o más `REQ-<PREFIX>-NNN`, cada uno con sus
  criterios de aceptación `AC-<PREFIX>-NNN.M`.
- **Blueprints**: describen el sistema desde adentro — cómo está estructurado y compuesto para
  que los requirements se cumplan. Container, Component o Feature Blueprint, según lo que
  documentan (ver `guides/blueprints.md`).
- **Work Orders**: la unidad de entrega. Un WO enlaza los REQ/AC y los blueprints que satisface,
  nace **dentro de una Etapa**, se estima en **puntos** y queda **planificado** o **emergente**. No
  repite lo que ya dicen sus documentos fuente: los referencia.

Todo se direcciona por referencias legibles — `WO-83`, `FRD-FICHAOP`, `BP-BACKEND-API`,
`E1` — nunca UUIDs. Es lo mismo que rige en el resto del repo (`CLAUDE.md`): referencias legibles en
toda superficie pública.

## Tabla de ruteo

| Si vas a… | Leé |
|---|---|
| Entender el recorrido completo de una Etapa, de FRD a entrega | [guides/flujo-de-trabajo.md](guides/flujo-de-trabajo.md) |
| Escribir o revisar un requirement (FRD) | [guides/requirements.md](guides/requirements.md) |
| Escribir o revisar un blueprint | [guides/blueprints.md](guides/blueprints.md) |
| Escribir o revisar un work order | [guides/work-orders.md](guides/work-orders.md) |
| Ejecutar un work order de punta a punta | [execution/ejecutar-wo.md](execution/ejecutar-wo.md) |
| Escribir el plan de implementación de un WO | [execution/plan-de-implementacion.md](execution/plan-de-implementacion.md) |
| Revisar un lote de work orders ya ejecutados | [execution/review.md](execution/review.md) |
| Registrar los tokens y el tiempo que costó un WO | [execution/registrar-runs.md](execution/registrar-runs.md) |
| Persistir checklist, contexto, plan y reviews del WO | [execution/dossier.md](execution/dossier.md) |
| Adaptar prácticas de análisis de producto | [references/product-analysis.md](references/product-analysis.md) |
| Empezar artefactos nuevos | [templates/feature-frd.md](templates/feature-frd.md), [templates/feature-blueprint.md](templates/feature-blueprint.md), [templates/work-order.md](templates/work-order.md) |

## Las reglas nuevas de la Fábrica (y por qué existen)

Esto es lo que la skill original de 8090 no sabía, porque 8090 no las tiene. Son reglas de esta
casa, y todo lo que se escribe y se ejecuta acá las respeta:

- **Una Etapa es un mini proyecto.** Contiene directamente FRDs, Blueprints y Work Orders. Crear
  la Etapa con `sf_stage` y pasar `stage: n` (entero, no `E<n>`) al crear documentos y WOs. Los documentos
  fundacionales pueden quedar a nivel de proyecto.
- **Backlog y Kanban son pasos separados.** Una WO nueva espera en Backlog; cuando se prioriza,
  pasa a Ready y aparece en Kanban. Cambiar de estado no cambia la Etapa ni sus vínculos.
- **Se estima en puntos, del 1 al 10.** Tamaño relativo, no horas ni plata (ver
  `guides/work-orders.md` y ADR-004 del blueprint del kit). `null` es "todavía no lo estimamos";
  nunca se inventa un valor para completar un hueco.
- **Se marca como planificado o emergente.** Planificado: estaba en el plan cuando se cerró la
  planificación de la Etapa. Emergente: apareció después. Sirve para saber si un proyecto tardó de
  más porque el trabajo real fue más grande, no solo porque costó más ejecutarlo.
- **Deja fechas reales.** `started_at` (primer pasaje a `in_progress`) y `completed_at` dan el
  tiempo de ciclo real de un WO, distinto del tiempo que pasó desde que se creó.
- **Al terminar, se registran los tokens y el tiempo del ejecutor y del reviewer.** Sin esto no hay
  forma de saber qué cuesta de verdad un work order ni de calibrar las estimaciones futuras. Ver
  `execution/registrar-runs.md`.

## Política de modelos

**El modelo grande orquesta y no ejecuta work orders inline.** La ejecución se delega a un agente
ejecutor según la dificultad del WO (`wo-executor-easy` / `-medium` / `-hard`, en `agents/`), y la
revisión es **por lote** — no work order por work order — con un reviewer (`wo-reviewer`) que lee y
verifica pero **no modifica código**. El detalle de cuándo delegar a cada nivel y cómo se arma un
lote de revisión está en `execution/ejecutar-wo.md`.

## Qué NO hace esta skill

- No reemplaza el template de work order del proyecto (`projects.settings.templates.work_order`):
  ese es el dato que manda al crear un WO. Esta skill explica el formato y por qué, no lo sustituye
  (ver ADR-003 en el blueprint del kit de trabajo).
- No incluye el hook `registrar_run.py` en sí — lo copia el empaquetador de la skill al armar el
  paquete final; acá solo se documenta cómo instalarlo y usarlo.
- No instala archivos automáticamente en ningún cliente ni reemplaza un workspace local:
  el ZIP distribuye esta skill y el hook bajo la raíz `agedrex-factory/`.
- No tiene una versión "genérica" para cualquier plataforma: es específica del MCP y del stack de
  La Fábrica.

---

Esta skill es la traducción y adaptación al método de Agedrex de la skill `software-factory` de
8090 Solutions Inc. (MIT, ver `LICENSE`), copiada de referencia en
`reference/plugin-8090/software-factory/`. Se conserva el esqueleto de ruteo y la licencia; todo el
contenido —idioma, formato de documentos, reglas de Etapas/puntos/origen/runs, nombres de tools MCP y
agentes— es el de esta casa.
