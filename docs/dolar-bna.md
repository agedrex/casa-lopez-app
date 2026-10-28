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

## Botón en la app

En **Dólar** hay un botón **Actualizar desde BNA** (lo ven solo el admin y el cotizador).
Muestra "Dólar BNA cargado: $… al DD/MM/AAAA." o "El dólar BNA de esa fecha ya estaba
cargado." Si el banco no responde o cambió la página, muestra un aviso y no guarda nada.

## Correrlo desde la terminal

Desde la carpeta `backend`, con `DATABASE_URL` apuntando a la base:

```bash
uv run python -m backend.actualizar_dolar
```

- Sale con código `0` si cargó el dólar o si ya estaba.
- Sale con código distinto de `0` y un mensaje en `stderr` si falla (banco caído, página
  distinta, base inaccesible). El mensaje nunca incluye la página ni la conexión.
- Habla directo con la base: no necesita usuario ni token de la API.

## Programarlo (todavía NO está configurado)

Se puede agendar con un **cron de Railway** que corra ese mismo comando, por ejemplo los días
hábiles a las 10:30 y a las 16:00 hs de Argentina (el banco actualiza durante el día; correr
dos veces es seguro porque no duplica). **Hoy no hay ningún cron creado**: hasta que se
configure, el dólar se actualiza con el botón o a mano.

## Cuándo se rompe

Si el BNA rediseña la página, la lectura falla con "La página del Banco Nación cambió…".
El parser está en `backend/src/backend/dolar_bna.py` y se prueba con una copia recortada de la
página real (`backend/tests/fixtures/bna_personas.html`): actualizar esa copia y el parser
juntos.
