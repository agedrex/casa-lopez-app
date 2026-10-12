# Cómo se escribe un work order

Un work order (WO) es la unidad de entrega: implementa lo que un requirement pide, siguiendo lo que
un blueprint especifica. Un buen WO conecta el contexto correcto, dice qué hay que hacer, dice qué
queda afuera, y deja claro cómo se verifica que está terminado.

**No repitas lo que ya dicen los requirements y blueprints conectados: enlazalos.** El ejecutor los
va a leer directo por MCP (`sf_context`). El checklist, contexto, plan y review log de ejecución
viven en un dossier persistido independiente (`sf_dossier`), no en la descripción del WO. El WO describe la responsabilidad de entrega puntual de
este work order, no vuelve a explicar el problema de negocio ni la arquitectura entera.

## Las seis secciones, en este orden

```markdown
## Contexto

_Los REQ/AC y el blueprint que este WO satisface, citados por referencia (@FRD-X, @BP-Y, REQ-X-001,
AC-X-001.1). Qué pasa hoy y qué falta. NO repitas la prosa del FRD/blueprint — el ejecutor los lee
directo por MCP._

## Caso de uso

_Quién, en qué situación, hace qué y qué obtiene. Una historia corta y concreta: el antes y el
después. Si el pedido llegó citado de un tercero (Federico, un cliente), el texto original va acá,
no parafraseado._

## Alcance

1. **Punto (AC-XXX-001.1)**: qué se construye, con el AC que satisface entre paréntesis cuando
   aplica.
2. …

## Criterios de aceptación

* **Dado** [estado inicial], **cuando** [acción], **entonces** [resultado observable].
  (uno por comportamiento nuevo; citá el `AC-XXX-NNN.M` del FRD cuando exista uno equivalente)

## Entrega

_Qué tiene que estar en verde para darlo por hecho: qué se construye, qué tests con evidencia de
rojo, qué verificación (build, migración probada, greps, etc.)._

## Fuera de alcance

_Qué queda excluido o diferido, y de qué WO vecino es responsabilidad (si se sabe)._
```

Qué va en cada sección y qué NO:

- **Contexto**: referencias, no prosa copiada. Si te encontrás copiando párrafos enteros del FRD o
  el blueprint, es señal de que el WO está mal armado — enlazá y listo.
- **Caso de uso**: el "por qué le importa a alguien" de este WO puntual. No es el "Problema /
  contexto" del FRD (eso ya está ahí, un nivel arriba) — es la escena concreta que este WO resuelve.
- **Alcance**: responsabilidades de este WO, no una lista exhaustiva de líneas de código. Suficiente
  para que el ejecutor sepa qué construir sin adivinar los límites.
- **Criterios de aceptación**: tienen que ser verificables — cada uno se convierte en un test o en
  un chequeo manual concreto. No repitas los AC del FRD palabra por palabra si ya cubre lo mismo:
  citalos.
- **Entrega**: la definición operativa de "terminado" para este WO — no confundir con "Criterios de
  aceptación" (el qué) ni con "Fuera de alcance" (los límites).
- **Fuera de alcance**: previene el scope creep. Si sabés que "X es responsabilidad de WO-Y", decilo
  acá explícito.

Esto **reemplaza** al formato en inglés de la guía original de 8090
(`reference/plugin-8090/software-factory/guides/work-order-writing-guide.md`) — no lo complementa.
Ningún work order de este repo usa esos headings en inglés.

## Las reglas de creación

### Etapa

Un work order **nace dentro de una Etapa** (`stage: n` tanto en MCP como en REST; la referencia legible es `E<n>`).
La Etapa reúne los FRDs, Blueprints y WOs de una entrega. Enlazá los documentos fuente
por referencia; pueden estar en otra Etapa si el trabajo los reutiliza.

### Puntos, del 1 al 10

Al crear un WO se le puede (y conviene) asignar `estimate_points`: un entero de **1 a 10**, tamaño
relativo del esfuerzo. `null` significa "todavía no lo estimamos" — nunca se completa un hueco
inventando un número. La validación rechaza `0`, valores fuera de rango, y booleanos disfrazados de
entero (`true` no es `1`).

**Los puntos NO se convierten a horas ni a dinero (ni a plata).** Conviven con las horas estimadas
(`estimated_hours`) sin reemplazarlas — son dos mediciones distintas: una de tamaño relativo, otra
de tiempo calendario. La misma regla vale para el costo de tokens: sin precio cargado, el costo es
desconocido, nunca cero (ver ADR-004 del blueprint del kit de trabajo, `BP-SKILL-KIT-TRABAJO-EQUIPO`).

### Origen: planificado o emergente

Todo WO queda marcado `origin: planificado` o `origin: emergente`.

- **Planificado**: existía en el plan cuando se cerró la planificación de la Etapa
  (`planning_closed_at` de la Etapa, seteado explícitamente).
- **Emergente**: se creó después de ese cierre — apareció en el camino, no estaba previsto.

Si no se especifica `origin` al crear, el servicio lo infiere solo: `emergente` si la Etapa ya tiene
`planning_closed_at`, `planificado` si no. **Cerrar la planificación de una Etapa** es el momento en
que decís "esto es lo que vamos a hacer en esta Etapa" — todo lo que se cree después ahí adentro es,
por definición, trabajo que no estaba anticipado. Sirve para distinguir un proyecto que tardó de más
porque el trabajo real fue más grande, de uno que tardó de más solo porque costó más ejecutarlo.

### Fechas reales

`started_at` se pisa solo la primera vez que el WO pasa a `in_progress`; `completed_at`, al llegar
a `completed` (Done) o `released`, y se conserva al pasar de Done a Released. Da el tiempo de ciclo real — distinto del tiempo transcurrido desde que
se creó, que puede incluir semanas en `backlog`.

## Secciones obligatorias (disciplina del proyecto)

Un proyecto puede exigir que ciertas secciones estén presentes y no vacías al crear o editar un WO
— por default, **"Caso de uso"** y **"Criterios de aceptación"**
(`wo_required_sections` en `projects.settings`; lista vacía apaga la regla). No es una sugerencia:
si falta una sección exigida, la escritura falla.

## El template del proyecto manda

El esqueleto exacto de un work order nuevo (los headings, el orden, los placeholders en cursiva)
llega solo, al crear el WO, desde `projects.settings.templates.work_order` — un dato del proyecto,
editable desde la web. **Esta guía explica el formato y por qué existe cada regla; no lo
reemplaza** (ADR-003 del blueprint del kit de trabajo). Si alguna vez el template del proyecto y
esta guía no coinciden en un detalle de redacción, gana el template; la estructura de fondo (las
seis secciones, en ese orden, en español) es la que no se negocia.
