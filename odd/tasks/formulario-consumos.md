# Formulario de consumos y herrajes (digital)
Objective: one digital "formulario de consumos y herrajes" per new article; the same component is the product's view and what the taller fills in; the admin validates. Branch: main (uncommitted; commits deferred, see Log). Delivery: ask-on-risk. Runner: `uv run --directory backend pytest -q`; `cd front && corepack pnpm lint && corepack pnpm build`.

## Specs
- S1: Top field "ARTÍCULO" (name or code). Two tables, same order and names as the paper sheet.
- S2: CONSUMOS table, columns `CONSUMOS | M2 | COMENTARIOS / MODIFICACIONES`. Preloaded rows in this order: CUERO, FORRO / TELA, FORRO / POTRO, GOMA EVA, FRISELINA, CARTÓN FIBRA, FLEX, CARTULINA, MOIRE, HS. DE TRABAJO, Y/O MANO DE OBRA TALLER, DESPERDICIO 30%, CORTE MANO DE OBRA, EMPAQUE.
- S3: HERRAJES table, columns `HERRAJES | CANTIDAD | COMENTARIOS / MODIFICACIONES`. Preloaded rows: CIERRE N5, CIERRE N3, DESLIZADOR N5, DESLIZADOR N3, HEBILLA, MOSQUETÓN, MEDIA LUNA, ARGOLLA 10MM, IMÁN, TORNIQUETE, CADENA, REMACHES, SPAGUETTI, TRENCILLA, MANGUERA, OJALILLO.
- S4: Cells editable inline; predefined names editable; rows can be added and removed; no row is mandatory; clean light layout, usable on mobile; buttons guardar / editar / imprimir (PDF via print).
- S5: Create (preloaded, empty quantities/comments), save, search/open, edit, duplicate from another, print/export. Each article has its own independent sheet.
- S6: "No se necesita desarrollar un sistema de costos ni realizar cálculos automáticos en esta primera versión." Quantities are exact; no general USD values in this form.
- S7: When an admin creates the article, the taller receives the form with the article name and fills it; "el mismo" component for the product view and for the taller.
- S8 (decided 2026-11-12, user "si"): the admin validates, never the taller. Flow BORRADOR -> ENVIADO (admin sends) -> COMPLETADO (taller completes) -> VALIDADO (admin validates) or back to ENVIADO with a review comment. A VALIDADO form is immutable (duplicate to change). Nothing is deleted.
- Assumptions (mark SUPUESTO, validate): the taller role is not linked to one specific taller, so any `taller` user sees forms in ENVIADO/COMPLETADO; the form is per article (not per modelo); applying values to `modelo`/`receta_linea` is NOT part of this stage.

## Tasks
- T1 (S1-S3, S5, S8) backend: tables `formulario_consumo` + `formulario_consumo_linea`, migration 0016, API, state machine, roles, tests. Route: delegated (context backstop). Commit: single combined commit (see L4).
- T2 (S1-S7) frontend: shared `FormularioConsumos` component, /formularios list + /formularios/[codigo], taller menu, print CSS, product sheet shows the validated form. Route: delegated (depends on T1). Commit: single combined commit (see L4).
- T3 independent verification (migration = high risk item 1, new roles = item 2) and docs. Commit: single combined commit (see L4).
  Result: B1 (writes never committed) found by the verifier, fixed with `session.commit()` in the four writers + regression test against the real session; all other probes OK. Not run: browser (mobile layout, print).

## Log
- L1 (2026-11-12): user pasted the "Especificación para digitalizar el formulario de consumos y herrajes" (summarized into S1-S7) and asked that when an admin creates a new product the taller receives this form with the article name, and that the taller fills it when quoting a new product.
- L2 (2026-11-12): "es de un prodcto nuevo y es como se deberia ver el prodcuto en si. Ya no tienen que haber valores generales en dólares ni nada de todo lo que se raje, sino que tiene que ir el precio exacto. [...] logremos esa sincronía de que este formulario sea el mismo tanto a la hora de que se ve el producto hecho [...] como en lo que le llega [...] al tallerista. ¿Quién finalmente es el que lo valida y todo?" Answer proposed: admin validates. User: "si".
- L3: the working tree holds uncommitted work from the previous request (ficha simplificada, precio-sugerido, migration 0015); commits are deferred until the user decides how to slice them.
- L4 (2026-11-12): user asked to leave everything ready for staging. Checks observed: backend 2174 passed/359 skipped without DB; 2527 passed/6 skipped against a throwaway Postgres (migrations 0015 and 0016 applied); front lint, tsc, node tests and `pnpm build` clean. Not run: browser check (mobile layout, print). Work of 0015 (precio con margen, ficha simplificada) and 0016 share files (models, api, auth, nav), so they go in one commit instead of two slices.
