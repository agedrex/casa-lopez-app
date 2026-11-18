# Fechas y mensajes de error en el front

Origen: QA manual de staging (2026-11-17), `odd/tasks/mejoras-qa-staging.md`, T3 (S6, S7, S8).

## Fechas y horas (S6)

La base guarda los momentos (`created_at`, `creado_en`, `registrado_en`, `iniciado`...) en UTC. Mostrarlos tal cual
corría el día: `2026-11-18T02:11Z` se veía `18/11` y en la tienda eran las 23:11 del 17.

Un solo lugar convierte: `front/lib/format.ts`, a la hora de **America/Argentina/Buenos_Aires**.

| Helper | Entrada | Salida |
|---|---|---|
| `formatDateTime` | `2026-11-18T02:11:00Z` | `17/11/2026 23:11` |
| `formatInstantDate` | `2026-11-18T02:11:00Z` | `17/11/2026` |
| `formatInstantTime` | `2026-11-18T02:11:00Z` | `23:11` |
| `formatDate` | `2026-11-18` (día sin hora) | `18/11/2026`, sin pasar por `Date` |

- Un **día sin hora** (`fecha`, `vigente_desde`, `fecha_de_envio`...) es una fecha de calendario, no un momento: se
  muestra con `formatDate` y no se corre.
- Un momento **con** `Z` o con desfase (`+00:00`, `-03:00`) se respeta. SUPUESTO: validar con Robert: sin desfase se
  lee como UTC (es el reloj del servidor).
- Ninguna pantalla usa `Intl`, `toLocale...` ni `new Date(...)` para mostrar un momento: usa estos helpers.

## Mensajes de validación legibles (S7)

Antes, un 422 de Pydantic se mostraba como `Revise los datos ingresados (cuero_m2_por_unidad).`, con el nombre interno
del campo. Ahora el mensaje sale en castellano con el nombre que usa la persona:
`El consumo de cuero por unidad debe ser mayor o igual a 0.`

- El mensaje se arma **en el front**, porque ahí ya se armaba (`readFailure` de `front/lib/api.ts`) y es el único cliente de la
  API. La lógica vive en `front/lib/errores-campos.ts` (funciones puras, con tests en `front/lib/errores-campos.test.ts`).
- **Un solo mapa de nombres:** `FIELD_LABELS` en ese archivo. Un campo nuevo en un cuerpo de la API necesita su entrada:
  `backend/tests/test_etiquetas_campos.py` falla si falta (recorre las clases `Entrada` de `api.py`).
- Tipos de error cubiertos: falta el dato, mayor o igual / mayor que / menor o igual / menor que, texto corto o largo, lista
  corta o larga, decimales y dígitos de más, número, fecha, sí/no, opción no permitida y formato. Un campo dentro de una
  lista nombra la fila (`Línea 2: ...`, `Piel 1: ...`). Los validadores propios del backend ya escriben en castellano y se
  muestran tal cual, sin el prefijo `Value error,`.
- Muestra hasta 4 mensajes y cuenta el resto (`(y 2 errores más).`). Un campo sin etiqueta se muestra sin guiones bajos.
- Los errores del servicio (409, 422 con texto) ya vienen en castellano desde el backend y no pasan por este mapa.

## Pedido repetido (S8)

La regla **no cambia**: un material admite un solo precio (y por lo tanto un solo pedido) por fecha, y si falla nada se
guarda. Cambió el mensaje del 409, que ahora dice qué ya existe (`servicios._precio_repetido`):

> Línea 1 (MAT-CU01): Ya hay un precio de Estándar (Anilina Fina Lisa - C Arena) para el 05/11/2026: PRE-0012 (del pedido
> PED-0001) y las piezas PZC-0001, PZC-0002. Un material admite un solo precio (y un solo pedido) por fecha: usá otra
> fecha, o sumá lo nuevo al pedido que ya está cargado.

Nombra el precio, el pedido que lo creó (si lo creó uno) y las piezas de cuero de esa fecha (hasta 5). La carga manual de
un precio (`POST /precios`) usa el mismo mensaje; la pantalla de Materiales sigue mostrando su texto fijo.
