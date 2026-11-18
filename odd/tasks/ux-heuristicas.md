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
- T1 (S1,S2,S4,S8): textos, voz única, env vars, login, 404 — ruta: writer W1 — commit: pendiente
- T2 (S3,S5,S6,S9-guardando): lotes/taller — ruta: writer W2 — commit: pendiente
- T3 (S7,S9-atajos): panel alertas, modelos — ruta: writer W3 — commit: pendiente
- T4: lint+build+tests, merge y staging — ruta: inline — commit: pendiente

## Log
L1: "quiero que empieces a trabajra en esos puntos que idetificaste hasta dejar todos los cambios en staging"
