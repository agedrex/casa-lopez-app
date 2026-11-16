# Dólar automático del Banco Nación (BNA)

La app puede traer sola el dólar oficial del Banco Nación y guardarlo en el historial,
en vez de tipearlo a mano.

## Qué se trae

- De la página pública <https://www.bna.com.ar/Personas>, solapa **Cotización Billetes**,
  fila **Dolar U.S.A**.
- Se guarda el valor de **Venta** (el "vendedor"), con la **fecha que informa el banco**
  (no la de hoy), fuente `BNA`, tipo `VENDEDOR` y la nota "Scrapeado de bna.com.ar".
- **SUPUESTO:** que los costos usen el dólar vendedor. Falta validarlo con Gerardo
  (supuestos abiertos 9 y 12 de `AGENTS.md`). Si dice otra cosa, se cambia en un solo lugar
  (`DOLAR_BNA_TIPO` en `servicios.py`).
- Como todo el historial, **no se edita ni se borra**: si ya hay un dólar BNA vendedor de esa
  fecha, no se hace nada (la app avisa "ya estaba cargado"). Si el banco cambia el valor el
  mismo día, el que ya está guardado se queda.

## En el panel

El Panel muestra **un solo cuadro**, "Dólar del día", con el valor más reciente guardado, su
origen (Banco Nación · vendedor) y la fecha. No hay botón, formulario ni historial en esa vista.

Se actualiza solo: al abrir el Panel, si el último dólar guardado es anterior a hoy (hora de
Buenos Aires), el navegador pide a una acción de servidor que corra la misma carga que el
comando de abajo. **SUPUESTO:** esto reemplaza al cron mientras no exista; como no hay un
proceso en segundo plano, el dólar se trae la primera vez que alguien abre el Panel cada día.

- Es idempotente: si la fecha del banco ya estaba guardada no cambia nada, y la pantalla solo se
  refresca cuando se agregó una fila nueva. El historial se agrega, nunca se edita.
- Se intenta una sola vez por día y por sesión del navegador (`sessionStorage`). Los fines de
  semana el banco informa la fecha del viernes, así que el cuadro sigue mostrando esa fecha.
- Si el banco no responde, el cuadro conserva el último valor guardado y no muestra error.
- Cargar un dólar a mano ya no tiene pantalla; sigue existiendo `POST /dolar` (lo usa la carga
  por voz) y el historial completo se ve en `GET /dolar`.

## Correrlo desde la terminal

Desde la carpeta `backend`, con `DATABASE_URL` apuntando a la base:

```bash
uv run python -m backend.actualizar_dolar
```

- Sale con código `0` si cargó el dólar o si ya estaba.
- Sale con código distinto de `0` y un mensaje en `stderr` si falla (banco caído, página
  distinta, base inaccesible). El mensaje nunca incluye la página ni la conexión.
- Habla directo con la base: no necesita usuario ni token de la API.

## Programarlo

Hay un **cron de Railway** que corre ese mismo comando: servicio `dolar-cron` (raíz `/backend`,
comando `uv run python -m backend.actualizar_dolar`, sin reintentos), de lunes a viernes a las
`0 12 * * 1-5` UTC (09:00 de Argentina). Correr el comando dos veces es seguro porque no duplica.
Existe en los dos ambientes (creado el 2026-11-15): `dolar-cron` en `staging` y
`dolar-cron-production` en `production` (el nombre de servicio es único en el proyecto). Los dos
usan `DATABASE_URL` del Postgres de su ambiente (`${{Postgres.DATABASE_URL}}` y
`${{Postgres-rZDV.DATABASE_URL}}`). El de staging se probó a mano en el contenedor del backend;
el de production desplegó bien (SUCCESS) pero su primera corrida programada todavía no se vio:
mirar sus logs después del primer día hábil a las 12:00 UTC. El Panel sigue trayendo el dólar al
abrirse si el cron falla.

## Cuándo se rompe

Si el BNA rediseña la página, la lectura falla con "La página del Banco Nación cambió…".
El parser está en `backend/src/backend/dolar_bna.py` y se prueba con una copia recortada de la
página real (`backend/tests/fixtures/bna_personas.html`): actualizar esa copia y el parser
juntos.
