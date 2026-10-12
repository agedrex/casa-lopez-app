# WO 2: aplicar y verificar el esquema en staging

Esta guía prepara el siguiente pedido. **Todavía no se aplicaron estas
migraciones en Railway.** Se necesita autorización de Agustin antes de entrar
al backend de staging y modificar esa base. Un merge a `main` despliega la app;
las tablas se crean después, mediante una ejecución manual de Alembic.

## Configuración existente

- Proyecto Railway `casa-lopez`, environment `staging`.
- Servicio `backend`, con raíz de construcción `/backend`, y servicio PostgreSQL.
- `DATABASE_URL` está configurada en Railway mediante una referencia a Postgres.
  No se copia a archivos, terminales locales, logs ni esta guía.
- El arranque registrado del backend es
  `uv run fastapi run src/backend/main.py --host 0.0.0.0 --port $PORT`.
- Producción y `proto` quedan fuera de esta operación.
- Better Auth tendrá sus tablas en `public`; las de costos y `alembic_version`
  están exclusivamente en `costos`.

Agustin informó un `SELECT 1` exitoso por SSH. El repositorio documenta
`python -m backend.db_check`, pero no registra el comando SSH exacto, la carpeta
del contenedor ni la ruta de su Python. No se verificaron por una nueva conexión.

## Aplicación manual: solo con autorización posterior

1. Confirmar en Railway el proyecto, environment `staging` y servicio `backend`.
   Usar la sesión/credencial autorizada por Agustin y entrar mediante `railway ssh`.
2. Dentro del contenedor, confirmar el environment antes de cualquier migración:

   ```sh
   test "$RAILWAY_ENVIRONMENT_NAME" = staging || exit 1
   ```

3. Ubicar la carpeta que contiene `pyproject.toml`, `alembic.ini` y `migrations/`.
   La raíz de construcción `/backend` no demuestra la ruta interna del contenedor.
   Confirmar allí si existe `uv`. El arranque registrado lo utiliza.
4. Desde esa carpeta, ejecutar en orden:

   ```sh
   uv run alembic current
   uv run alembic upgrade head
   uv run alembic current
   uv run alembic check
   ```

   El resultado esperado de `current` es `0002_semillas (head)` y el de `check`
   es `No new upgrade operations detected`.

Si el contenedor no tiene `uv`, confirmar un Python que ya tenga las dependencias
del backend. Con ese ejecutable, el equivalente es `python -m alembic ...`.
No se da por probada una ruta `.venv/bin/python` que no figura en la evidencia.
No imprimir variables de conexión ni errores completos del driver.

## Verificación

En la misma carpeta y dentro de staging:

```sh
uv run python -m backend.verificar_db
uv run python -m backend.verificar_db --prueba-escritura
```

El script se niega a ejecutar si `RAILWAY_ENVIRONMENT_NAME` existe y no es
exactamente `staging`. Sin esa variable puede utilizarse contra una base local
autorizada. Muestra environment, revisión, tablas, conteos y OK/FALLA; no muestra
URLs ni hosts. Termina con código 0 cuando todas las comprobaciones pasan.

La prueba de escritura usa una transacción externa y SAVEPOINTs para las doce
restricciones. Crea datos demo, comprueba aceptación/rechazo y hace ROLLBACK al
final, incluso si falla. No quedan filas demo. PostgreSQL puede consumir números
de secuencias aunque una inserción se revierta; esto no altera filas de negocio.
Las semillas se comprueban antes de esas inserciones.

| Tabla | Conteo esperado |
|---|---:|
| etapa | 8 |
| material | 11 |
| proveedor | 2 |
| precio_material | 11 |
| tipo_cambio | 1 |
| parametro | 2 |
| categoria | 3 |

Además deben existir 11 tablas de dominio y `costos.alembic_version`. Lagarto
y yacaré deben estar bloqueados; GG debe valer 11 con estado `supuesto`.
El script también compara los contenidos completos de las siete tablas semilla
contra el SQL fuente, incluyendo precios, dólar y ganancia, aunque sus conteos
sean correctos. Solo comunica OK/FALLA; no imprime esos importes.

Los endpoints GET disponibles después de aplicar las migraciones son:

- `/db/estado`: revisión `0002_semillas` y `tablas_costos: 11`.
- `/catalogo/etapas`: ocho etapas ordenadas, sin precios.

Una falla de conexión responde 503 con un mensaje genérico. Ninguna de estas
rutas escribe ni aplica migraciones. `/api/health` sigue siendo el chequeo demo.

## Volver atrás

Con autorización y después de confirmar nuevamente staging:

```sh
uv run alembic current
uv run alembic downgrade -1
uv run alembic current
```

Desde head, esto elimina las semillas de `0002`, sin vaciar tablas ajenas.
Puede fallar de forma segura si nuevos datos dependen de esas semillas; no se
fuerza con CASCADE ni SQL manual. Antes de borrar, identifica Rouez y Acropol
por los vínculos y atributos exactos de sus dos precios semilla, porque sus
nombres no son únicos. Si faltan esas relaciones o la identidad resulta ambigua,
rechaza el downgrade sin eliminar filas. Un homónimo ajeno no se borra.
`downgrade base` elimina las 11 tablas y es
una operación destructiva que requiere autorización específica. Conserva el
schema y la tabla de versiones. Ante una falla se registra solo un error
sanitizado y la revisión; se propone una migración/fix, sin arreglar la base a mano.

## Qué no hacer

- Ejecutar contra producción, `proto` o una URL de Railway desde la computadora local.
- Usar `create_all()`, SQL manual o migraciones automáticas al arrancar/desplegar.
- Guardar secretos en `.env`, `alembic.ini`, commits o salidas de terminal.
- Ejecutar `railway run`, redeploys, cambios de variables o desplegar como parte
  de esta preparación local.

## Evidencia local disponible

Pasan 59 tests deterministas; los quince de integración se omiten por falta
de Postgres local descartable. Después de autorizar la sincronización de paquetes
en la venv existente, Alembic 1.20.0 generó correctamente el SQL real de upgrade
y los downgrades offline; `heads` identifica `0002_semillas`. El archivo temporal
`wo2-esquema.sql` contiene las 11 tablas y semillas esperadas, sin tocar `public`.
Generar SQL no lo aplica: siguen pendientes el ciclo de migraciones, conteos reales,
`alembic check` y protección de una tabla `public."user"` en Postgres descartable.
Ver [decisiones y comprobaciones](wo2-decisiones.md).

## Resultado de la verificación en staging
