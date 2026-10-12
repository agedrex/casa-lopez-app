# Cómo se escribe un blueprint

Los requirements dicen qué tiene que ser cierto; los blueprints dicen **cómo** está (o va a estar)
estructurado el sistema para que sea cierto. Un blueprint es un diagrama escrito: los bloques
`component` son nodos, los párrafos de relación son las flechas entre ellos.

Asigná el Blueprint a la Etapa que lo entrega (`stage: n`, entero, por MCP). El Feature Blueprint generado junto al FRD desde REST hereda su Etapa; `sf_write` MCP no genera
ni enlaza un companion automáticamente. Si trabajás solo por MCP, creá el Blueprint FEATURE con
`sf_write` y conservá el vínculo `satisfies` mediante REST cuando corresponda. Otras Etapas pueden reutilizarlo por referencia.

## Las tres clases

- **Container Blueprint**: un contenedor C4 — una unidad desplegable o corrible por separado (la
  API, el frontend, un worker). Documenta stack, arranque, límites de entrada/salida.
- **Component Blueprint**: una capacidad reusable — servicios, hooks, providers, algo que dos o más
  features van a necesitar. Agnóstico de feature. No se crea para un helper de una sola feature.
- **Feature Blueprint**: compone Component Blueprints existentes + componentes propios de una
  feature puntual para satisfacer un FRD. Es el que más se escribe en el día a día.

Flujo esperado: los Container Blueprints ponen la base de runtime, los Component Blueprints
definen capacidades reusables sobre esa base, y los Feature Blueprints componen esas capacidades
para satisfacer un FRD concreto.

## Bloques `component`

```markdown
​```component
name: NombreDelComponente
container: API Backend (FastAPI + MCP)
responsibilities:
	- Responsabilidad concreta, una por línea
	- Puede mencionar otros componentes o elementos con backticks
​```
```

- `name` en **PascalCase**, igual al identificador real en el código (o al que va a tener).
- `container` nombra el contenedor C4 donde vive; varios separados por coma si aplica.
- `responsibilities` son bullets `-` con **tabulación** (no espacios) antes del guion.

Un párrafo de relación entre dos componentes: los menciona a ambos temprano, dice quién llama a
quién y con qué datos, y por qué existe esa interacción. Una relación por párrafo, 2-4 oraciones.
No hace falta el párrafo si la adyacencia ya deja clara la dirección y el motivo.

## Secciones obligatorias por categoría

**Feature Blueprint** (la que más se usa):

1. `## Feature Summary` — arranca siempre con **"Satisface a @<FRD>: …"**, seguido de 1-2 oraciones
   sobre qué habilita la feature.
2. `## Component Blueprint Composition` — qué Component Blueprints usa esta feature y cómo (no los
   redefine — el componente ya está descrito en su propio blueprint).
3. `## Feature-Specific Components` — bloques `component` completos para lo que existe solo por
   esta feature (paneles, servicios, hooks propios).
4. `## System Contracts` — ver abajo.
5. `## Architecture Decision Records` — ver abajo.

**Component Blueprint**: `## Capability Summary` (2-3 oraciones), `## Core Components` (los
bloques), `## System Contracts`, `## Architecture Decision Records`.

**Container Blueprint**: `## Container Summary`, `## Infrastructure`, `## Entry Points and
Boundaries`, `## System Contracts`, `## Architecture Decision Records`.

## `System Contracts`

- `### Key Contracts` — invariantes, idempotencia, orden, consistencia, qué garantiza el sistema
  pase lo que pase (ejemplo real: "Nada se inventa: un run cuyo consumo real no se midió no se
  carga").
- `### Integration Contracts` — endpoints, payloads, eventos concretos que cruzan un límite. Con el
  detalle real: método, ruta, forma del body, códigos de estado.
- `### Integration Boundaries` (opcional) — de quién es cada pedazo, cuando la separación de
  responsabilidades no es obvia por sí sola.

## `Architecture Decision Records`

Una por decisión no obvia, numeradas secuencialmente dentro del blueprint:

```markdown
### ADR-001: Título corto de la decisión

**Context:** la situación que fuerza la decisión.

**Decision:** qué se decidió.

**Consequences:** con qué hay que vivir a partir de ahora — ventajas y el costo que se acepta.
```

## Container vs. component vs. feature blueprint

La pregunta para elegir: ¿esto es una unidad que se despliega sola (container), una capacidad que
más de una feature necesita (component), o el ensamblado puntual para satisfacer un FRD (feature)?
No se crea un Component Blueprint para lógica que solo una feature usa — eso es
`Feature-Specific Components` dentro del Feature Blueprint, y si el día de mañana una segunda
feature lo necesita, ahí se extrae a su propio Component Blueprint.

## Mentions

- `` `#ComponenteEjecutable` `` — un componente en runtime, definido en algún bloque `component`.
- `` `Elemento` `` — un schema, modelo de datos, enum, tipo de request/response.
- `@EntidadDeLaFabrica` — un Requirement, Blueprint o Work Order (`@FRD-X`, `@BP-Y`).

## Idioma

Los bloques `component` y sus `name`/`container`/`responsibilities` pueden llevar identificadores
en inglés (son código). Las secciones, la prosa de relaciones, los ADR y los Key/Integration
Contracts van en **español**.
