# WO 2: decisiones del esquema de costos

Se implementa el DER v1 provisional, sin rediseñarlo: 11 tablas en `costos` y
dos migraciones versionadas. Este cambio prepara la base; no aplica migraciones
en Railway, no despliega y no implementa el importador ni el motor de costos.
La WO menciona Heroku; la plataforma del proyecto es Railway.

## Entrega y verificación actuales

La estrategia aprobada es **un solo PR a `main`**, manteniendo todos los
commits de trabajo en `feat/wo2-esquema-costos`. La guía de aproximadamente 400
líneas es un presupuesto orientativo para organizar la entrega, no un límite:
Agustin aprobó explícitamente la excepción `single-pr`. Un PR único puede formar
una unidad de revisión y merge mayor; se acepta porque cada merge puede iniciar
un deploy de staging en Railway y Agustin quiere controlar ese rollout.

La verificación local observada es **59 tests aprobados y 15 omitidos** porque
no hay PostgreSQL local descartable disponible. La generación del SQL offline
real de Alembic se completó correctamente. La validación con PostgreSQL en vivo
(incluidas las migraciones y las pruebas de integración omitidas) sigue
pendiente; no se ejecutó en staging ni en Railway.

## Decisiones acordadas

| Tema | Decisión y motivo |
|---|---|
| Migraciones | Alembic, revisiones `0001_esquema_costos` y `0002_semillas`, para mantener un historial legible. Es la única vía para crear el esquema. |
| Aislamiento | `MetaData(schema="costos")`, versiones en `costos` y filtro `include_name` que excluye cualquier otro schema. Better Auth queda en `public` y no pertenece a estas migraciones. |
| Primer arranque de Alembic | Crear `costos` y confirmar esa operación antes de configurar la migración online, porque Alembic necesita alojar allí su tabla de versiones. Offline, la primera sentencia es `CREATE SCHEMA IF NOT EXISTS costos`. |
| Conexión | Reutilizar `get_database_url()` y pasar su objeto `URL` directamente a `create_engine`. No escribir la URL en `alembic.ini` ni usar `config.set_main_option`; una contraseña con `%` no debe pasar por interpolación de configuración. |
| Identidades | `BigInteger` y `Identity(always=True)`, igual que el SQL probado. Las semillas resuelven referencias por claves naturales. |
| Precisión | `Numeric(..., asdecimal=True)` y `Decimal`; montos 14,4, consumos 10,4, dólar 12,4 y porcentajes 6,3. No se calcula dinero en el frontend. |
| Fechas | `DateTime(timezone=True)` y default del servidor `now()`. Las 11 tablas tienen `created_at`; solo `producto` tiene `updated_at`, actualizado por el ORM sin trigger. |
| Restricciones | Convención `pk_`, `fk_`, `uq_`, `ck_`, `ix_`; todos los CHECK tienen nombre. Se conservan `precio_material_uq` y `cotizacion_una_vigente`. |
| Historia | FKs sin `ON DELETE CASCADE`, para no eliminar dependencias históricas automáticamente. |
| Revisión de migraciones | Declaraciones de `0001` congeladas, independientes del modelo futuro. Comparación estructural con los modelos; cuando exista Postgres local, `alembic check` debe quedar limpio. |
| Semillas | SQL exacto del borrador, con prefijo `costos.` explícito y búsquedas por claves naturales. Como el nombre de proveedor no es único, el downgrade captura sus IDs mediante los precios semilla exactos antes de borrar; rechaza identidad ausente o ambigua. Nunca vacía tablas completas. |
| Staging | Aplicación manual dentro del backend mediante SSH, en otro pedido. Ninguna migración corre al arrancar la app ni en preDeploy. |
| API pública | Solo `/db/estado` y `/catalogo/etapas`, mediante GET; no exponen precios ni permiten escritura antes de Better Auth. Los errores de conexión son genéricos. |

## Diferencias entre fuentes

Orden aplicado: `docs/der.md` > `docs/der-borrador.sql` >
`docs/wo1-modelo-conceptual.md` > `AGENTS.md`. Los cuatro documentos se preservan.

