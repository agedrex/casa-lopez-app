# Roles y accesos

Fuente de verdad: `backend/src/backend/auth.py` (gates), `backend/src/backend/api.py` (matriz) y `front/lib/permissions.ts` (qué rutas abre cada rol). El test `backend/tests/test_roles.py` falla si un endpoint nuevo no tiene gate o tiene otro. Todo se niega por defecto.

Los nombres viejos se leen mapeados: `cotizador` → `admin`, `corte` → `taller`, `consulta` → `gerente`. Un usuario sin rol reconocido cae en `/sin-acceso`.

## Qué abre cada rol

| Módulo | `admin` | `gerente` | `taller` |
|---|---|---|---|
| Productos (lista y ficha), con precios de venta y rentabilidad | todo | solo lectura, **salvo el precio de venta**: elige el margen y lo guarda desde la ficha | lista y ficha, sin precios de venta |
| Modelos | todo | solo lectura | solo lectura |
| Escenarios (simulador) | sí | sí (solo lectura) | no |
| Panel (`/admin/panel`) y alertas | sí | **no** | no |
| Lotes (`/fabricacion`) y Talleres | sí | **no** | no |
| Formularios de consumos (`/taller/modelos`) | todo (revisa, valida, devuelve) | **no** | completa las hojas de los modelos que el admin le envía (y sube la foto); no crea modelos |
| Inventario de cuero (`/cueros`) y Corte | sí | **no** | sí |
| Proveedores | sí | **no** | no |
| Materiales y precios, Costos fijos, Catálogos, Administración | sí | no | Materiales: solo lectura |
| Voz | sí | no | sí |

El `gerente` no escribe nada, con **una sola excepción**: guarda el precio de venta de un producto (ver "El gerente guarda el precio de venta" abajo). SUPUESTO: validar con Robert y Alejandro qué persona real tiene qué rol.

## Gates del backend (`auth.py` y `api.py`)

| Gate | Roles | Lo usan |
|---|---|---|
| `SOLO_ADMIN` | admin | escrituras (incluida **`POST /productos/nuevo`**, crear un modelo), costos fijos, impuestos, alertas (`/calidad`), **`/panel/costos`, `/grilla`**, talleres, proveedores, reventa |
| `PRODUCTOS` | admin, gerente | rentabilidad, precio de venta y precio sugerido de un producto, **`GET /productos/{codigo}/precio-desde-lotes`**, **`POST /productos/{codigo}/precio-venta`** (única escritura del gerente), **`GET /cvu/periodo`** y **`POST /cvu/escenario`** |
| `CORTE` | admin, taller | voz, cortes, lotes (`GET /ordenes`), cueros (`GET /cueros*`) y, de lectura, **`/precios`, `/dolar`, `/colores` y `/categorias`** (el gerente no los lee) |
| `FORMULARIO_LEER` | admin, taller | `GET /formularios*` (el taller ve `ENVIADO` y `COMPLETADO`, y las que creó él si las hubiera) |
| `FORMULARIO_TRABAJAR` | admin, taller | guardar filas, completar y subir la foto (`POST /modelos/{codigo}/foto`: un taller solo en un modelo con hoja `ENVIADO` o creada por él) |
| `CUALQUIER_ROL` | admin, gerente, taller | lecturas compartidas que usan las páginas del gerente: productos (lista, conteo, ficha), modelos, `/materiales` y `/catalogos` |

## Decisiones (S8, 2026-11-13)

