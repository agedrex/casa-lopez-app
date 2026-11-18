# Formularios de consumos y herrajes

La planilla de papel de consumos y herrajes de cada artículo nuevo, hecha digital. **No calcula nada**: no hay costos, totales ni dólar. Las cantidades son exactamente lo que escribió una persona (`0,25` o `0.25`, hasta 6 enteros y 6 decimales). No toca `modelo`, `receta_linea` ni el motor de costeo. Nada se borra.

Código: `backend/src/backend/formulario.py` (reglas y API, el docstring del módulo es la referencia) y, en el frontend, `front/components/formulario-consumos.tsx` (la hoja), `front/app/(app)/taller/modelos/` (pantallas y acciones) y `front/lib/formularios.ts` (reglas puras: modo de la hoja, filas hacia la API). No existe una ruta `/formularios`: `front/lib/gerente-rutas.test.ts` fija que ya no es una página.

## Cómo nace: el modelo nuevo

Lo que llega al taller son **modelos**, no productos. Un modelo lo crea **solo el admin** (`/productos/modelos/nuevo`, sin foto en el alta: la sube después desde la ficha del modelo; el taller no crea modelos, solo recibe la hoja): **nombre**, **categoría**, tamaño (opcional) y **notas** (opcional, `modelo.nota`). No se piden consumos en el alta. `POST /productos/nuevo` (solo admin; el taller recibe 403) crea en una transacción el modelo (`validado = false`, consumos en NULL) y su formulario como **`BORRADOR`** con ese `modelo_id`: la hoja es la plantilla de siempre y nadie más que el admin la ve hasta que él la envía con el botón **«Enviar al taller»** (`POST /formularios/<FCO>/enviar`). El nombre va a `articulo` (en MAYÚSCULAS) y las notas se copian a la nota del formulario, que el taller lee arriba de la hoja y no puede editar. El taller completa las filas y el admin valida (una hoja sin ninguna cantidad mayor a 0 no se puede completar ni validar, 422 «La hoja no tiene ninguna cantidad cargada…»; el admin sí puede enviar una hoja en blanco al taller, que es el flujo normal): ahí las medidas y los insumos pasan al modelo y quedan como su receta. Después se crea el producto (cuero y color).

Un modelo vacío (cuero, forro, flex, goma EVA, herrajes e hilo y cemento todos faltantes o en 0, y sin insumos) tampoco se puede marcar como validado a mano (`POST /modelos/<MOD>/validado`, 422 «El modelo no tiene consumos cargados…»); quitar la marca siempre se puede. SUPUESTO: validar con Robert (qué cuenta como "vacío" y que la hoja que se valida solo necesite alguna cantidad; la validación de la hoja no exige que el modelo quede con cuero).

Tope por unidad (`MAX_CONSUMO_POR_UNIDAD` = 100, en `servicios.py`): al guardar un modelo (`POST /modelos`, consumos de un modelo y guardado de la grilla) el cuero, forro, flex y goma EVA no pueden superar 100 m² por unidad, y al guardar una hoja ninguna fila puede superar 100 (m² o unidades), salvo las de horas, mano de obra y empaque (`HS. DE TRABAJO`, `Y/O MANO DE OBRA TALLER`, `CORTE MANO DE OBRA`, `EMPAQUE`, constante `FILAS_SIN_TOPE`, derivada de `UNIDAD_DE_FILA`). Responde 422 («El consumo de cuero no puede superar 100 m² por unidad.» / «La cantidad de CUERO no puede superar 100 por unidad.»). Los importes (herrajes en USD, confección) no tienen tope. SUPUESTO: validar con Robert (el 100 y qué filas quedan exentas).

La ficha del modelo (`/productos/modelos/<código>`, admin) lista sus formularios con el estado y un link a la hoja (`GET /formularios?modelo=MOD-NNNN`). Los modelos viejos (del Excel) siguen con sus consumos y no tienen formulario. SUPUESTO (validar): la categoría es obligatoria al crear y tiene que existir (solo el admin crea categorías: `POST /categorias`); si el taller necesita otro dato del modelo, va en las notas.

### La plantilla y sus unidades

