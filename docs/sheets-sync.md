# Sincronizar el Google Sheet (solo para ver y consultar)

**Regla de oro:** el Sheet es una *copia para mirar*. La app calcula todo, empuja los datos
al Sheet y **nada vuelve del Sheet a la app**. Si alguien edita una pestaña, esa edición se
pisa en la próxima sincronización. Los números del Sheet son valores sueltos (sin fórmulas).

Nada de esto se ha probado contra un Google real todavía: el código se verificó con un
Google simulado. Hacé la primera prueba con un Sheet vacío y de prueba.

## Qué pestañas escribe la app

`Info`, `Catalogo`, `Costos_Variables`, `Cotizaciones`, `Productos`, `Modelos`, `Precios`,
`Dolar`, `Lotes`, `Lote_Productos`, `Costos_Fijos`, `Talleres`, `Parametros`, `Materiales`
y `Calidad`. La app **crea** las que falten, **reemplaza el contenido** de esas y **no toca**
ninguna otra pestaña del Sheet (tampoco borra pestañas). La pestaña `Info` dice cuándo se
generó la copia, con qué versión de la app y cuántas filas tiene cada pestaña.

Ojo: `Talleres` incluye CUIT, teléfono y dirección. Quien tenga acceso al Sheet los ve.

## 1. Crear el Google Sheet

1. En Google Drive: *Nuevo → Hojas de cálculo de Google*. Ponele un nombre, por ejemplo
   `Casa López · Copia de costos`.
2. Copiá el **id** de la dirección: en
   `https://docs.google.com/spreadsheets/d/<ESTE_ES_EL_ID>/edit`, es el texto entre `/d/` y
   `/edit`. Ese valor va en `GOOGLE_SHEETS_SPREADSHEET_ID`.

## 2. Crear la cuenta de servicio (la "persona robot" que escribe)

1. En [Google Cloud Console](https://console.cloud.google.com/) elegí (o creá) un proyecto.
2. *APIs y servicios → Biblioteca*: buscá **Google Sheets API** y tocá *Habilitar*.
3. *IAM y administración → Cuentas de servicio → Crear cuenta de servicio*. No hace falta
   darle ningún rol del proyecto.
4. Dentro de la cuenta: *Claves → Agregar clave → Crear clave nueva → JSON*. Se descarga un
   archivo. **Es una contraseña**: no lo subas al repositorio, no lo mandes por chat ni lo
   pegues en tickets.
5. Anotá el email de la cuenta (termina en `.iam.gserviceaccount.com`).

## 3. Compartir el Sheet con la cuenta de servicio

En el Sheet: *Compartir* → pegá el email de la cuenta de servicio → rol **Editor** → quitá
la casilla de avisar por correo → *Compartir*. Sin este paso Google responde "sin permiso" y
la app lo muestra como "¿Lo compartiste con su email como editor?".

## 4. Cargar las dos variables en Railway (staging)

En el servicio **backend** del environment `staging` (no en el frontend, no en producción):

| Variable | Valor |
|---|---|
| `GOOGLE_SHEETS_SPREADSHEET_ID` | el id del paso 1 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | el **contenido completo** del archivo JSON del paso 2 (el texto, no la ruta) |

Cargalas desde el panel de Railway (*Variables*) y redeployá el backend. Después borrá el
archivo JSON descargado de tu computadora. La app nunca muestra, registra ni devuelve estos
valores: la pantalla solo dice si están cargadas.

## 5. Probar: primero Simular, después Sincronizar

1. Entrá a la app como administrador → *Administración → Google Sheets*
   (`/admin/sync`). Tiene que decir **Configurado**.
2. **Simular (no escribe en Google).** Pide confirmación. Arma todas las pestañas con los
   datos de hoy y muestra cuántas filas tiene cada una. Si algo falla en la base, falla acá
   y no se toca el Sheet. La *Vista previa* muestra las primeras 50 filas de cada pestaña
   tal como las recibiría el Sheet.
3. **Sincronizar ahora.** Pide confirmación (avisa que se pisa el contenido de las pestañas
   de la app). Escribe en el Sheet. Abrí el Sheet y mirá `Info`.

Si algo sale mal, el mensaje de la pantalla dice qué revisar (permiso, id incorrecto,
límite de Google). Si Google corta justo entre limpiar y escribir, las pestañas de la app
quedan vacías hasta la próxima sincronización: volvé a tocar *Sincronizar ahora*.
El resumen de la "Última ejecución" vive en la memoria del backend y se borra al reiniciarlo.

## Para quien lo opera por API

`POST /sync/sheets` con `{"simular": true}` o `{"simular": false}` (solo administradores).
Si las variables no están cargadas, el valor por defecto es simular y un pedido real
(`false`) se rechaza con 422. Si ya hay una corrida en curso responde 409; si Google falla,
502 con un mensaje seguro. `GET /sync/sheets/estado` lo puede leer cualquier usuario con
sesión. Detalle en [`backend/README.md`](../backend/README.md#google-sheet-display-copy-t6).

## Más adelante: que n8n lo dispare solo (trabajo futuro, no implementado)

n8n no escribe en el Sheet: solo tendría que llamar a `POST /sync/sheets` con
`{"simular": false}` en un horario (por ejemplo, cada noche). Hoy el endpoint exige una
sesión de usuario administrador, así que **para eso falta definir un token de servicio**
(una credencial propia de n8n con permiso solo para este endpoint). Eso no está hecho:
hay que acordarlo antes (dónde se guarda, cómo se rota) y agregarlo como una tarea aparte.

## Qué NO se verificó

- Ninguna llamada real a Google (no hay credenciales en este entorno): el cliente se probó
  contra un Google simulado y el intercambio de la clave de la cuenta de servicio contra un
  servidor de tokens falso.
- La primera sincronización real va a mostrar si hay detalles propios de Google (cuotas,
  límites de celdas) que el simulador no reproduce.
