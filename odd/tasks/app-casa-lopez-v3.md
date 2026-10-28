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
- T1 (S1,S4,S5) Esquema v3: modelos SQLAlchemy + migración Alembic 0003 (reemplaza v1) + semillas desde la plantilla + tests · delegated (backstop de contexto) · commit: pendiente
- T2 (S1,S2) Motor de costeo v3 (función pura) + paridad contra la plantilla · inline · pendiente
- T3 (S2) API: lectura y carga por módulo · pendiente
- T4 (S3,S7) Frontend base + Better Auth + usuario de prueba · pendiente
- T5 (S7) Módulos consulta/carga + admin · pendiente
- T6 (S2) Sync de lectura hacia Google Sheet · pendiente
- T7 (S7) Módulo de voz · pendiente

## Log
- L1 (2026-10-27): "migrar todo a la planilla que te acabo de decir que revises, esos son los datos que realmnete vamos a terminar usando. El sheet es solo para ver y consultar datos. la app es la que realemnte se conecta y carga todo y si usamos Better Auth"
- L2: Hallazgo: docs/wo2-staging.md dice que las migraciones v1 no estaban aplicadas en Railway al escribirse; no verificado. 0003 debe funcionar con o sin v1 aplicada.
