# Panel del negocio: costos de Fábrica y de Tienda

Pantalla `/admin/panel` (solo `admin`). Tiene tres vistas, en el parámetro `?vista=`:

| Vista | Qué muestra |
|---|---|
| **Costos** (por defecto) | Dashboard: costo-volumen del mes, dólar del día y alertas. |
| **Fábrica** (`?vista=fabrica`) | Total de costos de la fábrica del mes, su grilla de costos (donde se agregan), los retazos de cuero del mes y su punto de equilibrio. |
| **Tienda** (`?vista=tienda`) | Lo mismo para la tienda, más la Mercadería comprada en el mes. |

Un `?vista=` desconocido (por ejemplo el viejo `gastos`) cae en **Costos**.

## Unidades producidas y costo variable del mes

SUPUESTO: validar con Robert (QA 2026-11-18, S5). El panel de **Costos** divide los costos fijos por las unidades producidas del mes y
promedia el costo variable de esas mismas unidades. Una unidad cuenta como producida **solo cuando su lote está terminado**
(estado `LISTA` o `CERRADA`; "desde que se termina y el taller ya terminó"). Un lote `PLANIFICADA`, `EN_CORTE`, `CORTADA` o
`EN_CONFECCION` no suma unidades ni costo variable. Antes el panel contaba todos los lotes y `/unidades` todos menos los planificados
(21,5 contra 13 en el QA), y crear un lote subía el costo variable al instante.

- **Un solo criterio** (`servicios.lotes_que_cuentan`) para el panel, la tendencia, el CVU del mes (`cvu`, `equilibrio`, `fijo_por_unidad`,
  `costo_variable_total`), la pantalla `/unidades` y el stock de fábrica. No hay otro lugar donde se cuenten unidades de lotes.
- **Costo variable del mes = el mismo conjunto de lotes.** `costo_variable_total` y `costo_variable_por_unidad` suman solo renglones de
  lotes terminados del mes. Elección no obvia: no hay un costo variable "en curso" aparte; se podría mostrar el costo de los lotes
  abiertos como adelanto, pero se dejó afuera para que unidades y costo no puedan discrepar.
- **Mes del lote:** el de su entrega o, si no tiene, el de su envío (sin cambios). No es el mes en que pasó a `LISTA`: un lote enviado
  en octubre y terminado en noviembre cuenta en octubre, y octubre cambia cuando se termina. Alternativa si molesta: contar en el mes del
  cambio de estado a `LISTA` (pide leer `orden_estado`).
- **Avisos:** `SIN_UNIDADES` dice "No hay lotes terminados en este mes…" y `VOLUMEN_PRODUCIDO` aclara que el volumen es lo producido en
  lotes terminados, no lo vendido.
- **En cada lote** (`/fabricacion/[codigo]`, solo admin) aparece cuánto mueve el costo variable: su costo, sus unidades y si ya suma al
  mes o suma cuando llegue a Lista.

## La grilla de costos de cada área

- Es la grilla de costos fijos que antes estaba en "Gastos del negocio" / Costos fijos, movida a cada área. Lee `GET /costos-fijos?periodo=` y filtra por `fabrica_o_tienda`.
- El área no es una columna: la decide la vista. Una fila nueva de la vista Tienda se guarda con `fabrica_o_tienda = TIENDA`.
- Guarda con `POST /costos-fijos/lote` (la misma acción de las otras grillas). Regla de oro 4/10: solo se agregan filas. Un monto cambiado es una fila nueva que apunta a la anterior con `reemplaza_a_id`; borrar es una marca `anulado`. Escribe solo `admin`.
- No hay cambio de esquema ni migración: `gasto_periodo.fabrica_o_tienda` ya existía.

## Mercadería en la Tienda

`GET /costos-fijos/mercaderia?periodo=AAAA-MM` (solo `admin`, solo lectura):

- Suma `unidades × costo_unitario_ars` de cada compra de Mercadería (`compra_reventa`) con fecha dentro del mes. Una fila sin unidades es un cambio de precio de la grilla de Mercadería, no una compra, y no cuenta.
- Devuelve `total_mercaderia`, `total_gastos_tienda` (costos fijos de la tienda del mes) y `total_tienda` (la suma, calculada por el backend). Los totales de `/costos-fijos` **no cambian**: la mercadería no se escribe en `gasto_periodo`.
- SUPUESTO: validar con Robert que la compra se imputa al mes de su fecha.

## Retazos en la Fábrica

`GET /costos-fijos/retazos?periodo=AAAA-MM` (solo `admin`, solo lectura):

- Lista cada retazo de cuero dado de baja en el mes (movimiento `DESPERDICIO` de una `pieza_cuero`, fecha dentro del mes): pieza, cuero y color, fecha, m², precio por m² y total (m² × precio pagado por m² de esa pieza).
- Una pieza sin precio ni dólar viene con `precio_por_m2_ars` y `total_ars` en `null`: la pantalla muestra "sin precio" (nunca 0) y avisa cuántos retazos quedan fuera del total (`sin_precio`).
- Devuelve `total_retazos`, `total_gastos_fabrica` (costos fijos de la fábrica del mes) y `total_fabrica` (la suma, calculada por el backend; la pantalla no suma nada). Los totales de `/costos-fijos` **no cambian**.
- **No escribe nada en `gasto_periodo`:** el costo de retazos se calcula cada vez que se mira el mes, así que corregir un precio o un dólar lo cambia solo.

## Lo que ya no está

- El formulario de margen de transferencia del panel se quitó. El parámetro `MARGEN_TRANSFERENCIA_PCT` y sus datos siguen en la base (el escenario y las transferencias lo usan); solo no se edita desde el panel.

## Para después (no implementado)

Porcentajes de la fábrica a la tienda (20 % / 30 %) y el pase de lotes terminados a costo de tienda.
