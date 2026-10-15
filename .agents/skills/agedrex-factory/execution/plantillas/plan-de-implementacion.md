<!--lint disable no-undefined-references strong-marker-->

# Plan de implementación: {{WORK_ORDER_REF}}

**Work order:** {{WORK_ORDER_REF}} — {{WORK_ORDER_TITLE}}
**Creado (UTC):** {{INICIADO_EN}}

Persistí este plan en `sf_dossier.implementation_plan` con `expected_version` antes de cambiar
código. El archivo local es solo un borrador opcional.

## Resumen

_1-3 oraciones: qué entrega este work order y el enfoque de implementación a alto nivel._

## Reuso de código y estructura de paquetes

_Archivos/servicios/hooks/schemas/tests existentes a reusar o tomar como patrón, con la decisión
explícita (reusar directo / extraer compartido / seguir como patrón). Después, los archivos y
directorios que este plan crea o modifica a propósito, agrupados por capa. No listar archivos que
cambian solo por arrastre (imports, barrels, formateo, generado)._

## Componentes y flujo

_Componentes definidos por el blueprint que tienen que existir, componentes de soporte necesarios,
interfaces/firmas importantes, y el flujo de llamadas y datos entre ellos._

## Pasos

_Pasos de implementación ordenados. Cada paso debería producir un estado intermedio revisable
(idealmente compilable). Marcar los pasos paralelizables (archivos distintos, sin dependencia)._

1. **[título]** — _qué hacer, dónde_
2. **[título]** — _qué hacer, dónde_

## Testing

_Tests automáticos y manuales: suites, archivos nuevos/modificados, escenarios, comandos exactos
(con `PYTHONPATH` y base de test propia). No es para justificar conformidad con requirements o
blueprint — eso va en la revisión._
