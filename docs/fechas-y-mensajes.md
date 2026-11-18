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
