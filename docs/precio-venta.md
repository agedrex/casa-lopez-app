# Precio de venta desde los lotes (ficha de producto)

Bloque **Precio de venta** de `/productos/<código>` (S4 de `odd/tasks/flujo-modelos-lotes-precio.md`). Lo ven `admin` y `gerente`; el `taller` no. Pedido del usuario: *"en base a los lotes que ya se hicieron debe definir un precio tomando en cuenta el margen que él escoja, y sobre ese precio se aplican los impuestos que tenga cargados el usuario"*.

El frontend no calcula plata: todos los montos los devuelve el backend como string (`Decimal`).

## Cómo se arma el precio

1. **Costo por unidad (base).** El costo por unidad del **lote terminado más reciente** del producto. Terminado = `LISTA` o `CERRADA` (`servicios.ESTADOS_TERMINADOS`, el mismo criterio del panel y de Unidades). El costo del lote es el que muestra la pantalla Lotes: materiales a precios de la fecha del lote + lo que cobró el taller (pagado, o cotizado si no hay pagado); si el lote tiene el producto en más de un renglón, es el promedio ponderado por unidades.
   - **SUPUESTO: validar con Robert y Alejandro.** Se eligió "el último lote terminado" y no un promedio de lotes porque es la regla más simple y refleja lo que cobra hoy el taller. La pantalla lista hasta 5 lotes terminados (`MAX_LOTES_DEL_PRECIO`) y marca cuál se usó.
   - Un lote cuyo costo no se puede calcular (falta dólar o precio) ni se usa ni se lista. Los lotes no terminados (planificado, en corte, cortado, en confección) no cuentan, aunque sean más nuevos.
   - **Sin lote terminado:** se usa el costo de hoy calculado por el motor y la pantalla lo marca como **estimado, no real** (`fuente_costo = "ESTIMADO"`). Sin ninguno de los dos no hay precio (`fuente_costo = null`).
2. **Margen** que elige la persona, en porcentaje con un decimal (`30`, `32,5`), **sobre el precio** (no sobre el costo).
3. **Precio sin impuestos** = costo ÷ (1 − margen), redondeado a centavos (`costeo.precio_con_margen`). Ejemplo: costo 1.000 y margen 30 % dan 1.428,57 (no 1.300).
4. **Impuestos.** Cada impuesto **activo y con porcentaje** de la tabla `impuesto` (los de `/costos-fijos/impuestos`) se aplica sobre el precio sin impuestos: monto = precio × alícuota, redondeado a 4 decimales, sin compuestos (`servicios.armar_precio_con_impuestos`, la misma función que usa el historial de precios). **Precio final = precio sin impuestos + impuestos.** Los impuestos nunca van sobre el costo. SUPUESTO: validar con el contador. Si no hay impuestos cargados, el precio final es el neto y la pantalla muestra un aviso (con link a `/costos-fijos/impuestos` solo para el admin); no se inventa ninguno.

## API

- `GET /productos/{codigo}/precio-desde-lotes?margen=30` (gate `PRODUCTOS`: admin y gerente). Solo lee, no guarda. `margen` es opcional (0 a menos de 100, un decimal); sin margen devuelve solo la base de costo. Respuesta: `fuente_costo` (`LOTE` / `ESTIMADO` / `null`), `costo_por_unidad`, `lote_base`, `lotes[]` (`codigo`, `estado`, `fecha`, `unidades`, `costo_por_unidad`, `usado`), `margen_pct`, `precio_neto`, `impuestos[]` (`codigo`, `nombre`, `alicuota`, `monto`), `total_impuestos`, `precio_final`, `sin_impuestos`, `avisos[]`. 404 si el producto no existe; 422 si el margen es 100 o más, negativo o tiene más de un decimal.
- `POST /productos/{codigo}/precio-venta` (gate `PRODUCTOS`, antes solo admin: ver `docs/roles.md`). Agrega **una fila nueva con fecha** (`precio_venta`, solo se agregan filas; guardar dos veces el mismo día agrega una segunda y gana la más nueva). Guarda `precio_ars` (sin impuestos) y `margen` como fracción del precio (`0.300` = 30 %).
- `GET /productos/{codigo}/precio-venta`: historial, el más nuevo primero. La columna "con impuestos" del historial usa los impuestos cargados **hoy** sobre cada precio guardado.

## Pantalla

- Margen: campo de texto (GET `?margen=`), botón **Calcular precio**. Sin `?margen=` arranca con el margen del último precio guardado, si tiene.
- Se ve el costo base y los lotes usados, el precio sin impuestos, cada impuesto con su monto y el precio final.
- **Guardar este precio** manda solo el margen: la acción (`savePrecioPorMargen`) le pide el precio a la API otra vez y lo guarda con una nota ("Margen 30 % sobre el costo del lote LOT-0003" o "…sobre el costo estimado de hoy (sin lotes terminados)"). Ningún monto viaja desde el navegador.
- Debajo, el historial de precios guardados (el más nuevo marcado como vigente).

## Ficha: consumo

En la tabla *Consumo* de la ficha, **Herrajes** e **Hilo y cemento** dicen "Según los insumos" (y no "Falta el dato") cuando el modelo no tiene el monto único pero sí insumos de esa etapa, igual que la página del modelo (`front/lib/formulario-insumos.ts`).

## Pruebas

`backend/tests/test_precio_desde_lotes.py` (reglas puras, sin base), `test_precio_desde_lotes_integration.py` (Postgres local; incluye el flujo del gerente), `test_roles.py` y `test_api.py` (permisos), `front/lib/ficha-consumo.test.ts` y `front/lib/permissions.test.ts`.
