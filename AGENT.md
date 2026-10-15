# Contexto para agentes — Casa López

## Qué estamos construyendo

Este repositorio contiene el prototipo inicial de descubrimiento de Casa López, descrito por La Fábrica `WO-4`. Es una aplicación web con frontend Next.js (`front/`) conectado a una API JSON en FastAPI (`backend/`). La aplicación muestra recursos ficticios para explorar el producto.

**Es solo un prototipo:** no usar sus datos como cotizaciones, costos ni base para decisiones comerciales. Las fórmulas de costeo y los modelos de producción todavía no están validados ni implementados. No asumir que existen funcionalidades, datos o reglas de negocio que el código no confirme.

## Cómo trabajar

Antes de cambiar algo, entendé la tarea y revisá el código y la documentación relacionados. Hacé el cambio más directo que resuelva el problema, y comprobá el resultado con los tests o verificaciones pertinentes. Evitá agregar complejidad, alcance o funcionalidades que no se pidieron.

### Regla: The Pareto Cut

**Buscá el 20 % del trabajo que produce el 80 % del resultado.**

En cada fix, tarea o desarrollo, priorizá la solución más chica que resuelva la necesidad principal y aporte el mayor valor. Dejá para después lo secundario. No conviertas un pedido acotado en una refactorización ni agregues extras sin necesidad. Si hay varias opciones, elegí la más simple que sea segura y suficiente; si no está claro qué resultado se necesita, preguntá antes de ampliar el alcance.

## Comandos útiles

- API local: `uv run --directory backend fastapi dev src/backend/main.py --host 127.0.0.1 --port 8000`
- Frontend local: `cd front && corepack pnpm dev`
- Tests del backend: `uv run --directory backend pytest -q`
- Verificaciones del frontend: `cd front && corepack pnpm lint && corepack pnpm build`

## Despliegue

Consultá `README.md` para el flujo vigente de despliegue. Los cambios probados llegan a staging mediante CI; producción requiere verificación de staging y aprobación explícita. No habilitar el auto-despliegue de producción.
