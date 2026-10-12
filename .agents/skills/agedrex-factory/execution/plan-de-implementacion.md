# Escribir el plan de implementación

El plan de implementación es el puente entre el contexto de la Fábrica y el código. Traduce el work
order, sus requirements enlazados y sus blueprints enlazados en cambios concretos sobre el repo.

Tratá el blueprint como el ancla de arquitectura: define los componentes y contratos que tienen que
existir. El plan de implementación expande ese modelo en estructura de paquetes, componentes de
soporte, interfaces, flujo de control y **cómo se va a testear el cambio**.

**No se toca código antes de persistir el plan en `sf_dossier.implementation_plan` con la
versión vigente**, aunque sea corto. Para un WO fácil el plan
puede ser un párrafo; para uno difícil, varias secciones. Lo que no cambia es el orden: plan primero.

## Estructura del plan

1. **Resumen** — qué entrega este work order y el enfoque de implementación a alto nivel, en 1-3
   oraciones.

2. **Reuso de código y estructura de paquetes** — qué archivos, servicios, hooks, schemas o tests
   existentes se reusan o se toman como patrón. Decidí explícitamente: ¿se reusa directo, se extrae
   a algo compartido, o se sigue como patrón sin compartir código? Después, la lista de archivos y
   directorios que el plan crea o modifica **a propósito**, agrupados por capa (`services/`,
   `routers/`, `mcp_server/`, `models/`, frontend). No enumeres archivos que cambian solo por
   arrastre (orden de imports, barrels, formateo, migraciones autogeneradas).

3. **Componentes y flujo** — qué componentes definidos por el blueprint tienen que existir, qué
   componentes de soporte hacen falta para implementarlos con limpieza (schemas Pydantic, servicios,
   tools MCP, hooks de React), y las firmas públicas antes que los cuerpos cuando aclaran el límite:
   nombre de función/clase, parámetros, tipo de retorno, forma del request/response. Traducí los
   párrafos de relación del blueprint en flujo de llamadas a nivel de código: quién llama a quién,
   en qué orden, qué cruza cada límite.

4. **Pasos** — pasos de implementación concretos que producen estados intermedios revisables
   (idealmente compilables). Marcá qué pasos son independientes entre sí (tocan archivos distintos,
   sin dependencia) cuando eso ayude a paralelizar.

5. **Testing** — qué suites corrés o extendés (unitarios de servicio, tests dirigidos de router/MCP,
   frontend), qué archivos de test son nuevos o cambian, qué escenarios cubren, y el comando exacto
   para correrlos (con `PYTHONPATH` y `TEST_DB_NAME` propios — ver `CLAUDE.md` del proyecto). Esta
   sección **no** es para justificar si el cambio satisface los requirements o el blueprint — esa
   trazabilidad va en la revisión y en el checklist.

## Reglas

- Preferí reuso sobre código nuevo. Si algo existente casi encaja, decidí entre reusarlo directo,
  extraer una pieza compartida, o seguirlo como patrón.
- Preferí una estructura madura y extensible sobre el camino directo pero frágil.
- No planifiques mejoras fuera de alcance. Si las ves, anotalas como nota de seguimiento solo si
  afectan el riesgo de esta entrega — no las implementes acá.

## Fuente

Adaptación al español de
`reference/plugin-8090/software-factory/execution/writing-implementation-plans.md`. La plantilla opcional está en `execution/plantillas/plan-de-implementacion.md`; el registro
canónico es el dossier MCP.