| Diferencia | Resolución |
|---|---|
| SQL omite `created_at` en `etapa` y `cotizacion_linea`; DER §3 lo exige en todas las tablas. | Gana DER: se agrega en las dos tablas. |
| SQL no restringe los montos NULL de `cotizacion`; DER §4.9 dice «NULL solo en borrador». | Gana DER: CHECK `ck_cotizacion_costos_calculados` exige los cuatro montos fuera de borrador. |
| DER §4.8 no especifica nulabilidad de `fuente` y `fuente_detalle` en parámetros. | Se sigue el SQL y el prompt: `fuente NOT NULL`, `fuente_detalle` nullable. |
| AGENTS §7 habla de fuente «manual Excel» para precios importados. | Gana el SQL exacto: precios y parámetros usan `excel_migracion`; el dólar usa `manual Excel`. |
| DER §5.2 menciona presentación para cartón; la semilla SQL no aporta presentación ni cantidad. | Se conserva la semilla exacta solicitada: esos datos quedan NULL. No se inventan medidas ni precios de presentación. |
| WO1 §11 menciona `railway run`; el pedido actual exige ejecutar las migraciones dentro de Railway por SSH. | Se documenta SSH. No se reutiliza esa alternativa ni se ejecuta una conexión remota. |
| WO1 registra revisión con Robert como pendiente; el DER y el pedido actual registran autorización provisional. | Se trabaja con el DER provisional autorizado, sin cambiar su diseño. |

## Supuestos técnicos nuevos

- **SUPUESTO:** no son necesarias relaciones ORM de navegación para esta WO.
  Se declaran columnas, FKs y restricciones; los endpoints de lectura usan SELECT.
- **SUPUESTO:** el script de comprobación corresponde al estado inicial de WO 2.
  Sus conteos de semillas son exactos; después de incorporar datos reales pueden
  aumentar y será necesario revisar esa comprobación.
- **SUPUESTO:** se aceptan pruebas de integración solo con una
  `TEST_DATABASE_URL` explícita, para una base local descartable y fuera de Railway.
  Se rechazan destinos que no sean locales. No se reutiliza `DATABASE_URL` ambiente.
- La ruta del contenedor y el comando exacto del SSH anterior no están registrados
  en el repositorio. La guía describe cómo confirmarlos, sin presentar una ruta
  supuesta como verificada.

## Pendiente en backend: otras WO

Estas reglas no se implementan con triggers ni restricciones adicionales:

1. Un precio solo puede usarse si `unidad_precio = material.unidad_consumo`.
2. `material_id` es obligatorio cuando `etapa.requiere_material` lo indique.
3. Publicar una cotización cambia la vigente anterior a histórica en la misma
   transacción; una vigente o histórica no se edita.
4. Precios, dólar, parámetros y cotizaciones conservan historia mediante filas nuevas.
5. Solo el motor escribe montos calculados.

## Pruebas locales observadas

- Baseline: **27 tests pasan** antes de implementar.
- RED: las pruebas nuevas fallaron por ausencia de `backend.models` y
  `backend.verificar_db` antes de crear esos módulos.
- Suite inicial completa: **54 pasan y 13 se omiten**; las omitidas requieren
  `TEST_DATABASE_URL` para Postgres local descartable. No hay Docker en PATH ni
  en su ubicación habitual; tampoco Postgres en las ubicaciones habituales revisadas.
- Compilación Python y `uv lock --check --offline --directory backend`: pasan.
  La herramienta `uv` existente resolvió el lock sin instalar paquetes.
- `uv add --offline alembic` falló inicialmente porque Alembic no estaba en caché.
  Se declaró la dependencia y se resolvió el lock con la herramienta existente:
  Alembic 1.20.0 y Mako 1.4.3. En esa fase no se autorizó instalar paquetes.
- El intento inicial `python -m alembic upgrade head --sql` falló con
  `No module named alembic`. No se presenta como una ejecución exitosa.
- Se compiló una **referencia SQL** temporal de las declaraciones congeladas:
  `wo2-esquema-referencia.sql`, fuera del repositorio. Contiene 11 tablas,
  cuatro índices y siete INSERT de semillas. No fue generada por el runtime
  Alembic ni aplicada a una base. Las pruebas comprueban que la revisión
  congelada coincide con el modelo y que las semillas coinciden con el borrador.
- Pendientes actuales: upgrade/current/check/downgrade/re-upgrade contra una base,
  conteos reales y protección de `public."user"` en un Postgres local descartable.
  La generación real de SQL Alembic ya se completó en la autorización local posterior.
  No se instaló infraestructura ni se aplicó SQL en una base.

La advertencia existente de Starlette sobre httpx no falla los tests. La revisión
independiente y la aprobación previa al commit siguen siendo pasos separados.

## Corrección después de la revisión independiente

La primera revisión encontró dos problemas: borrar proveedores por un nombre
no único podía alcanzar un homónimo ajeno; comprobar conteos, exóticos y GG no
detectaba valores incorrectos en otras semillas. Se realizó una ronda acotada:

- `0002` identifica los dos precios semilla de refuerzos por material, proveedor,
  atributos, fecha y celda. Captura los IDs de precio y proveedor dentro de un
  bloque PostgreSQL `DO`, antes de cualquier DELETE. Bloquea cambios concurrentes
  en esas dos tablas durante la identificación y eliminación. Si falta una
  relación o hay varias candidatas, se niega a bajar la revisión.
- Se eliminan solo los precios capturados y los de claves exactas sin proveedor.
  Un proveedor homónimo ajeno queda fuera. Otro precio de un proveedor distinto
  tampoco se borra; si depende de un material semilla, la FK impide completar
  el downgrade y la transacción revierte. No se agregan restricciones ni IDs fijos.
- El script compara todo el catálogo inicial con los valores exactos del SQL:
  etapas, materiales, proveedores, precios y presentaciones, dólar, ambos
  parámetros y categorías. La salida sigue limitada a conteos y OK/FALLA,
  sin mostrar precios ni datos de conexión.
- RED observado: **5 regresiones fallaron** antes de corregir. GREEN enfocado:
  **21 tests pasan**. Suite final: **59 pasan y 15 se omiten**, con la advertencia
  ya existente. Dos casos nuevos requieren Postgres para comprobar conservación
  de homónimos y rechazo de proveedores ligados indistinguibles. Los cuatro casos
  de corrupción con igual conteo se prueban sin base: precio, dólar, ganancia y etapa.
- Compilación Python y hashes de las cuatro fuentes: pasan. La prueba del `DO`
  en PostgreSQL sigue pendiente; la prueba estructural
  no se presenta como ejecución de esa base. Se preparó una referencia temporal
  `wo2-semillas-downgrade-referencia.sql`, sin ejecutarla.

**SUPUESTO técnico:** el downgrade requiere conservar identificables las dos
relaciones originales entre precio y proveedor semilla. Si se modificaron o se
volvieron ambiguas, se requiere revisar la situación, sin reconstruir identidad
por nombre ni borrar filas como alternativa.

## Instalación local autorizada y SQL real de Alembic

La causa de `No module named alembic` era que resolver `uv.lock` no instala
paquetes. Se confirmó directamente: Python era el de `backend/.venv`, versión
3.13.16, y `find_spec('alembic')` devolvía ausencia. El ejecutable `uv` existente
está en las herramientas temporales del proyecto, versión 0.13.0; no estaba en PATH.

Agustin autorizó instalar exclusivamente las dependencias declaradas del backend,
sin commits ni infraestructura. `uv sync --frozen --offline --no-python-downloads
--directory backend` falló porque faltaban las wheels en caché. El intento con
descarga falló por el bloqueo de red del sandbox, error de socket 10013. La misma
operación, con aprobación del runtime, preparó dos paquetes e instaló tres:
Alembic 1.20.0, Mako 1.4.3 y el backend editable local reconstruido. No se instaló
otro Python, Postgres, Docker ni paquetes globales. El import de Alembic ahora
resuelve dentro de la misma `backend/.venv`.

Con una URL ficticia generada solo en el entorno del proceso, sin guardarla ni
mostrarla y sin conexión a una base, se observaron estos resultados:

| Comando con `backend/.venv/Scripts/python.exe -m alembic`, desde `backend/` | Resultado |
|---|---|
| `upgrade head --sql` | Código 0; archivo temporal `wo2-esquema.sql`. |
| `downgrade 0002_semillas:0001_esquema_costos --sql` | Código 0; archivo `wo2-semillas-downgrade.sql`, con captura de identidad y guardas. |
| `downgrade 0002_semillas:base --sql` | Código 0; archivo `wo2-downgrade-base.sql`, sin DROP SCHEMA. |
| `heads` | Código 0; `0002_semillas (head)`. |

El SQL real de upgrade comienza con `CREATE SCHEMA IF NOT EXISTS costos` y contiene
11 tablas de dominio más `alembic_version`, cuatro índices, 11 identidades ALWAYS,
11 timestamps `created_at` con zona horaria, todas las restricciones con nombre
y las siete inserciones exactas. Sus filas de semillas son 8 etapas, 11 materiales,
2 proveedores, 11 precios, 1 dólar, 2 parámetros y 3 categorías. No toca `public`.
Esta evidencia sustituye la referencia compilada para revisar el SQL emitido,
pero **no prueba que se haya aplicado correctamente en PostgreSQL**.

La suite posterior a la instalación volvió a dar **59 pasan, 15 omitidos y una
advertencia existente**. Compilación Python, `uv lock --check --offline` y hashes
de las cuatro fuentes pasan. Se conservan las omisiones de integración por falta
de Postgres local descartable; no se utilizaron conexiones Railway ni variables
reales de base. No se creó ningún commit.
