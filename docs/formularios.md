# Formularios de consumos y herrajes

La planilla de papel de consumos y herrajes de cada artículo nuevo, hecha digital. **No calcula nada**: no hay costos, totales ni dólar. Las cantidades son exactamente lo que escribió una persona (`0,25` o `0.25`, hasta 6 enteros y 6 decimales). No toca `modelo`, `receta_linea` ni el motor de costeo. Nada se borra.

Código: `backend/src/backend/formulario.py` (reglas y API, el docstring del módulo es la referencia) y, en el frontend, `front/components/formulario-consumos.tsx` (la hoja), `front/app/(app)/taller/modelos/` (pantallas y acciones) y `front/lib/formularios.ts` (reglas puras: modo de la hoja, filas hacia la API). No existe una ruta `/formularios`: `front/lib/gerente-rutas.test.ts` fija que ya no es una página.

## Cómo nace: el modelo nuevo

Lo que llega al taller son **modelos**, no productos. Un modelo lo puede crear el **taller** (pantalla "Nuevo modelo", `/taller/modelos/nuevo`, con **foto**) o el **admin** (`/productos/modelos/nuevo`, sin foto en el alta: la sube después desde la ficha del modelo): **nombre**, **categoría**, tamaño (opcional) y **notas** (opcional, `modelo.nota`). No se piden consumos en el alta. `POST /productos/nuevo` (admin y taller) crea en una transacción el modelo (`validado = false`, consumos en NULL) y su formulario ya `ENVIADO` con ese `modelo_id`; el nombre va a `articulo` (en MAYÚSCULAS) y las notas se copian a la nota del formulario, que el taller lee arriba de la hoja y no puede editar. El taller completa las filas y el admin valida: ahí las medidas y los insumos pasan al modelo y quedan como su receta. Después se crea el producto (cuero y color).

La ficha del modelo (`/productos/modelos/<código>`, admin) lista sus formularios con el estado y un link a la hoja (`GET /formularios?modelo=MOD-NNNN`). Los modelos viejos (del Excel) siguen con sus consumos y no tienen formulario. SUPUESTO (validar): la categoría es obligatoria al crear y tiene que existir (el taller no crea categorías: `POST /categorias` es solo admin); si el taller necesita otro dato del modelo, va en las notas.

### Alta desde el taller (modelo-taller-foto, T4)

1. **Nuevo modelo** (`/taller/modelos/nuevo`): nombre, categoría (lista existente), tamaño, notas y foto (JPG, PNG o WebP, hasta 5 MB). El ID (`MOD-nnnn`) lo genera la app.
2. Al guardar, primero se crea el modelo (`POST /productos/nuevo`, queda `validado = false` y la hoja `ENVIADO`, con `creado_por` = el usuario) y **después** se sube la foto (`POST /modelos/<MOD>/foto`). Si la foto falla, el modelo ya existe: se abre igual la hoja con el aviso "El modelo se creó, pero la foto no se pudo subir" y la foto se sube desde ahí.
3. La **hoja** (`/taller/modelos/<FCO-nnnn>`) muestra el nombre y el ID del modelo en títulos separados, la foto, y las tablas de consumos y herrajes con cantidad y comentario por fila (coma o punto decimal). "Guardar" y "Completar y enviar a revisión".
4. El admin ve las hojas completadas en **Hojas de consumos** (`/taller/modelos`, abre en `COMPLETADO`, con filtro por estado), abre una y la **valida** o la **devuelve** con un comentario. Al validar, las medidas pasan al modelo y la hoja muestra el link al modelo.
5. El taller sigue sus hojas en **Mis modelos** (`/taller/modelos`).

El alta completa con todos los consumos (`POST /modelos`) sigue en la API pero ya no tiene pantalla.

## Pantallas

| Ruta | Quién | Qué hace |
|---|---|---|
| `/taller/modelos` | admin, taller | Taller: **Mis modelos**, las hojas que ve (`ENVIADO`, `COMPLETADO` y las que creó, en cualquier estado). Admin: **Hojas de consumos**, abre en `COMPLETADO` con filtros por estado y "Todas". Botón "Nuevo modelo". |
| `/taller/modelos/nuevo` | admin, taller | Formulario de alta con foto (arriba). |
| `/taller/modelos/<FCO-nnnn>` | admin, taller | La hoja: ID y nombre del modelo en títulos separados, estado, foto, notas y las tablas CONSUMOS (m²) y HERRAJES (cantidad) con `COMENTARIOS / MODIFICACIONES`. El taller edita en `ENVIADO` ("Agregar fila" y "×" por fila; ninguna es obligatoria). El admin la ve de solo lectura y, en `COMPLETADO`, tiene "Validar" y "Devolver al taller" (con comentario). |
| Ficha del modelo (`/productos/modelos/<MOD>`) | admin | Lista las hojas del modelo con su estado y link. |

No hay pantalla de "Nuevo formulario" (`POST /formularios`, un borrador suelto) ni de duplicar: siguen solo en la API. La ficha del producto tampoco muestra el formulario validado.

Menú: el taller ve "Nuevo modelo" y "Mis modelos" (en la barra de abajo del celular también); el admin ve "Hojas de consumos" en Producción. El gerente no ve nada de esto. Al taller el formulario no le muestra costos. Limitación conocida: en la barra del celular, estando en "Nuevo modelo" se resalta "Mis modelos" (el resaltado de esa barra mira el menú del admin y toma el prefijo más largo).

## Flujo y botones

`BORRADOR` → (admin envía) `ENVIADO` → (taller completa) `COMPLETADO` → (admin valida) `VALIDADO`, o el admin lo devuelve a `ENVIADO` con un comentario que el taller ve arriba de la hoja.

| Botón | Quién | Cuándo |
|---|---|---|
| Guardar | taller (pantalla); admin y taller (API) | taller solo en `ENVIADO` (solo las filas); la API deja al admin hasta `COMPLETADO` pero la pantalla no lo ofrece |
| Completar y enviar a revisión | taller (y admin en la API) | `ENVIADO`; guarda primero lo que se escribió |
| Devolver al taller | admin | `COMPLETADO`, con comentario |
| Validar | admin | `COMPLETADO` |
| Enviar / Reenviar, Duplicar | admin (solo API) | `BORRADOR` / `ENVIADO`; duplicar copia filas, cantidades y comentarios a un borrador nuevo |

Un formulario `VALIDADO` es de solo lectura para todos: para cambiarlo se duplica (por API).

SUPUESTOS (validar): el rol `taller` no está atado a un taller concreto: cualquier usuario `taller` ve las hojas `ENVIADO` y `COMPLETADO`, y además las que creó él (`creado_por`), en cualquier estado, para seguirlas hasta `VALIDADO` (solo lectura). La foto: el taller puede subirla a un modelo con una hoja `ENVIADO` o creada por él; el admin a cualquiera (`POST /modelos/<MOD>/foto`, 403 si no).