- Pedido del usuario: "el gerente solo pueda ver productos, modelos y todo lo que es el simulador de escenarios".
- `POST /cvu/escenario` es un POST solo por su body: `servicios.escenario_cvu` y sus ayudas solo leen y la sesión no hace commit. Por eso pasó de `SOLO_ADMIN` a `PRODUCTOS`. El `taller` sigue sin acceso.
- La API cierra lo mismo que el menú. El simulador tiene su propio `GET /cvu/periodo` (gate `PRODUCTOS`): devuelve solo `{"periodo": "AAAA-MM"}`, el mes de hoy, que es lo único que `/escenarios` usaba de `/panel/costos`. `/panel/costos` (costo del mes por lotes, costos fijos, dólar) pasó a solo admin.
- Se verificó qué llaman las páginas del gerente (Productos lista y ficha, Modelos lista y ficha, Escenarios): `/productos*`, `/modelos*`, `/materiales` (líneas de consumo del modelo), `/catalogos` (filtros) y `/catalogo/etapas` (público). Nada más. Por eso `/grilla` (ninguna pantalla la llama), `/precios`, `/dolar`, `/colores` y `/categorias` se cerraron al gerente. El `taller` conserva `/precios`, `/dolar`, `/colores` y `/categorias` (gate `CORTE`); `/materiales` y `/catalogos` siguen abiertos a los tres.
- Matriz final del gerente (`RUTAS_DEL_GERENTE` en `test_roles.py`): `GET /productos`, `/productos/conteo`, `/productos/{codigo}`, `/productos/{codigo}/rentabilidad`, `/productos/{codigo}/precio-venta`, `/productos/{codigo}/precio-sugerido`, `/productos/{codigo}/precio-desde-lotes` y `POST /productos/{codigo}/precio-venta` (ver abajo), `/modelos`, `/modelos/{codigo}`, `/materiales`, `/catalogos`, `/cvu/periodo` y `POST /cvu/escenario`. Páginas (`front/lib/gerente-rutas.test.ts`): `/productos`, `/productos/<c>`, `/productos/modelos`, `/productos/modelos/<c>` y `/escenarios`.
- La ficha del producto ya no muestra el formulario de consumos validado al gerente (`seesValidatedFormulario`).
- En la pantalla de Escenarios, los links de los avisos (cargar costos fijos o impuestos) se muestran solo a quien puede abrirlos (admin).

## El taller recibe modelos, no los crea (2026-11-16)

- Pedido del usuario: "El taller solo debería recibir los modelos que se quieren crear, más no poder crearlos". `POST /productos/nuevo` volvió a `SOLO_ADMIN` (el taller recibe 403): el admin crea el modelo y su hoja nace `ENVIADO`, y el taller la ve y la completa. Antes (modelo-taller-foto T4) estaba en `FORMULARIO_TRABAJAR`.
- Lo que el taller puede: leer y completar las hojas `ENVIADO` (solo las filas) y subir la foto a un modelo con una hoja `ENVIADO`. Lo que no puede: crear modelos, crear categorías (`POST /categorias`), `POST /formularios`, validar, devolver, enviar, duplicar, `POST /modelos`. `test_roles.py` y `test_taller_modelos.py` lo fijan.
- Visibilidad: el taller ve las hojas `ENVIADO` y `COMPLETADO`; si una hoja la creó él (caso histórico), la sigue viendo en cualquier estado. Editar: solo las filas y solo en `ENVIADO`.
- Foto: un taller solo sube foto a un modelo con una hoja `ENVIADO` o que creó él; el admin no tiene límite. SUPUESTO: validar.
- Páginas del taller (`front/lib/permissions.ts`): `/taller/modelos` y `/taller/modelos/<FCO-nnnn>`, y nada más de `/taller`. El gerente no abre ninguna. `/formularios` sigue sin existir como página.

## El gerente guarda el precio de venta (2026-11-18)

- Pedido del usuario (QA, S4 de `odd/tasks/flujo-modelos-lotes-precio.md`): el gerente "debe definir un precio tomando en cuenta el margen que él escoja". Es un **cambio de permiso**: `POST /productos/{codigo}/precio-venta` pasó de `SOLO_ADMIN` a `PRODUCTOS` (admin + gerente). Sigue siendo una fila nueva con fecha (solo se agregan filas, nada se pisa); `creado_por` guarda quién la cargó.
- Lo nuevo de lectura, mismo gate: `GET /productos/{codigo}/precio-desde-lotes?margen=` (ver `docs/precio-venta.md`). El `taller` recibe 403 en ambas.
- Lo que el gerente **no** puede: cualquier otra escritura (`/productos/precios-lote`, impuestos, costos fijos, lotes, etc.). `test_roles.py` fija la matriz y `test_precio_desde_lotes_integration.py` el flujo.
- SUPUESTO: validar con Robert. La pantalla solo manda el margen y la API recalcula el precio, pero el endpoint acepta cualquier `precio_ars` y `vigente_desde`: un gerente con la API en la mano podría cargar un precio a mano o con fecha pasada. Si no se quiere, se cierra con un endpoint que reciba solo el margen.
- Página: la ficha del producto (`/productos/<código>`) muestra el bloque "Precio de venta" a `admin` y `gerente` (`canSetPrice` en `front/lib/permissions.ts`); el `taller` no lo ve. La acción del servidor verifica el rol otra vez.
