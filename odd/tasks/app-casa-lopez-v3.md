# App Casa López sobre plantilla v4.1 (DER v3)
Objetivo: migrar base + backend a DER v3 de la plantilla, luego frontend (Next.js) con Better Auth, módulos y admin.
Branch: feat/der-v3 · Entrega: ask-on-risk · Runner: `uv run --directory backend pytest -q`, `cd front && corepack pnpm lint && corepack pnpm build`

## Specs
- S1. Fuente de verdad = `Plantilla Costos Casa Lopez v4.1 (trabajo).xlsx` (~/Desktop), pestaña `Diccionario` (hoja → tabla → columna). Reemplaza al DER v1 y a las reglas del Excel viejo (GG 11 % se elimina; CORTE fijo; CONFECCION; HILO_CEMENTO separado).
- S2. El Sheet es solo para ver y consultar. La app es la que se conecta y carga todo (la app escribe y lee la base; el Sheet es una vista).
- S3. Auth con Better Auth (schema `public`, nunca tocado por Alembic). Usuario de prueba `contacto@agedrex.com`.
- S4. Tablas v3 (solo columnas "carga" se persisten; las "calculada (la app recalcula)" las calcula el backend): modelo, producto, receta_linea (origen EXTRA), precio_material, tipo_cambio, orden_fabricacion, orden_item, gasto_periodo, etapa, material, categoria, color, persona, taller, impuesto, parametro, molde, modelo_molde, orden_estado, registro_tarea, pieza_cuero, movimiento_cuero, conteo_inventario, kit_componente, cotizacion. Las hojas "vista" no se sincronizan.
- S5. Reglas que se conservan: dinero con Decimal/NUMERIC; precios y dólar solo se agregan con fecha; schema `costos`; clave de negocio = `codigo` único que nunca cambia.
- S6. Aplicar migraciones en Railway requiere autorización explícita (docs/wo2-staging.md). No se hace sin ella.
- S7. Frontend: estilo casalopez.com.ar; módulos de consulta/carga, panel admin, módulo de voz (el LLM interpreta, nunca calcula; una persona confirma).

## Tasks
- T1 (S1,S4,S5) Esquema v3: modelos SQLAlchemy + migración Alembic 0003 (reemplaza v1) + semillas desde la plantilla + tests · delegated (backstop de contexto) · HECHO · commit 173968c · aplicado en staging (123 passed, 13 skipped; migraciones verificadas en Postgres local descartable)
- T2 (S1,S2) Motor de costeo v3 (función pura, tests por regla; SIN prueba de paridad, el usuario la descartó) · inline · HECHO (22 tests, 145 passed)
- T3a (S2) Generador de recetas y cotización a una fecha, en la app (receta.py, puro) · inline · HECHO (12 tests, 157 passed)
- T3b (S2) Servicio con DB + endpoints de lectura y carga, todos tras `require_user` fail-closed (401 hasta T4) · delegated (backstop de contexto) · HECHO (226 passed; 257 con Postgres local)
- T4 (S3,S7) Frontend base + Better Auth + usuario de prueba + verificador en backend · delegated (backstop) · HECHO local (250 passed; E2E con Postgres local); falta desplegar y migrar en staging
- T5 (S7) Módulos consulta/carga + admin · pendiente
- T6 (S2) Sync de lectura hacia Google Sheet · pendiente
- T7 (S7) Módulo de voz · pendiente

## Log
- L1 (2026-10-27): "migrar todo a la planilla que te acabo de decir que revises, esos son los datos que realmnete vamos a terminar usando. El sheet es solo para ver y consultar datos. la app es la que realemnte se conecta y carga todo y si usamos Better Auth"
- L2: Hallazgo: docs/wo2-staging.md dice que las migraciones v1 no estaban aplicadas en Railway al escribirse; no verificado. 0003 debe funcionar con o sin v1 aplicada.
- L3: T1 cerrado. Consumos pasaron a NUMERIC(12,6) para no romper la paridad (12 valores se redondeaban con (10,4)). Slice 1 = 173968c, ~2900 líneas (semillas JSON generadas). Pendiente: elegir estrategia de cadena de PRs. Migraciones NO aplicadas en Railway (S6).
- L4 (2026-10-28): Autorizado por el usuario: todo el trabajo va a staging; producción no se toca. Entornos `staging` y `production` ya existían en Railway (proyecto casa-lopez); production no tiene DATABASE_URL (aislado, deploy FAILED/detenido).
- L5: Rama feat/der-v3 pusheada. Staging despliega solo desde main, así que el código v3 se subió con `railway up` (raíz del repo; el servicio tiene root /backend) solo al servicio backend de staging. Deploy fc057a95 SUCCESS. `alembic upgrade head` en staging: 0002_semillas -> 0004_semillas_v3 (head), `alembic check` limpio, `verificar_db`: todo OK. Las 11 tablas v1 se borraron (datos de prueba). Evidencia S6 cumplida para staging.
- Estrategia de PRs: feature-branch-chain (todos contra feat/der-v3, PR final a main).
- L6 (2026-10-28): "hay una prueba de paridad. Necesito que solo esté funcionando la lógica, en realidad" -> T2 sin fixtures de paridad contra Excel; solo tests de cada regla de la plantilla (LEEME sec. 6).
- L7 (2026-10-28): "esa receta y todo se debería generar directamente en la aplicación, ya no estar en el Excel... el Excel ya no sirva para hacer cálculos, sino solo para mostrar información" -> refuerza S2: la receta, las cotizaciones y todos los cálculos se hacen y persisten en la app; el Sheet solo muestra.
- L8: T3b hecho. Corregido por el parent: el componente de un kit cuenta por su subtotal de etapas (plantilla Cotizaciones!O), no por su total, para no duplicar IVA/arreglos. Supuestos abiertos del worker: prefijos REX-/LOT-/LIT-, kits anidados hasta 5 niveles, parámetro faltante = 0 %, desperdicio_manual como fracción. CORS ahora permite POST.
- L9: T4 hecho. Decisiones del worker: roles admin|cotizador|consulta (default consulta, supuesto), sign-up deshabilitado, el navegador nunca llama al backend (el front reenvía la cookie), backend verifica llamando a AUTH_VERIFY_URL (get-session). Riesgo: `next build` de Next 16.4.0 falla la 1ª vez por un aviso de seguridad de npm y pasa en el reintento; decisión de actualizar Next pendiente del usuario.
