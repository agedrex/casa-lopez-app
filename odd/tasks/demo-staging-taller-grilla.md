# demo-staging-taller-grilla

Objective: realistic staging demo data + taller with a single entry (lots) + productos grid reordered (costs first, dollar of the quote date).
Branch: feature/demo-staging-taller-grilla. Delivery: ask-on-risk. Runners: `uv run --directory backend pytest -q`, `cd front && corepack pnpm lint && corepack pnpm build`.

## Specs

- S1. Staging has several realistic examples of the final interface: suppliers each with their products (`proveedor_producto`), lots in several states with items, saved quotes (`cotizacion`) with their own dollar, a consumption form in ENVIADO for the taller and one new model to practice, "como si fuera todo un ejemplo real". Loaded through `backend.servicios`, marked EJEMPLO, idempotent, staging-only guards unchanged.
- S2. Taller has ONE entry: the lots list ("cada vez que se crea un lote"): sees what to make and how many of each product; from each product opens the full product sheet (materials/recipe, no prices/profitability). Menu, landing and mobile tabs of taller point to it (Lotes + Formularios for practicing the sheet).
- S3. Taller can see an example of the consumption sheet (planilla), receives one to complete, and can practice filling the whole planilla for a new model (the ejemplo sent by the user).
- S4. Proveedores shows, in example mode, every supplier with its products.
- S5. Products grid column order: Producto + ID (PRD-), Modelo + ID (MOD-), then the rest of existing columns, COSTS first, and margin / precio neto / precio final LAST.
- S6. "El costo tiene que ser tomando en cuenta el dólar del día que se cotizó": the cost in the grid uses the dollar of the quote date (latest saved cotización: its dollar and date are shown); without a quote it falls back to today's cost and says so. Assumption (SUPUESTO): "se cotizó" = latest saved cotización of the product.

## Tasks

- T1 (S1,S3,S4,S6) backend: seeds + API fields — route: delegated (parallel unit A)
- T2 (S2,S3,S5) front: taller entry, nav, grid order, new fields — route: delegated (parallel unit B)
- T3 (S1) load staging DB — route: inline, needs user's go (remote)

## Log

L1 (2026-11-13): "Quiero que hagamos dos cambios importantes y lanza SupaGente si es necesario para que lo termines. Por un lado quiero que la base de datos de staging tenga ya varios ejemplos, aunque sea a partir de lo que teníamos antes o con lo que tenemos ahora, de cómo se vería la interfaz final. El taller solo debería tener una entrada, básicamente cada vez que se crea un lote, para que ellos puedan ver el lote de lo que tienen que fabricar y cuánto tienen que hacer de cada producto. Donde entren a cada producto y vean sus materiales, toda la ficha del producto en sí Y otra cosa: la parte de producto no me terminó de gustar cómo se quedó la grilla. Quisiera que quede producto con el producto ID, el modelo con el modelo ID y después todo lo demás que ya pusiste, pero que lo del margen, precio y todo eso esté al final. Lo más importante es que primero se vean los costos. El costo, no te olvides, tiene que ser tomando en cuenta el dólar del día que se cotizó. Quiero que, en la parte de taller, se pueda ver un ejemplo de cómo saber la planilla y que al taller se le sea una planilla para que la complete. Que se le sea un nuevo modelo y practique armar toda la planilla que estuvimos haciendo con el ejemplo que te mandé. Y que también, en la parte de proveedores, todo eso, aunque sea en modo ejemplo, pueda ver cómo se va a ver finalmente con todos los productos: todo lo que sería cada proveedor y todo con sus respectivos productos. Quiero que haga toda la interfaz como si fuera todo un ejemplo real de todo lo que se va a tener y hacer."
