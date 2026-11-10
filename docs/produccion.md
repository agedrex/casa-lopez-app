# Promover a producción (con migraciones)

Guía para llevar un commit probado de `staging` a `production` **sin romper la base**.
Última revisión: 2026-11-10. No lleva valores secretos: las URLs y claves se piden a Railway o a Agustin.

Marcas: **[V]** = verificado (se leyó el repo, la documentación oficial o `--help` del CLI);
**[I]** = inferido o dato que nos pasaron, hay que confirmarlo en el momento.

---

## 0. Qué cambia con este proceso

- Se agregó `backend/railway.toml`. Le dice a Railway que, **antes de arrancar cada deploy del backend**, corra
  `uv run alembic upgrade head` (el "pre-deploy"). Si la migración falla, **el deploy no sigue** y queda la versión anterior
  andando [V: la documentación dice "If your command fails, it will not be retried and the deployment will not proceed"].
- También pide a Railway que, antes de pasar el tráfico a la versión nueva, espere que `/api/health` responda 2xx
  (hasta 120 s) [V].
- **No** define el comando de arranque (`startCommand`): sigue en el dashboard y no se toca.
- **Staging también lo va a correr en su próximo deploy.** Como staging ya está en `0007_proveedores_documentos` (head),
  `alembic upgrade head` no hace nada ("no-op"). [I: se confirma mirando el log del pre-deploy.]
- La guía manual `docs/wo2-staging.md` queda como alternativa si el pre-deploy no corre.

### Dos cosas que una persona tiene que hacer en el dashboard (el archivo solo no alcanza)

