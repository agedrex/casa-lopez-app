# UX heurísticas: menos texto, taller y admin
Aplicar el plan de mejoras de la auditoría UX (Engram topic `ux/auditoria-heuristicas-2026-11-18`, id 1202) y dejarlo en staging.

## Specs
- S1: "reducir al minimo el texto que se usa en la aplicacion ya que cada componente se deb explicar por si solo y entenderse" (subtítulos ≤12 palabras o tooltip; Voz, Sync, Escenarios, Nuevo lote, Usuarios, Materiales, Talleres, Proveedores, Unidades, login).
- S2: Ninguna pantalla muestra nombres de variables de entorno o claves (AI_GATEWAY_API_KEY, GOOGLE_*) a roles no técnicos; el texto dice solo "no disponible" y a quién pedirlo.
- S3: Cambiar el estado de un lote pide confirmación corta y ofrece deshacer (volver al estado anterior) sin perder el historial. Respetar lo que ya definió `odd/tasks/mejoras-qa-staging.md` (S3 de ese archivo: no saltar estados).
- S4: Voz único en toda la UI (voseo rioplatense, decisión provisoria hasta que Robert diga otra cosa) y glosario fijo: Lote, Modelo, Producto, Taller, Fábrica.
- S5: Taller: Voz y Cortes en la barra inferior; la ficha no muestra importes en $ al taller; "Hilo y cemento" en juegos con máx. 2 decimales.
- S6: Lote: una sola tabla de insumos (cuero + consumo + total); no mostrar "Sin responsable · guardado …" si no hay dato; sin "a hacer" en lotes cerrados.
- S7: Alertas del Panel agrupadas por tipo con contador y nombre antes que código; Modelos paginado con orden por columna.
- S8: /formularios, /cueros, /cvu: 404 propio con enlace al inicio (o redirect si la ruta existe en docs).
- S9: Atajos mínimos ("/" busca, "n" nuevo) y estado "Guardando…" en botones de guardar.
- S10: "quiero que empieces a trabajra en esos puntos ... hasta dejar todos los cambios en staging" (merge a main solo con CI verde; production no se toca).

## Tasks
- T1 (S1,S2,S4,S8): textos, voz única, env vars, login, 404 — ruta: writer W1 — commit: hecho (rama feat/ux-heuristicas)
- T2 (S3,S5,S6,S9-guardando): lotes/taller — ruta: writer W2 — commit: hecho (rama feat/ux-heuristicas)
- T3 (S7,S9-atajos): panel alertas, modelos — ruta: writer W3 — commit: hecho (rama feat/ux-heuristicas)
- T4: lint+build+tests, merge y staging — ruta: inline — commit: pendiente

- T5 (S3): "Deshacer" del cambio de estado de lote (backend retroceso append-only + front 10 s) — writer W4 — commit: pendiente
- T6 (S9, higiene): ayuda contextual "?", validación inline en Mano de obra, indicador de carga, warnings de lint — writer W5 — commit: pendiente
- T7: verificar rol taller en staging tras el deploy — inline (ego-browser) — pendiente

## Log
L1: "quiero que empieces a trabajra en esos puntos que idetificaste hasta dejar todos los cambios en staging"

L2: T2 sin 'Deshacer' (S3 parcial): requiere endpoint de retroceso en backend y choca con el carril de estados de mejoras-qa-staging.md. Queda pendiente aparte.
L3: Slices: T1 (6566a50), T2 (3a44252), T3 (último commit); la rama supera ~400 líneas, se entrega como una sola rama porque son cambios de front independientes y verificados.

L4: Cierre 2026-11-18. PR #52 mergeado y verificado en staging como admin. Pendientes para otra sesión (detalle en Engram `odd/ux-heuristicas/pendientes`): verificar rol taller en staging, "Deshacer" de estado de lote (backend), decisiones de voseo y Herrajes, P3 (ayuda contextual, validación inline, skeletons).

L5: "resolve esos pendietes" (2026-11-18). Voseo y Herrajes-oculto quedan como están hasta que Robert decida (no son resolubles por código).

L6: Decisiones confirmadas por el usuario: voseo en toda la UI; el taller no ve importes en $ ni Herrajes.
