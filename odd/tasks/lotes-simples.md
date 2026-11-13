# Lotes simples: alta mínima y comparación con el último lote del taller
Objective: tanda 2. Branch: main. Delivery: ask-on-risk. Runner front: `cd front && corepack pnpm lint && corepack pnpm exec tsc --noEmit && corepack pnpm build`. Sin cambios de backend ni DER (reusa `GET /talleres/{codigo}/historial` y `POST /ordenes`).

## Specs
- S1: "igual debería ser fácil registrar que se está creando [el lote]. [...] simplifiquen [...] tienen demasiados campos que lo hacen difícil de llenar." Alta de lote visible con solo: Taller, Fecha de envío (default hoy) y filas Producto + Cantidad. Todo lo demás (dónde se hace/persona, precio cotizado y pagado por fila, nota) va dentro de un bloque plegado "Más opciones". Sin "más opciones", el lote se crea EXTERNA con el taller elegido.
- S2: "a la hora de armar un nuevo lote, te haga la comparación de cómo se vio con el último." Al elegir taller en el alta, se muestra el resumen de su último lote (código, fecha de envío, estado, unidades, total pagado, promedio por unidad) y, para cada producto cargado que estuvo en ese lote, la cantidad y el precio pagado por unidad del último lote junto a la cantidad que se está cargando ahora.
- S3: "en cada taller debería haber un resumen de cada lote que se le envió." La ficha del taller muestra una tabla de lotes (código, fecha de envío, estado, unidades, total pagado, promedio por unidad) con enlace al lote; si ya existe en `historial-del-taller.tsx`, solo se ordena del más nuevo al más viejo y se agregan las columnas que falten.
- S4: "unidades producidas [...] en automático" ya se calcula de los lotes (estado distinto de PLANIFICADA); no se toca. El calendario ya abre en el mes actual.
- Supuestos (SUPUESTO, validar): el "último lote" es el de fecha de envío más nueva (desempate por código) del mismo taller, cualquier estado; un taller sin lotes muestra "Primer lote de este taller".

## Tasks
- T1 (S1) front: simplificar `fabricacion/nuevo` y `createOrden`. Route: delegated (context backstop). DONE.
- T2 (S2) front: panel de comparación con el último lote. Route: same worker. DONE.
- T3 (S3) front: resumen por lote en la ficha del taller. Route: same worker. DONE.

## Log
- L1 (2026-11-13): "el tema de lotes, igual debería ser fácil registrar que se está creando. Quiero que simplifiquen uno de esos flujos porque tienen demasiados campos que lo hacen difícil de llenar. después en cada taller debería haber un resumen de cada lote que se le envió y que, a la hora de armar un nuevo lote, te haga la comparación de cómo se vio con el último." Tanda 2 acordada con "si".
- L2 (2026-11-13): worker done; parent spot check: lint y tsc limpios, tests front 31/31. La columna 'Fecha' del historial es entrega o envío (el backend no expone fecha_de_envio): el 'último lote' usa esa fecha. Sin prueba en navegador.