La lista precargada (`LINEAS_PRECARGADAS`: 13 consumos y 16 herrajes) es **solo la plantilla**: el admin la edita (agrega, quita y renombra filas, cambia cantidades) antes de enviarla y también en revisión (`COMPLETADO`); el taller hace lo mismo mientras la hoja está `ENVIADO`. Ya no existe la fila «DESPERDICIO 30%» («ya no aplica, hay que poner el consumo real de todo»). Las hojas creadas antes la conservan: mientras esté vacía no se muestra y al guardar la hoja se descarta; si alguien le escribió una cantidad o un comentario, se sigue viendo (no se pierde nada, no hay migración).

Cada fila tiene su unidad (`unidad` en la respuesta de la API, regla `formulario.unidad_de_fila`): `HS. DE TRABAJO` en **horas**, `Y/O MANO DE OBRA TALLER` y `CORTE MANO DE OBRA` en **$**, `EMPAQUE` en **unidades**, cualquier otra fila de consumo en **m²** y todo herraje en **unidades** (SUPUESTO: validar con Robert las unidades de esas cuatro filas). La pantalla muestra la unidad al lado de cada cantidad y renombrar una fila la vuelve a la unidad por defecto de su sección hasta que se guarda.

### Del alta a la validación

1. El **admin** crea el modelo (nombre, categoría, tamaño y notas): `POST /productos/nuevo` deja el modelo `validado = false` y la hoja en `BORRADOR`. El ID (`MOD-nnnn`) lo genera la app.
2. El admin abre la hoja, la **edita** (plantilla completa) y toca **«Enviar al taller»**: guarda lo que está en pantalla y pasa a `ENVIADO`; recién ahí el taller la ve.
3. El taller abre la **hoja** (`/taller/modelos/<FCO-nnnn>`): ID y nombre del modelo, foto (puede subirla), y las tablas de consumos y herrajes con nombre, cantidad (con su unidad) y comentario por fila (coma o punto decimal), «×» para quitar una fila y «+ Agregar fila» en cada tabla (una fila agregada sin nombre, cantidad ni comentario se ignora). "Guardar" y "Enviar" (completa la hoja y la pasa a revisión). La pantalla es compacta: filas bajas y sin títulos de más.
4. El admin ve el **estado de la hoja más nueva de cada modelo** en la grilla de Modelos (`/productos/modelos`, columna "Estado" justo después de "Modelo", con link a la hoja; "Sin hoja" si no tiene), abre una completada y la **valida** o la **devuelve** con un comentario. Al validar, las medidas pasan al modelo y la hoja muestra el link al modelo. La última columna de esa grilla se llama "Validación" (validado / faltan datos).
5. El taller sigue sus hojas en **Mis modelos** (`/taller/modelos`).

### Qué pasa al validar

Validar (`planificar_aplicacion`, en `formulario.py`) copia la hoja al modelo y **avisa lo que no pudo copiar**:

| Fila de la hoja | Va a |
|---|---|
| `CUERO`, `FLEX`, `GOMA EVA` | `cuero_m2_por_unidad`, `flex_m2_por_unidad`, `goma_eva_m2_por_unidad` (un 0 escrito significa «no lleva») |
| `FORRO / TELA`, `FORRO / POTRO` (una sola con cantidad) | `forro_m2_por_unidad` y, si el texto después de la barra coincide con el nombre corto o el nombre de un material de forro cotizable (Tela, Potro), `forro_id`. Con dos filas de forro con cantidad no se adivina: no se copia ninguna y se avisa. Sin material coincidente se copia la medida y se avisa que falta elegir el forro en el modelo |
| Herrajes y `FRISELINA`, `CARTÓN FIBRA`, `CARTULINA`, `MOIRE` | un `modelo_insumo` por material cuyo nombre o nombre corto coincide (sin mayúsculas, tildes, puntos ni `°`/`º`: `CIERRE N5` = `Cierre N°5`) |
| Cualquier otra fila con cantidad mayor a 0 (horas, mano de obra, corte, empaque, filas agregadas) | no se copia: el modelo no tiene un campo para eso |

