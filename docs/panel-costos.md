# Panel del negocio: costos de Fábrica y de Tienda

Pantalla `/admin/panel` (solo `admin`). Tiene tres vistas, en el parámetro `?vista=`:

| Vista | Qué muestra |
|---|---|
| **Costos** (por defecto) | Dashboard: costo-volumen del mes, dólar del día y alertas. |
| **Fábrica** (`?vista=fabrica`) | Total de costos de la fábrica del mes, su grilla de costos (donde se agregan) y su punto de equilibrio. |
| **Tienda** (`?vista=tienda`) | Lo mismo para la tienda, más la Mercadería comprada en el mes. |

Un `?vista=` desconocido (por ejemplo el viejo `gastos`) cae en **Costos**.

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

## Lo que ya no está

- El formulario de margen de transferencia del panel se quitó. El parámetro `MARGEN_TRANSFERENCIA_PCT` y sus datos siguen en la base (el escenario y las transferencias lo usan); solo no se edita desde el panel.

## Para después (no implementado)

Porcentajes de la fábrica a la tienda (20 % / 30 %) y el pase de lotes terminados a costo de tienda.
