# Cómo se escribe un requirement (FRD)

Un requirement (Feature Requirements Document, FRD) describe el sistema **desde afuera**: qué le
pasa hoy al usuario o al negocio, y qué tiene que ser observablemente cierto después. No dice cómo
se construye — eso es trabajo del blueprint.

Creá cada FRD de producto dentro de su Etapa (`sf_write(kind="requirement", doc_type="feature", stage=n, ...)` por MCP; `stage` es un entero). El FRD es un Document persistido, no un tipo de entidad adicional. Los documentos
fundacionales del proyecto pueden quedar sin Etapa. Un WO de otra Etapa puede enlazar este FRD
sin duplicarlo.

## Estructura

```markdown
## Problema / contexto

_Qué le pasa hoy, por qué duele, quién lo pide y cuándo. Uno o dos párrafos, sin implementación.
Si el pedido tiene fecha o viene de alguien puntual, van acá: "Pedido de Federico, 2026-09-08."_

## REQ-<PREFIX>-001 — Título del requirement

* **AC-<PREFIX>-001.1**: Cuando [condición], el sistema [comportamiento observable].
* **AC-<PREFIX>-001.2**: …

## REQ-<PREFIX>-002 — Título del requirement

* **AC-<PREFIX>-002.1**: …

## Decisiones abiertas

_Solo si hay algo sin cerrar antes de poder ejecutar. Si no hay nada abierto, la sección no va._
```

- El heading de cada requirement es `## REQ-<PREFIX>-NNN — Título`, con el em dash `—` y NNN de
  tres dígitos (`001`, `002`, …). `<PREFIX>` es un slug corto y estable del feature (`HORAS`,
  `ETAPAS`, `KIT`) — una vez elegido, no cambia.
- Cada criterio de aceptación es un bullet `* **AC-<PREFIX>-NNN.M**:` seguido de una frase
  testeable y observable. Formato recomendado: "Cuando [condición], el sistema [comportamiento]" —
  pero lo que importa es que se pueda convertir en un test o en una verificación manual sin
  ambigüedad, no la fórmula exacta.
- Un FRD puede tener uno o varios `REQ-`. Cada uno es una capacidad cohesiva y evaluable por
  separado. Si dos requirements se rompen sin el otro, son un solo requirement, no dos.

### Ejemplo real (recortado)

Ejemplo de criterio observable para un Work Order:

```markdown
## REQ-WO-001 — Registrar una entrega

* **AC-WO-001.1**: La Work Order se crea dentro de una Etapa y aparece en Backlog.
* **AC-WO-001.2**: Al pasar a Ready, aparece en Kanban sin perder su Etapa.
```

Notá lo que NO tiene: no dice en qué componente de React vive el formulario, ni el nombre de la
tabla donde se guarda. Eso es blueprint.

## Qué NO va en un requirement

- Nombres de clases, funciones, tablas, endpoints o componentes — eso es blueprint.
- Pasos de implementación ("primero migrar la tabla, después el endpoint").
- Repetir contenido que ya vive en otro FRD: si dos features comparten una regla, esa regla vive en
  un solo lugar y el otro FRD la referencia.

## IDs: se preservan una vez asignados

Un `REQ-<PREFIX>-NNN` o `AC-<PREFIX>-NNN.M` no se renumera ni se borra cuando cambia el texto: se
edita el contenido y el ID se mantiene. Los work orders y los blueprints citan estos IDs — cambiar
un número rompe esas referencias silenciosamente. Si un criterio deja de aplicar, se marca como tal
en el texto (o se archiva el documento entero); no se reordena la numeración de los que quedan.

## Idioma y formato

Todo en **español**. Nada de `## Overview`, `## Requirements`, `### REQ-X: Name` ni
"As a [role], I want to…" — ese es el formato de 8090 en inglés
(`reference/plugin-8090/software-factory/guides/requirements-writing-guide.md`), y no es el
nuestro. Nuestro formato es el de arriba, punto.

## El template del proyecto manda

El esqueleto exacto con el que nace un FRD nuevo vive en
`projects.settings.templates.requirement_feature` (dato del proyecto, editable desde la web). Esta
guía explica el formato y el porqué; si el template del proyecto difiere en algún detalle menor de
redacción, gana el template — la regla que no cede es la de fondo: español, `## REQ-<PREFIX>-NNN`,
`* **AC-<PREFIX>-NNN.M**`, sin implementación.
