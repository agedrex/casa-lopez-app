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
| `SOLO_ADMIN` | admin | escrituras, costos fijos, impuestos, alertas (`/calidad`), talleres, proveedores, reventa |
| `PRODUCTOS` | admin, gerente | `/panel/costos`, rentabilidad y precios de venta de un producto, `/grilla`, **`POST /cvu/escenario`** |
| `CORTE` | admin, taller | voz, cortes, **lotes (`GET /ordenes`) y cueros (`GET /cueros*`)** |
| `FORMULARIO_LEER` | admin, taller | `GET /formularios*` (el taller solo ve `ENVIADO` y `COMPLETADO`) |
| `CUALQUIER_ROL` | admin, gerente, taller | lecturas compartidas: productos, modelos, materiales, precios, catálogos, dólar |

## Decisiones (S8, 2026-11-13)

- Pedido del usuario: "el gerente solo pueda ver productos, modelos y todo lo que es el simulador de escenarios".
- `POST /cvu/escenario` es un POST solo por su body: `servicios.escenario_cvu` y sus ayudas solo leen y la sesión no hace commit. Por eso pasó de `SOLO_ADMIN` a `PRODUCTOS`. El `taller` sigue sin acceso.
- `/panel/costos` sigue abierto al gerente porque `/escenarios` lo usa para el período. `/dolar`, `/materiales`, `/precios` y `/catalogos` siguen en `CUALQUIER_ROL` porque los usan Productos, Modelos y el taller.
- La ficha del producto ya no muestra el formulario de consumos validado al gerente (`seesValidatedFormulario`).
- En la pantalla de Escenarios, los links de los avisos (cargar costos fijos o impuestos) se muestran solo a quien puede abrirlos (admin).
