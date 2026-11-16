# Grilla de modelos, creado por, alta de modelo desde taller con foto
Objective: rediseñar la grilla de modelos, columna "creado" en Productos, que el taller cree el modelo (con foto) y complete la hoja de consumos, y que administración lo valide. Branch: feat/modelo-taller-foto. Delivery: ask-on-risk. Runner: `uv run --directory backend pytest -q`; `cd front && corepack pnpm lint && corepack pnpm build`.

## Specs
- S1: "Revisa el diseno de la Grillas de modelos que se ve mal y esta mal el diseno". Grilla de modelos con columnas claras (código, nombre, categoría, tamaño, validación, datos faltantes, consumos clave, horas), sin mezclar todo en la primera columna.
- S2: "En producto quiero que aumnetes una columna que diga cunaod fue creado y por que usuario". Columna "Creado" (fecha y usuario) en la lista de Productos. Requiere `producto.creado_por` (migración, nullable) y mostrar el nombre del usuario.
- S3: "A LA HORA DE CREAR un nevo modelo se deberia crear en algun menu del taller que hay un nuveo modelo que deberia recibir todos los datos y todo el formulario que dijismo para que complete usanod los datos reales. La idea es que el taller cree el modelo y luego la admistracion lo calide". Menú del taller "Nuevo modelo": el taller crea el modelo y completa la hoja de consumos; administración valida (flujo `formulario` existente).
- S4: "y en el formulario que se manda para crear un modelo estaria bueno anadir una fotografia y que el ID del modelo y el nombre esten en titulos separados". Foto en el alta del modelo; ID y nombre en títulos separados.
- Supuestos (SUPUESTO, validar): foto guardada en la base (bytea, como `documento_proveedor`), sin object storage; el taller ve solo los modelos que creó o que están ENVIADO/COMPLETADO.

## Tasks
- T1 (S1) front: rediseño de la grilla de modelos. Route: inline. DONE (tsc y lint sin errores nuevos; sin prueba en navegador).
- T2 (S2) backend+front: producto.creado_por (migración 0023), columna Creado en Productos. Route: delegated (context backstop). DONE, commit 118197f (pytest 2505 passed; tsc, lint, build OK; query a public.user y migración sin probar contra Postgres real).
- T3 (S4) backend+front: foto del modelo (migración 0024, endpoints, ficha) y títulos ID/nombre separados. Route: delegated (context backstop). DONE, commit 5c01047 (pytest verde, tsc, lint, front tests, build OK; sin Postgres real ni navegador). Abierto: taller puede subir foto a cualquier modelo (SUPUESTO), acotar en T4.
- T4 (S3, S4) backend+front: taller crea modelo, pantallas /taller/modelos*, validación admin. Route: delegated (context backstop). DONE (pytest 2578 passed, front 71 passed, tsc, lint, build OK; verificador independiente PASS sin blockers). Sin Postgres real ni navegador.

## Log
- L1 (2026-11-16): "Revisa el diseno de la Grillas de modelos que se ve mal y esta mal el diseno. En producto quiero que aumnetes una columna que diga cunaod fue creado y por que usuario. A LA HORA DE CREAR un nevo modelo se deberia crear en algun menu del taller que hay un nuveo modelo que deberia recibir todos los datos y todo el formulario que dijismo para que complete usanod los datos reales. La idea es que el taller cree el modelo y luego la admistracion lo calide. y en el formulario que se manda para crear un modelo estaria bueno anadir una fotografia y que el ID del modelo y el nombre esten en titulos separados"
- L2 (2026-11-16): Decisión: "Pantalla nueva y completa (recomendada)". Hallazgo: no existe pantalla de formularios en el front; head de migraciones es 0022.
- L3 (2026-11-16): Delivery: single-pr (una rama, un PR), elegido por el usuario al pasar las 400 lineas.
- Advisories del verificador: alta de admin sin campo de foto; gerente/taller ven email si el usuario no tiene nombre; categoria obligatoria en alta de taller; query a public.user y migraciones 0023/0024 sin probar en Postgres real.