1. **Decirle a Railway dónde está el archivo.** Railway **no** sigue el "root directory" para este archivo: hay que poner la
   ruta absoluta `/backend/railway.toml` en la configuración del servicio `backend` [V: doc de monorepo, "You have to specify the
   absolute path ... /backend/railway.toml"]. Se hace en Settings del servicio, sección de Config as Code / "Railway Config File"
   [I: el nombre exacto del campo puede variar], **una vez por environment** (staging y production).
2. **Poner el mismo pre-deploy directo en el dashboard** (Settings → Deploy → Pre-deploy Command =
   `uv run alembic upgrade head`) y un **Pre-deploy Timeout** de 600 segundos, para que no cuelgue un deploy para siempre
   [V: por defecto el pre-deploy no tiene límite de tiempo; acepta 1 a 3600 s].
   Motivo: **Railway declaró "Config as Code" (railway.toml) como deprecado y dice que los archivos existentes dejan de leerse
   el 2026-12-01** [V]. Después de esa fecha el `railway.toml` puede ser ignorado y los deploys dejarían de migrar la base sin ningún error visible.
   Si el servicio `backend` cuenta como "legacy" (existente) y lo lee hasta esa fecha, no lo sé [I]. Lo más seguro es dejar
   el pre-deploy en el dashboard. El reemplazo oficial es Infrastructure as Code (`.railway/railway.ts`); migrar a eso queda como pendiente (sección 7).

Fuentes oficiales (consultadas 2026-11-10):

- Pre-deploy command: <https://docs.railway.com/deployments/pre-deploy-command>
- Config as Code (sintaxis de `preDeployCommand`, `healthcheckPath`, `healthcheckTimeout`, `restartPolicyType`): <https://docs.railway.com/config-as-code/reference>
- Monorepo / ruta absoluta del archivo: <https://docs.railway.com/deployments/monorepo>
- Healthchecks: <https://docs.railway.com/deployments/healthchecks>
- Backups de volúmenes: <https://docs.railway.com/volumes/backups>
- Point-in-Time Recovery: <https://docs.railway.com/volumes/point-in-time-recovery>
- Deprecación de Config as Code: <https://docs.railway.com/infrastructure-as-code>

---

## 1. Estado conocido

| Dato | Estado | Marca |
|---|---|---|
| Production tiene Postgres + backend + frontend, cada uno con URL pública | Lo informó Agustin | [I] |
| Base de production en la migración `0004_semillas_v3` | Lo informó Agustin; **se confirma con `alembic current` antes de promover** | [I] |
| Staging y `main` en `0007_proveedores_documentos` (head) | `main` [V: es la última de `backend/migrations/versions`]; staging [I] | [V]/[I] |
| Production **no** despliega sola (auto-deploy apagado) | README, sección Deployment | [V] |
| Un push a `main` despliega staging (si CI pasa) pero **no migra** (hasta este cambio) | README + `docs/wo2-staging.md` | [V] |
| El README dice que production "no tuvo un deploy exitoso todavía"; no coincide con una base ya migrada a 0004 | Hay que mirar `railway deployment list` | [I] |
| `/api/health` responde `{"status":"ok","mode":"demo"}` y **no mira la base** | `backend/src/backend/main.py` | [V] |
| `/db/estado` devuelve `alembic_revision` y `tablas_costos`; es público | `backend/src/backend/routers.py` | [V] |
| Better Auth vive en el schema `public`; Alembic solo mira el schema `costos` | `backend/migrations/env.py` (`include_name`) | [V] |

---

## 2. Qué hacen las migraciones 0005 a 0007 (las leí en `backend/migrations/versions`)

Promover el código sin migrar rompe proveedores (la tabla `costos.proveedor` no existe en production).

| Migración | Qué hace al subir | ¿Pierde datos? | Marca |
|---|---|---|---|
| `0005_gasto_reemplaza_a` | Agrega la columna `reemplaza_a_id` (admite NULL) a `gasto_periodo`, una FK a la misma tabla y un índice único parcial | **No.** Es aditiva; las filas existentes quedan con NULL | [V] |
| `0006_precio_venta` | Crea la tabla `precio_venta` y su índice | **No.** Tabla nueva | [V] |
| `0007_proveedores_documentos` | Crea las tablas `proveedor` y `documento_proveedor` (con los archivos en una columna `bytea`) y sus índices | **No.** Tablas nuevas | [V] |

Conclusión: **subir de 0004 a 0007 es aditivo**. No borra ni reescribe filas existentes [V]. Lo único que puede fallar es el
bloqueo breve de `gasto_periodo` mientras se agrega la columna y el índice (tabla chica, segundos) [I].

Lo que **sí** destruye datos es **bajar** (downgrade), ver sección 5.

---

## 3. Checklist previo a promover (todo tiene que estar tildado)

- [ ] **CI verde en `main`** para el commit que se va a promover (pestaña Actions de GitHub). Anotar el SHA: `git rev-parse origin/main`.
- [ ] **Ese mismo commit está andando bien en staging**: `/api/health` ok, `/db/estado` muestra `0007_proveedores_documentos`, login y lista de productos funcionan. No se promueve algo que no pasó por staging.
- [ ] **En staging ya corrió el pre-deploy** (log del deploy de staging con la línea de `alembic`, no-op). Si no corrió, el archivo no se está leyendo: resolver la sección 0 antes de seguir.
- [ ] **Backup de la base de production hecho y verificado** (sección 6). Sin backup verificado no se sigue.
- [ ] **`alembic current` de production** anotado (se espera `0004_semillas_v3`). Si da otra cosa, parar y avisar a Agustin:

  ```sh
  railway ssh -e production -s backend
  # ya dentro del contenedor:
  test "$RAILWAY_ENVIRONMENT_NAME" = production || exit 1
  uv run alembic current
  ```

  (La carpeta con `alembic.ini` dentro del contenedor no está documentada [I]; si `uv run` no la encuentra, `cd` a la carpeta que tenga `pyproject.toml`, ver `docs/wo2-staging.md` paso 3.)
- [ ] **Anotar cómo volver atrás**: el ID del deployment actual de production y su commit:

  ```sh
  railway deployment list -e production -s backend --limit 5
  ```

- [ ] Las migraciones 0005 a 0007 revisadas (sección 2): aditivas, sin pérdida de datos.
- [ ] Una persona (Agustin o quien él indique) **autorizó explícitamente** la promoción.

---

## 4. Secuencia de promoción (en este orden)

1. **Backup** de production (sección 6) y verificar que se puede leer.
2. **Confirmar que estás en production, no en staging.** Todos los comandos llevan `-e production` y se confirma el nombre
   antes de tocar nada:

   ```sh
   railway status -e production
   ```

3. **Migrar y desplegar.** Con el pre-deploy configurado (sección 0), **la migración corre sola al desplegar el backend**:

   ```sh
   railway redeploy -e production -s backend --from-source --commit <SHA_DE_MAIN_VERIFICADO>
   ```

   (Para esto, `--commit` despliega un commit puntual una sola vez; `--from-source` toma el código del repo [V: `railway redeploy --help`, CLI 5.71.0]. También se puede deployar desde el dashboard: servicio `backend` de production → Deployments → elegir/crear el deploy del commit.)

   Mirar el log del deploy: tienen que verse primero la migración (`Running upgrade 0004_semillas_v3 -> 0005...` hasta `0007...`) y después el arranque.

   ```sh
   railway logs -e production -s backend --deployment
   ```

   **Alternativa manual** (solo si el pre-deploy no corrió o está desactivado): migrar a mano **antes** de desplegar el código nuevo.

   ```sh
   railway ssh -e production -s backend
   # dentro del contenedor:
   test "$RAILWAY_ENVIRONMENT_NAME" = production || exit 1
   uv run alembic current
   uv run alembic upgrade head
   uv run alembic current
   ```

   Es seguro hacerlo antes del código nuevo porque 0005 a 0007 son aditivas: el código viejo (0004) sigue funcionando con la base nueva [I].
   Si falla a mitad de camino, **no insistas**: ir a la sección 5.

4. **Desplegar el frontend** con el mismo commit (si cambió algo en `front/`). El frontend no usa Alembic: sus tablas de Better Auth están en `public`.
5. **Smoke test** (reemplazar las URLs por las de production, que están en el dashboard; no las pegues en este archivo):

   ```sh
   curl -s -o /dev/null -w "%{http_code}\n" https://<URL_BACKEND_PRODUCTION>/api/health
   curl -s https://<URL_BACKEND_PRODUCTION>/db/estado
   ```

   Esperado: `200`, y `/db/estado` con `"ok":true` y `"alembic_revision":"0007_proveedores_documentos"`.
   Después, en el navegador con la URL del frontend de production: **iniciar sesión**, abrir la **lista de productos** y abrir la pantalla de **proveedores** (que es la que 0007 habilita). Si hay datos reales, ver que el producto cargado se vea igual que antes.
6. **Criterio de rollback**: si el pre-deploy falla, si `/db/estado` no muestra `0007...`, si el login falla, o si la lista de productos o proveedores da error 5xx → **rollback** (sección 5). No se "arregla sobre la marcha" en production.

---

## 5. Rollback

### Qué se puede

- **Volver el código atrás** (lo normal y lo primero que se hace). Redeploy del commit anterior anotado en el checklist:

  ```sh
  railway redeploy -e production -s backend --from-source --commit <SHA_ANTERIOR>
  ```

  Como 0005 a 0007 solo agregan cosas, el código viejo anda con la base ya migrada [I]. **Normalmente no hace falta bajar la base.**
- **Si el pre-deploy falló**: no hace falta rollback de código, porque Railway no pasó el tráfico a la versión nueva [V]. Se lee el log, se corrige en `main`, se prueba en staging y se vuelve a intentar.
- **Bajar migraciones** (`alembic downgrade`): **todas las migraciones del repo tienen `downgrade`** [V: las leí; 0001 a 0007]. Pero:

  | Bajar de → a | Qué pasa | Marca |
  |---|---|---|
  | 0007 → 0006 | Borra las tablas `proveedor` y `documento_proveedor`: **se pierden proveedores y las facturas/imágenes guardadas** | [V] |
  | 0006 → 0005 | Borra la tabla `precio_venta`: **se pierden todos los precios de venta** | [V] |
  | 0005 → 0004 | Borra la columna `reemplaza_a_id`: las correcciones de gastos quedan como filas normales y **se suman dos veces** (viejo y corregido) | [V] |
  | 0004 → 0003 | Borra solo las filas de semillas por su clave; **falla si otras tablas ya las referencian** | [V] |
  | 0003 → 0002 | Borra las tablas del DER v3; **el DER v1 no se recrea**: se pierde todo ese esquema y sus datos | [V] |

  Para volver de 0007 a 0004 recién migrada, la pérdida es solo lo que se cargó **después** de migrar. Se baja **solo con backup tomado inmediatamente antes** y con autorización de Agustin:

  ```sh
  railway ssh -e production -s backend
  # dentro del contenedor:
  test "$RAILWAY_ENVIRONMENT_NAME" = production || exit 1
  uv run alembic downgrade 0004_semillas_v3
  uv run alembic current
  ```

### Qué no se puede

- Recuperar datos borrados por un `downgrade` sin un backup. Un `downgrade` **no es reversible** si no hay copia.
- Deshacer una migración a medias con cambios fuera de Alembic. Nunca se cambia la base a mano.

### Restaurar desde backup

Se usa cuando la base quedó dañada o se perdieron datos. **Pierde todo lo escrito después del backup.**

- **Backup de volumen de Railway** (sección 6A): en el servicio Postgres de production → Backups → elegir la fecha → **Restore**. Railway monta un volumen nuevo con la copia, deja el anterior desmontado (no lo borra) y **deja el cambio pendiente de revisión**: hay que apretar **Deploy** para aplicarlo [V: doc de backups]. Solo restaura dentro del mismo proyecto y environment [V].
- **Backup `pg_dump`** (sección 6B): restaurar en una base nueva y apuntar el backend a ella, o `pg_restore` sobre la base. Siempre ensayarlo antes en una base descartable (sección 6C).

---

## 6. Backups

**Hallazgo [V: se buscó]:** el CLI de Railway (5.71.0) y el MCP de Railway **no tienen comandos para crear, listar ni restaurar backups**. Se hace en el dashboard o con `pg_dump`.

### 6A. Backups de volumen en el dashboard (los activa una persona)

1. Entrar a Railway → proyecto `casa-lopez` → environment **production** → servicio **Postgres**.
2. Pestaña **Backups**.
3. Apretar **Create backup** (manual) y esperar que aparezca en la lista con su fecha. Anotar la fecha y hora.
4. Activar los **schedules**. Los que ofrece Railway [V]: Diario (cada 24 h, se guarda 6 días), Semanal (cada 7 días, se guarda 27 días), Mensual (cada 30 días, se guarda 89 días). Se pueden elegir varios a la vez.

**PROPUESTA (no decidida):** activar **Diario + Semanal**, y hacer un **backup manual justo antes de cada promoción**. Los backups manuales están limitados al 50 % del tamaño del volumen [V]. Disponibilidad y costo según el plan de Railway [I]: confirmarlo con quien paga la cuenta. Los backups son incrementales y se cobran como el volumen [V].

Opcional: **Point-in-Time Recovery** (PITR). Archiva el WAL de Postgres en un bucket y permite restaurar a un momento exacto; el restore crea un servicio Postgres **nuevo** al lado y no toca el original [V: doc de PITR]. Se activa desde la pestaña Backups. Lleva un bucket y redeploy del Postgres (hay un momento de reinicio) [V], por eso conviene hacerlo en una ventana tranquila, no el día de una promoción.

Límites a tener presentes [V]: "wiping a volume deletes all backups" (borrar el volumen borra los backups) y la función está documentada como "todavía en desarrollo". Por eso conviene **además** tener un `pg_dump` fuera de Railway.

### 6B. Alternativa manual: `pg_dump`

- **¿Existe `pg_dump` en la imagen del backend?** No lo sé: la imagen del backend se arma con Railpack a partir de `backend/pyproject.toml`, y ahí (y en `uv.lock`) solo está el driver `psycopg[binary]`, que **no incluye** `pg_dump` [V: leí ambos archivos]. Que el contenedor igual lo tenga por el sistema base es [I]; no lo asumas: probalo con `railway ssh -e production -s backend -- pg_dump --version`.
- **El servicio Postgres de Railway sí lo tendría**, porque su imagen deriva de la imagen oficial de PostgreSQL [V: doc de PostgreSQL de Railway; que traiga `pg_dump` es [I]].

Dos formas (elegir una, **en el environment production**, sin imprimir contraseñas en pantalla ni en logs):

1. **Desde tu computadora**, con `pg_dump` local de la **misma versión mayor** que el Postgres de Railway. Necesita que el Postgres tenga *Public Access* activado (crea la variable `DATABASE_PUBLIC_URL`; el tráfico por ese proxy cobra egress) [V: doc de PostgreSQL de Railway]:

   ```sh
   mkdir -p ~/backups-casa-lopez
   railway run -e production -s Postgres -- sh -c 'pg_dump --format=custom --no-owner "$DATABASE_PUBLIC_URL" > ~/backups-casa-lopez/production-$(date +%Y%m%d-%H%M).dump'
   ```

   (`Postgres` es el nombre supuesto del servicio; confirmalo con `railway status -e production`. `railway run` pone las variables del servicio en un comando **local**: nunca uses `railway run env` ni `printenv` porque imprimen secretos [V: `railway run --help`].)
2. **Dentro del servicio Postgres** por `railway ssh`, escribiendo el archivo adentro y copiándolo después (requiere un mecanismo para bajar el archivo que no verifiqué [I]).

Para ambas: el dump incluye **todos los schemas**, o sea `costos` **y** `public` (tablas de Better Auth, usuarios y sesiones). Eso es lo que queremos.

**Verificar el backup** (esto es parte del checklist, no se saltea):

```sh
ls -lh ~/backups-casa-lopez/
pg_restore --list ~/backups-casa-lopez/production-<FECHA>.dump | head -40
pg_restore --list ~/backups-casa-lopez/production-<FECHA>.dump | grep -c "TABLE DATA"
```

El archivo no puede estar vacío, `--list` tiene que mostrar las tablas de `costos` (por ejemplo `producto`, `cotizacion`) y las de `public` (`user`, `session`), y la cuenta de `TABLE DATA` tiene que ser mayor que cero. Los dumps tienen datos de producción: **no se suben al repo ni a un chat**; se guardan en un lugar privado.

### 6C. Probar una restauración en una base descartable (local, nunca en Railway)

Se hace en tu computadora con un Postgres local descartable (el repo no usa Docker, ver `docs/wo2-decisiones.md`):

```sh
createdb casa_lopez_restore_test
pg_restore --no-owner --dbname casa_lopez_restore_test ~/backups-casa-lopez/production-<FECHA>.dump
cd backend
DATABASE_URL="postgresql+psycopg://localhost:5432/casa_lopez_restore_test" uv run alembic current
psql casa_lopez_restore_test -c "SELECT count(*) FROM costos.producto;"
```

Esperado: `alembic current` muestra la revisión que tenía production al momento del backup (`0004_semillas_v3` antes de la promoción) y el conteo de productos coincide con el de production. Al terminar: `dropdb casa_lopez_restore_test`.
(Si `pg_restore` avisa de extensiones o roles que no existen, anotá el mensaje; los avisos de roles son normales por `--no-owner`.)

---

## 7. Lo que NO hay que hacer

- ❌ **Migrar production a mano (o dejar que el pre-deploy lo haga) sin un backup verificado.**
- ❌ **Desplegar production sin que ese commit haya pasado por staging.** Staging es el ensayo.
- ❌ **Tocar el schema `public` o las tablas de Better Auth (`user`, `session`, `account`, `verification`) con Alembic.** Eso lo maneja `pnpm auth:migrate` desde `front/`; Alembic solo mira `costos` [V: `backend/migrations/env.py`].
- ❌ **Cambiar la base a mano** (`psql` con `ALTER`/`DROP`) para "arreglar" algo. Todo cambio es una migración.
- ❌ **Correr `alembic downgrade` en production** sin backup tomado en el momento y sin autorización explícita.
- ❌ **Correr scripts de `staging` (cargar ejemplo, importador) contra production.** Los scripts se niegan si `RAILWAY_ENVIRONMENT_NAME` no es `staging` [V: README y docs]; no intentes saltearlo.
- ❌ **Activar el auto-deploy de production.** Sigue manual a propósito [V: README].
- ❌ **Pegar `DATABASE_URL`, `DATABASE_PUBLIC_URL`, contraseñas o tokens** en el repo, en chats, en logs o en este archivo.
- ❌ **Cambiar el `startCommand`** del dashboard como parte de este proceso.

---

## 8. Pendientes de la auditoría que siguen abiertos

Este cambio **no** los resuelve; quedan como trabajo aparte.

| # | Pendiente | Por qué importa |
|---|---|---|
| 1 | Healthcheck real que mire la base | `/api/health` hoy responde ok aunque la base esté caída [V]; el healthcheck de Railway no detecta ese caso |
| 2 | `/db/estado` es público | Muestra la revisión de Alembic y la cantidad de tablas a cualquiera [V]. Proteger o sacar de production |
| 3 | Rutas demo | `/api/demo/*` sigue en el backend [V]; no deberían estar en production |
| 4 | Cabeceras de seguridad | No hay middleware de cabeceras de seguridad en `main.py` [V: solo CORS] |
| 5 | Rotar la credencial de admin de staging | Pendiente de la auditoría; hacerlo antes de usar datos reales |
| 6 | Observabilidad | Sin alertas ni monitoreo continuo: Railway no vigila el healthcheck después del deploy [V: doc de healthchecks] |
| 7 | CI sin Postgres | El CI no corre los tests de integración (se saltean sin `TEST_DATABASE_URL`) [V: `.github/workflows/ci.yml` + tests] |
| 8 | Cron del dólar | La actualización automática del dólar no está programada |
| 9 | Migrar `railway.toml` a Infrastructure as Code | Config as Code deja de leerse el **2026-12-01** [V]; mientras tanto el pre-deploy va también en el dashboard (sección 0) |
