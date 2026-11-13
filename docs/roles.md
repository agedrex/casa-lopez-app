# Roles y accesos

Fuente de verdad: `backend/src/backend/auth.py` (gates), `backend/src/backend/api.py` (matriz) y `front/lib/permissions.ts` (qué rutas abre cada rol). El test `backend/tests/test_roles.py` falla si un endpoint nuevo no tiene gate o tiene otro. Todo se niega por defecto.

Los nombres viejos se leen mapeados: `cotizador` → `admin`, `corte` → `taller`, `consulta` → `gerente`. Un usuario sin rol reconocido cae en `/sin-acceso`.

## Qué abre cada rol

| Módulo | `admin` | `gerente` | `taller` |
|---|---|---|---|
| Productos (lista y ficha), con precios de venta y rentabilidad | todo | solo lectura | lista y ficha, sin precios de venta |
| Modelos | todo | solo lectura | solo lectura |
| Escenarios (simulador) | sí | sí (solo lectura) | no |
| Panel (`/admin/panel`) y alertas | sí | **no** | no |
| Lotes (`/fabricacion`) y Talleres | sí | **no** | no |
| Formularios de consumos | todo | **no** | completa los que le envían |
| Inventario de cuero (`/cueros`) y Corte | sí | **no** | sí |
| Proveedores | sí | **no** | no |
| Materiales y precios, Costos fijos, Catálogos, Administración | sí | no | Materiales: solo lectura |
| Voz | sí | no | sí |

El `gerente` nunca escribe. SUPUESTO: validar con Robert y Alejandro qué persona real tiene qué rol.

## Gates del backend (`auth.py` y `api.py`)

| Gate | Roles | Lo usan |
|---|---|---|
| `SOLO_ADMIN` | admin | escrituras, costos fijos, impuestos, alertas (`/calidad`), **`/panel/costos`, `/grilla`**, talleres, proveedores, reventa |
| `PRODUCTOS` | admin, gerente | rentabilidad, precio de venta y precio sugerido de un producto, **`GET /cvu/periodo`** y **`POST /cvu/escenario`** |
| `CORTE` | admin, taller | voz, cortes, lotes (`GET /ordenes`), cueros (`GET /cueros*`) y, de lectura, **`/precios`, `/dolar`, `/colores` y `/categorias`** (el gerente no los lee) |
| `FORMULARIO_LEER` | admin, taller | `GET /formularios*` (el taller solo ve `ENVIADO` y `COMPLETADO`) |
| `CUALQUIER_ROL` | admin, gerente, taller | lecturas compartidas que usan las páginas del gerente: productos (lista, conteo, ficha), modelos, `/materiales` y `/catalogos` |

## Decisiones (S8, 2026-11-13)

- Pedido del usuario: "el gerente solo pueda ver productos, modelos y todo lo que es el simulador de escenarios".
- `POST /cvu/escenario` es un POST solo por su body: `servicios.escenario_cvu` y sus ayudas solo leen y la sesión no hace commit. Por eso pasó de `SOLO_ADMIN` a `PRODUCTOS`. El `taller` sigue sin acceso.
- La API cierra lo mismo que el menú. El simulador tiene su propio `GET /cvu/periodo` (gate `PRODUCTOS`): devuelve solo `{"periodo": "AAAA-MM"}`, el mes de hoy, que es lo único que `/escenarios` usaba de `/panel/costos`. `/panel/costos` (costo del mes por lotes, costos fijos, dólar) pasó a solo admin.
- Se verificó qué llaman las páginas del gerente (Productos lista y ficha, Modelos lista y ficha, Escenarios): `/productos*`, `/modelos*`, `/materiales` (líneas de consumo del modelo), `/catalogos` (filtros) y `/catalogo/etapas` (público). Nada más. Por eso `/grilla` (ninguna pantalla la llama), `/precios`, `/dolar`, `/colores` y `/categorias` se cerraron al gerente. El `taller` conserva `/precios`, `/dolar`, `/colores` y `/categorias` (gate `CORTE`); `/materiales` y `/catalogos` siguen abiertos a los tres.
- Matriz final del gerente (`RUTAS_DEL_GERENTE` en `test_roles.py`): `GET /productos`, `/productos/conteo`, `/productos/{codigo}`, `/productos/{codigo}/rentabilidad`, `/productos/{codigo}/precio-venta`, `/productos/{codigo}/precio-sugerido`, `/modelos`, `/modelos/{codigo}`, `/materiales`, `/catalogos`, `/cvu/periodo` y `POST /cvu/escenario`. Páginas (`front/lib/gerente-rutas.test.ts`): `/productos`, `/productos/<c>`, `/productos/modelos`, `/productos/modelos/<c>` y `/escenarios`.
- La ficha del producto ya no muestra el formulario de consumos validado al gerente (`seesValidatedFormulario`).
- En la pantalla de Escenarios, los links de los avisos (cargar costos fijos o impuestos) se muestran solo a quien puede abrirlos (admin).
