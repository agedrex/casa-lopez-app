# Ficha de producto (`/productos/<código>`)

Qué muestra la ficha y qué se puede cambiar desde ahí. Es una pantalla de consulta: no calcula plata (los montos los pone el backend).

## Qué se ve

- **Nombres, no códigos.** La columna *Material* y el subtítulo (modelo · cuero · color) muestran el nombre del material y del modelo. La API sigue mandando también el código (`material`, `modelo`, `cuero`) porque el motor y otros reportes lo usan; el nombre viene en `material_nombre`, `cuero_nombre` y `modelo_nombre`. Si un material no tiene nombre cargado, se muestra su código (nunca una celda vacía).
- **Hilo y cemento.** Solo el precio de referencia en pesos: el monto que el motor le carga hoy al producto (`costo_hoy.etapas.HILO_CEMENTO`). Ya no se muestra el monto en USD ni el texto "Fijo en 1 USD, dólar de referencia…". Sin cotización de hoy se ve "—"; si el modelo no tiene el dato, "Falta el dato".
- **Horas de confección.** Última fila de *Consumo*: las horas del modelo (`modelo.horas_de_confeccion`). Es informativa: **no entra en el costo** (el motor no la lee) y se edita en *Modelos*.

## Qué se puede cambiar

- **Color** (solo `admin`): sección *Color* de la ficha. Elegir uno existente, "+ Crear color nuevo…" o "Sin color" para quitarlo. `PUT /productos/{codigo}/color` con `{"color": "<nombre>" | null}`; el color tiene que existir (422 si no) y devuelve la ficha. Las cotizaciones ya guardadas no cambian (son fotos); el costo de hoy sigue los precios del color nuevo. `gerente` y `taller` no ven el formulario y la API les responde 403.

## Pruebas

`backend/tests/test_ficha_producto_nombres.py` (sin base), `test_ficha_producto_integration.py` (Postgres local) y `front/lib/ficha-consumo.test.ts`.