La respuesta de `validar` trae `no_aplicadas` (`[{nombre, motivo}]`, en el orden de la hoja) y `sin_material` (solo los insumos sin material). El admin que vuelve a abrir una hoja `VALIDADO` ve la misma lista en «Estas filas no pasaron al modelo» (`GET /formularios/<FCO>` la recalcula con los materiales de hoy; solo para el admin). Qué pasaba en el caso de QA (CUERO 1,2; FORRO / TELA 0,8; FLEX 0,3; CIERRE N5 1; leído del código, no se reprodujo en staging): el forro nunca se copiaba (solo cuero, flex y goma EVA); un herraje con material coincidente se guarda como insumo y **no** en «Herrajes» (que es el monto en USD), y esa fila quedaba en «Falta el dato» aunque el insumo existiera: la ficha del modelo ahora dice «Según los insumos (ver abajo)» cuando hay insumos de esa etapa; y un herraje sin material coincidente no se guardaba y el aviso solo aparecía unos segundos (el panel de revisión se cerraba al refrescar), ahora queda la lista fija. Hoy la base no trae materiales de herrajes sembrados: un herraje sin material aparece en la lista para cargarlo en Materiales.

El alta completa con todos los consumos (`POST /modelos`) sigue en la API pero ya no tiene pantalla.

## Pantallas

| Ruta | Quién | Qué hace |
|---|---|---|
| `/taller/modelos` | admin, taller | Taller: **Mis modelos**, las hojas que recibe (`ENVIADO` y `COMPLETADO`). Admin: lista de hojas, abre en `COMPLETADO` con filtros por estado y "Todas"; ya no está en el menú, se llega desde la columna "Estado" de Modelos o desde la ficha del modelo. Nadie crea modelos desde acá. |
| `/taller/modelos/<FCO-nnnn>` | admin, taller | La hoja: ID y nombre del modelo en títulos separados, estado, foto, notas y las tablas CONSUMOS y HERRAJES (la unidad va en cada fila) con `COMENTARIOS / MODIFICACIONES`. Se edita entera (renombrar, "×", "+ Agregar fila", cantidades; ninguna fila es obligatoria): el admin en `BORRADOR`, `ENVIADO` y `COMPLETADO`, el taller solo en `ENVIADO`. En `BORRADOR` el admin tiene "Enviar al taller"; en `COMPLETADO`, "Guardar" y, abajo, "Validar" y "Devolver al taller" (con comentario; usan lo último guardado). Una hoja `VALIDADO` es de solo lectura y al admin le lista las filas que no pasaron al modelo. |
| Ficha del modelo (`/productos/modelos/<MOD>`) | admin | Lista las hojas del modelo con su estado y link. |

No hay pantalla de "Nuevo formulario" (`POST /formularios`, un borrador suelto) ni de duplicar: siguen solo en la API. La ficha del producto tampoco muestra el formulario validado.

Menú: el taller ve "Mis modelos" (en la barra de abajo del celular también); el admin ya no tiene "Hojas de consumos" en el menú: ve el estado en Modelos. El gerente no ve nada de esto. Al taller el formulario no le muestra costos.

## Flujo y botones

`BORRADOR` → (admin envía) `ENVIADO` → (taller completa) `COMPLETADO` → (admin valida) `VALIDADO`, o el admin lo devuelve a `ENVIADO` con un comentario que el taller ve arriba de la hoja.

| Botón | Quién | Cuándo |
|---|---|---|
| Guardar | admin (`BORRADOR`, `ENVIADO`, `COMPLETADO`); taller (`ENVIADO`) | el taller cambia solo las filas; el admin también artículo y nota (por API) |
| Enviar al taller | admin | `BORRADOR`; guarda primero lo que está en pantalla y pasa a `ENVIADO` |
| Enviar (completar) | taller (y admin en la API) | `ENVIADO`; guarda primero lo que se escribió y pasa a `COMPLETADO` |
| Devolver al taller | admin | `COMPLETADO`, con comentario |
| Validar | admin | `COMPLETADO` |
| Reenviar, Duplicar | admin (solo API) | `ENVIADO`; duplicar copia filas, cantidades y comentarios a un borrador nuevo |

Un formulario `VALIDADO` es de solo lectura para todos: para cambiarlo se duplica (por API).

SUPUESTOS (validar): el rol `taller` no está atado a un taller concreto: cualquier usuario `taller` ve las hojas `ENVIADO` y `COMPLETADO`, y además las que creó él (`creado_por`), en cualquier estado, para seguirlas hasta `VALIDADO` (solo lectura). La foto: el taller puede subirla a un modelo con una hoja `ENVIADO` (o creada por él, caso histórico); el admin a cualquiera (`POST /modelos/<MOD>/foto`, 403 si no).

Al validar, la fila `HS. DE TRABAJO` pasa a `horas_de_confeccion` del modelo (dato informativo, fuera del costo). SUPUESTO: validar con Robert.
