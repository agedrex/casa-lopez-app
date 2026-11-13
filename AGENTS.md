# AGENTS.md — Casa López · App de costos

> Contexto obligatorio para cualquier agente de código que trabaje en este repo (Codex CLI, Gentle AI, etc.).
> Leelo entero antes de tocar el DER, el importador o el motor de costeo.
> Última revisión: **2026-11-10 (v6)**. Antes: v5 (2026-10-12, sincronizada con el DER v1 de la WO 1). Fuente original: Excel `COSTOS1 en vigencia al 01-09-2026.xlsx`, meeting del equipo e informe de hallazgos. Desde 2026-10-27 la fuente del modelo es la plantilla v4.1 (DER v3), ver sección 5.
> **Qué cambió en la v6:** el DER vigente es el v3 (28 tablas, migraciones 0001 a 0007), no el v1; la prueba de paridad con el Excel se descartó y el GG de 11 % se eliminó del costo; el importador real es `generate_seed_v3.py` + `importar_productos.py`; roles `admin`, `gerente` y `taller`; sección nueva "Producción y despliegue" (9.2); las secciones 3 y 4 quedan como historia del Excel viejo.
> **Marcas:** **[V]** = verificado en esta revisión contra el archivo citado del repo. **SUPUESTO** = lo dijo el equipo o es inferido, sin verificar desde el repo: confirmarlo antes de apoyarse en eso.

| Secciones | Estado |
|---|---|
| 1, 2, 5, 5.1, 6, 7, 8, 9, 10, 11 | **Vigentes**: describen el sistema real (DER v3). |
| 3 y 4 | **Historia del Excel viejo.** Explican de dónde vienen los datos y qué trampas tiene leerlos. No son el modelo ni las reglas de costo vigentes. |
| Anexo | Memorias para Engram. Las marcadas "(histórico)" ya no rigen. |

---

## 1. Qué estamos construyendo y para quién

**Cliente:** Casa López, casa de cueros y marroquinería desde 1939. Tiene tienda propia; fabrica inventario para vender (no produce estrictamente a demanda).

**Problema:** todos los costos viven en un Excel que solo entiende Gerardo, y Gerardo se va de la empresa. No hay SKUs claros, ni historial de precios, ni fechas, ni seguimiento de costo real o margen real. El costo "se actualiza" cambiando el dólar a mano y el resto es una caja negra.

**Objetivo:** pasar ese Excel a una web app estandarizada donde cualquiera pueda cotizar un producto sin depender de Gerardo, con los datos en casa para integrarlos después con otros sistemas (el ERP de la tienda).

**Personas:**
| Quién | Rol | Qué le importa |
|---|---|---|
| Gerardo | Arma los costos en el Excel. Se va pronto. | Es la única fuente de verdad sobre las reglas. Todo lo dudoso se valida con él. |
| Alejandro | Dueño / gerente de tienda. Recibe el producto, lo etiqueta y lo da de alta en su ERP. | No quiere pensar en esto: quiere información masticada y **margen real**. |
| Artesano interno | Cotiza mano de obra en horas. | — |
| Talleres externos | Cobran por producto o por lote. Es el costo real de M.O. | — |
| Agustin | Forward deployment engineer, dueño del proyecto. | Nuevo en modelado de datos. Quiere cero errores arrastrados. |
| Robert | Compañero y jefe de Agustin (equipo de La Fábrica). | Define alcance, prioridades y decisiones de producto. Lo que no es una regla del Excel sino una decisión del proyecto se habla con él. |

**Sprint inicial:** 3 semanas (15 días hábiles) desde el 2026-10-11, fecha del primer commit [V: `git log`]. Cierre esperado: **Gerardo cotiza 2 o 3 productos nuevos sin abrir el Excel.** SUPUESTO: en el repo no hay evidencia de que esa prueba con Gerardo ya se hizo; preguntarle a Agustin.

**Alcance de la primera versión:** "una forma más amena de usar este Excel", no un cambio del proceso. Se respetan las etapas (es el idioma de Gerardo y de los talleres) y se les ponen nombres claros. El valor nuevo es lo que el Excel no tiene: fechas, historia, costo real y margen real. **El alcance se movió el 2026-10-27:** la fuente de datos pasó a ser la plantilla v4.1 y se dejaron las reglas del Excel viejo donde chocan con ella (GG de 11 %, prueba de paridad); ver sección 5 y `odd/tasks/app-casa-lopez-v3.md` [V].

**Métrica tentativa:** qué porcentaje de las tareas de Gerardo se automatiza o mejora (sin definir del todo).

**Riesgo principal:** que Gerardo no tenga tiempo antes de irse. Todo lo que el código necesite de él se junta en una lista de preguntas y se prioriza lo bloqueante.

**Stack en uso [V: `front/package.json`, `backend/pyproject.toml`, `README.md`]:** Next.js 16 + React 19 + Better Auth (`front/`, pnpm) · FastAPI + SQLAlchemy 2 + Alembic (`backend/`, Python 3.13, uv) · Postgres, todo en Railway. Integraciones: dólar del BNA (`docs/dolar-bna.md`), voz y OCR de facturas con un LLM (`docs/voz.md`), copia de solo vista a un Google Sheet (`docs/sheets-sync.md`). El LLM **nunca** calcula costos: interpreta o lee texto y una persona confirma.

**Gestión del trabajo:** el MCP de La Fábrica (kanban, work orders, documentos fundacionales y blueprints). Git y GitHub para el código.

---

## 2. Reglas de oro (no negociables)

1. **Sin paridad con el Excel (decisión del usuario, 2026-10-28).** Se descartó comparar el motor contra el Excel viejo: el motor se prueba regla por regla [V: `odd/tasks/app-casa-lopez-v3.md`, T2 y L6]. Los valores del Excel viejo quedan como referencia (`modelo.excel_viejo_*`, parámetros `GG_PCT_EXCEL` y `DOLAR_PARIDAD`), nunca como verdad. Las mejoras entran como parámetros, nunca cambiando una fórmula en silencio.
2. **No inventar reglas de negocio.** Si algo no está en este archivo o en el Excel, no se asume: se marca como `SUPUESTO` y se pregunta. Ver la sección 6.
3. **Dinero con `Decimal`, nunca `float`.** Python `decimal.Decimal`, Postgres `NUMERIC`. En el frontend no se calcula plata: el backend devuelve los montos ya calculados como string. El recálculo en vivo del formulario llama a la API (o a un endpoint de "previsualizar" sin guardar).
4. **Las cotizaciones son inmutables.** Una cotización guardada no se edita ni se pisa: se agrega otra. Hay una por producto + fecha + tipo (`INICIAL`, `RECOTIZACION`, `FINAL`) y repetirla es un conflicto [V: `servicios.guardar_cotizacion`, `models.Cotizacion`]. No hay marca "vigente". Cada una guarda una foto del dólar, un monto por etapa y los totales; **no** guarda precios ni consumos unitarios, que salen de las tablas con historia (`precio_material`, `tipo_cambio`).
5. **Nada subjetivo sin consenso.** Si una decisión depende del criterio de una persona (qué producto es "comparable", si un consumo es razonable, qué M.O. usar), la app no la toma sola: la propone y una persona la confirma.
6. **El motor es una función pura.** Recibe datos, devuelve un desglose. No lee la base, no lee la hora, no llama a internet [V: docstring de `backend/src/backend/costeo.py`]. Así se testea sin base ni reloj.
7. **Cada cambio al motor corre los tests del backend** (`uv run --directory backend pytest -q`; `test_costeo.py` y `test_receta.py` fijan cada regla). Si un test se rompe, el cambio no entra.
8. **El motor es el único que calcula.** Los montos por etapa, el IVA de compras, los arreglos y el total en ARS y USD los calcula el backend. Ni el frontend ni un usuario pueden escribirlos. Si alguien quiere otro número, cambia un dato de entrada y queda registrado quién y por qué.
9. **Cada precio guarda su moneda y su unidad de origen.** Nada se convierte "por las dudas". La conversión a pesos se hace en el motor, con el dólar de la cotización, solo cuando el material está en USD.
10. **Todo tiene fecha.** Precios, dólar, costos fijos, precios de venta, cotizaciones y órdenes. Sin fecha no hay margen real. Excepción conocida: los parámetros se editan en el lugar, sin historial (el valor anterior solo queda en el log) [V: `odd/tasks/app-casa-lopez-v3.md`, L15].
11. **Nada se borra.** Archivar un producto lo oculta de las listas, pero conserva su historia. Lo que se corrige en la migración queda marcado, no se tira.

---

## 3. Cómo funciona el Excel (verificado celda por celda)

> **Historia del Excel viejo, no el modelo vigente.** Las secciones 3 y 4 describen cómo funciona `COSTOS1 en vigencia al 01-09-2026.xlsx` (hoja `Marroquineria1`). Se conservan porque explican el origen de los datos (los consumos de los 325 modelos del seed vienen de ahí: `origen_de_los_consumos = EXCEL` [V: `test_seeds.py`]) y las trampas al leerlo. Las reglas de costo de ese Excel (GG de 11 %, REB, PREP y M.O. por separado, comparación contra el Excel) **ya no rigen**: ver 3.5.4 y la sección 5.

Hoja `Marroquineria1`. Tabla central: encabezado en la fila 21, productos en las filas 22 a 347. Cada fila es un producto y las columnas son etapas.

### 3.1 Parámetros globales (arriba de la hoja)
| Celda | Qué es | Valor actual | Nota |
|---|---|---|---|
| G15 | Cotización del dólar ("Cotiz") | 1545 | Manual. Uno solo para todo. |
| G16 | GG | 11 (%) | Probablemente Gastos Generales, **no IVA**. Sin validar. |
| G17 | "Ganancia 27%" | **0** | Ninguna fórmula lo usa. El Excel termina en costo, no en precio. |
| I3 | "desperdicio en cuero 30 %" | texto | Es una nota, **no se aplica en ninguna fórmula**. |

### 3.2 Tabla MATERIAL (E7:H14)
| Código | Material | USD | ARS |
|---|---|---|---|
| Cuero 1 | Estándar (Anilina Fina Lisa) | 24 | `=G7*G15` |
| Cuero 2 | Carpincho | 80 | `=G8*G15` |
| Cuero 3 | Lagarto | `"usd 26 x cm"` (texto) | da `#VALUE!` |
| Cuero 4 | Yacaré overo | `"usd 3 x cm"` (texto) | da `#VALUE!` |
| Cuero 5 | Grano largo | 23 | **34040 tipeado** (23 × 1545 daría 35535) |
| Cuero 6 | Camuflado / vaca con pelo | 35 | `=G12*G15` |
| Forro 1 | Potro / Popurri / Cuero | 19 | `=G13*G15` |
| Forro 2 | Tela forrería | `=X7` | `=G14*G15` (en la práctica, ARS por m² de la tabla de insumos) |

### 3.3 Tabla de insumos en pesos (S4:X10)
Proveedor y fecha en S (ej. "3/9/26 Rouez", "3/9/26 Acropol"), precio por rollo en V, precio por m² **tipeado a mano** en W, y X = W / dólar.
- Flex 1 × 1,40 m: rollo 14000, m² 10000.
- Goma EVA 1 × 1,40 × 2 mm: rollo 8200, m² 5857.
- Tela forro 1 × 1,50: rollo 6080, m² 4053.
- Cartón 1,5 mm: aparece, **no se usa** en ninguna fórmula.

### 3.4 Etapas de la tabla central (fila 22 como ejemplo)
| Etapa | Columnas | Fórmula | Moneda real |
|---|---|---|---|
| 1. Cuero (capa externa) | H tipo, I nombre, J consumo m², K precio, **L total** | `K = CHOOSE(H, H7..H13)`, `L = K × J` | USD × dólar |
| 2. Forro (capa interna) | M tipo, N nombre, O consumo, P precio, **Q total** | `P = CHOOSE(M, H13, H14)`, `Q = P × O` | Potro en USD; tela en ARS |
| 3a. Herrajes | R (USD), **S total** | `S = R × dólar` | USD |
| 3b. Flex | T consumo, U, V, **W total** | `W = T × (W5 / dólar) × dólar` | **ARS** (el paso por USD se cancela) |
| 3c. Goma EVA | X consumo, Y, Z, **AA total** | igual que flex con W6 | **ARS** |
| 4. Refinamiento | **AB** corte, **AC** reb, **AD** prep | números tipeados | ARS |
| 5. Mano de obra | **AE** | número tipeado | ARS |
| Subtotal | **AF** | `SUM(L, Q, S, W, AA, AB, AC, AD, AE)` | ARS |
| GG | **AG** | `IF(AF>1, AF × G16/100, "consumo")` | ARS |
| Costo | **AH** | `AF + AG` | ARS |
| Costo en USD | **AI** | `AH / dólar` | USD |

**Ejemplo real, fila 22 (Portafolio Simple Ch., modelo 6):** cuero 37080 × 0,25 = 9270; forro tela 4053 × 0,2 = 810,6; herrajes 4 USD = 6180; flex 0,45 m² = 4500; goma 0; corte 3000 + reb 1500 + prep 1500; M.O. 12000. Subtotal 38760,6; GG 4263,67; **costo 43024,27 ARS = 27,85 USD**. Fue el primer caso de la prueba de paridad, que se descartó (sección 8); hoy no es un test.

### 3.5 Fórmula del Excel viejo (la que se iba a usar para la paridad, descartada)
```
subtotal = cuero + forro + herrajes + flex + goma_eva + corte + reb + prep + mano_de_obra
gg       = subtotal × (gg_pct / 100)          # gg_pct = 11 hoy, parámetro
costo    = subtotal + gg                       # costo en ARS
costo_usd = costo / dolar
```
- `cuero = precio_cuero_ars × consumo_cuero`, con `precio_cuero_ars = precio_usd × dolar` (salvo grano largo, ver trampas).
- `herrajes = herrajes_usd × dolar`.
- `flex = consumo_flex × precio_flex_ars_m2` y `goma = consumo_goma × precio_goma_ars_m2`. Modelarlos en ARS directamente.
- Ganancia y desperdicio **no entran** en el costo de paridad. Existen como parámetros con valor 0 o desactivados.

### 3.5.1 Segundo caso de paridad: recotización (histórico)
Misma fila 22 con dólar 1700: cuero 0,25 × 24 × 1700 = 10200; herrajes 4 × 1700 = 6800; forro, flex, corte, reb, prep y M.O. **no cambian** (están en pesos). Subtotal 40310,6 → **costo 44744,77 ARS = 26,32 USD**. Ilustra que cada insumo tiene su moneda (el motor vigente conserva esa regla: un precio en USD se multiplica por el dólar de la fecha y uno en ARS no). Fíjate que el costo en USD **baja** cuando sube el dólar, porque la parte en pesos pesa menos en dólares.

### 3.5.2 Cuánto pesa cada etapa (mediana sobre el subtotal)
Cuero 38 %, M.O. 25 %, herrajes 12 %, corte 6,5 %, reb 3,3 %, prep 3,3 %, forro 2,5 %; flex y goma eva están en cero en la mitad de los productos. **Cuero y M.O. son el 63 % del costo:** ahí van las validaciones y las alertas de valores raros. El consumo de forro es, en mediana, el 69 % del de cuero.

### 3.5.3 Lo que de verdad hay en cada etapa
- **Herrajes (R)** no son solo herrajes: el encabezado dice "Herraj. hilo cemento" y la nota S11 dice "Hilo, cemento va en HERRAJES usd 2". Es un monto global en USD sin detalle (0 a 30, casi siempre 1 a 8). Se migra como una línea global; el detalle por herraje es una mejora futura.
- **Reb y prep valen 1500 en 325 de 326 productos; corte vale 3000 en 287** (el resto 2000, 2500 o 4000). En la práctica son valores por defecto, no datos del producto. Supuesto: reb = rebajado, prep = preparación de piezas.
- **M.O. tiende a escalones, pero no los respeta:** 36 valores distintos en 342 filas. Solo 212 usan 6000, 8000, 12000 o 20000; el resto tiene 10000, 14000, 15000, 16000, 18000, 30000, 50000 (AE122) y valores sueltos como 6885 o 3915. **Se importa el valor de cada fila tal cual.** La tabla "tentativos" (G368:J370, 31/07/2024) es solo una referencia.
- **La columna AE tiene 8 comentarios de 2016-2017** con nombres de talleres y lo que se pagó (ej. AE53: "Sanchez 1,000 pidió, pagamos 750"). Es la única traza de costo real del archivo: **el importador tiene que leer los comentarios de celda** y guardarlos como nota.
- **Columnas sin título:** B tiene nombres de personas en 35 filas (Fabián, Adrián, Lorena, Mariano, Lucio, Carrión; supuesto: taller o artesano), D tiene "barba", "Mariano", "Fabian" (34 filas, significado desconocido), E tiene una fecha en 116 filas, de 22/09/2022 a 25/08/2026 (supuesto: fecha de cotización).
- **Fila 242** está pegada como valores con precios de otro dólar (cuero 33600, potro 26600).
- **Nombres definidos rotos** ("este", "Título1", "VentasDePuntoDeEquilibrio") y celdas sueltas B1 y F20: ignorar.

### 3.5.4 Qué quedó de esa fórmula en el motor vigente (`costeo.py`, `receta.py`)
Todo [V: `backend/src/backend/costeo.py`, `receta.py`, `servicios.cargar_contexto`, `test_costeo.py`]:
- **No hay GG.** El motor no aplica ningún porcentaje de gastos generales (`test_no_gg_is_applied_total_is_subtotal_without_extras`). El 11 % queda solo como parámetro de referencia `GG_PCT_EXCEL` y el dólar 1545 como `DOLAR_PARIDAD` [V: `seed_v3.json`]. Los costos fijos de la fábrica y la tienda viven en `gasto_periodo` y alimentan el panel de costo-volumen, no el costo del producto. SUPUESTO: que ese sea el reemplazo de hecho del GG; sin confirmar con Gerardo.
- **Línea de material** = `consumo × (1 + desperdicio) × precio`. El precio en USD se multiplica por el dólar vigente a la fecha de la cotización (el más nuevo que no sea posterior); el precio en ARS no se toca. Sin dólar o sin precio para esa fecha, la cotización queda incompleta con un aviso. El "costo de hoy" (ficha, listas, panel) se calcula con la fecha real de hoy y el dólar más nuevo hasta esa fecha (`servicios._hoy`; SUPUESTO: validar): un precio cargado hoy cuenta enseguida, sin esperar a un dólar nuevo. Sin ningún dólar anterior a hoy usa el más nuevo cargado.
- **Ocho etapas:** CUERO, FORRO, FLEX, GOMA_EVA, HERRAJES, HILO_CEMENTO, CORTE y CONFECCION. HILO_CEMENTO se separó de HERRAJES; CORTE vale siempre 0 (el sueldo de Alderete es un costo fijo); CONFECCION reemplaza a REB + PREP + M.O. y vale 0 si el producto lo confecciona la casa (`INTERNA`).
- **Insumos del modelo** (`modelo_insumo`, migración 0019): cada insumo es una línea más, `cantidad × precio unitario` con la misma búsqueda de precio (genérico, el más nuevo no posterior), la misma moneda y el mismo dólar que una línea de material, en la etapa de su material. Sin precio, la cotización queda incompleta con el aviso "Sin precio para MAT-… a esa fecha". Sin doble conteo: si el modelo tiene insumos en HERRAJES, reemplazan a `herrajes_usd_por_unidad`; si tienen en HILO_CEMENTO, reemplazan a `hilo_y_cemento` (y no sale el aviso "Falta hilo y cemento"). Un modelo sin insumos se costea como siempre. Se cargan al validar la hoja de consumos (filas de HERRAJE y FRISELINA, CARTÓN FIBRA, CARTULINA y MOIRE con cantidad) si el nombre coincide con un material cotizable; SUPUESTO: validar, la coincidencia por nombre es una convención nuestra.
- **Confección externa** = promedio del precio por unidad del lote más nuevo (el pagado; si no hay, el cotizado); sin lotes, la estimación del modelo (`confeccion_estimada_ars`).
- **Total** = subtotal de etapas + componentes de kit + IVA de compras (solo si el impuesto `IVA` está marcado como costo; hoy no) + arreglos (`ARREGLOS_PCT`, hoy 0). USD = total ÷ dólar.
- **Desperdicio:** `FACTOR_DESPERDICIO_DEFAULT` (hoy 0) o `material.desperdicio_manual` si el material lo tiene. Sigue sin aplicarse el 30 % del Excel.

### 3.6 Otros bloques de la hoja
- **Filas 351-366: variantes.** Código de modelo con barra (`103/1`, `2538/3`): son variantes de un producto base. En el DER v1 era `producto.producto_base_id`; el DER v3 no tiene esa columna [V: `models.py`] y los 325 modelos del seed cubren solo las filas 22 a 347, sin las variantes 351-366 [V: `seed_v3.json`]. SUPUESTO: cómo se van a cargar las variantes sigue sin definirse.
- **Filas 368-370: M.O. "tentativa" por tamaño** (fecha 31/7/2024): Bolso grande 20000, Portafolio mediano 12000, Cartera chica 8000. Es una referencia, no una regla.
- **Filas 374-381: tabla de Necesaires.** Es un duplicado de filas del bloque central con dos columnas extra (AJ costo anterior, AK % de variación). **No es otra tabla:** "necesaire" es una categoría de producto. Al importar, deduplicar.
- **Zona AJ373 en adelante:** ignorar (decisión de Agustin).
- **Hoja `Hoja1`:** vacía.
- Columnas A a E traen datos sueltos (índice, notas como "esta", nombres de personas, fechas). Se importan como notas o metadatos, no como reglas.

### 3.7 Reglas implícitas de Gerardo (su baseline)

Son las reglas que el Excel aplica sin decirlo: de fórmula, de criterio o de forma de pensar. Sirven para entender cómo cotiza Gerardo hoy y como referencia del origen de los datos (la paridad con el Excel se descartó, sección 8). No son reglas aprobadas para la app: las que son criterio se convierten en sugerencias o parámetros, nunca en automatismos, hasta que Gerardo y Alejandro las confirmen.

- **Observada:** verificada en celdas, fórmulas, valores o comentarios del Excel, o dicha textualmente en la meeting.
- **Inferida:** interpretación nuestra a partir de un patrón. Hay que confirmarla con Gerardo.

#### A. Reglas de fórmula (cómo calcula)

| # | Regla | Evidencia | Estado | Qué hace el agente |
|---|---|---|---|---|
| A1 | Costo = suma de las 9 etapas + 11 % de GG. No hay margen, impuestos ni redondeo. | AF, AG, AH en todas las filas; G17 = 0; ninguna fórmula usa `ROUND`. | Observada | Replicar igual. Redondear solo al mostrar. |
| A2 | El GG se aplica sobre **todo** el subtotal, incluida la M.O. y el refinamiento. | `AG = AF × G16/100`, y AF suma también AB:AE. | Observada | Replicar. Si algún día el GG va solo sobre materiales, es un parámetro nuevo. |
| A3 | Un solo dólar para todo y para siempre: la hoja entera usa G15, sin fecha ni fuente. | Todas las fórmulas apuntan a `$G$15`. | Observada | Cada cotización guarda su dólar. |
| A4 | "Actualizar el costo" = cambiar solo el dólar. Lo que está en pesos (corte, reb, prep, M.O., flex, goma, tela) queda congelado. | Meeting: "solamente actualizan por dólar", ejemplo de la Cartera Fucsia. | Observada | La recotización de la app tiene que pedir también precios en pesos actualizados. |
| A5 | Si el subtotal da 0, la fila muestra "consumo": es su aviso de que falta cargar el consumo. | `IF(AF>1, …, "consumo")`. | Observada | Validación: no se guarda una cotización sin consumos. |
| A6 | Precio de insumo en pesos por m² = precio del rollo ÷ superficie del rollo, calculado a mano y redondeado al peso. | 14000 / 1,40 = 10000; 8200 / 1,40 ≈ 5857; 6080 / 1,50 ≈ 4053 (W5:W7 tipeados). | Observada (el cálculo); Inferida (que siempre lo hace así) | Para paridad, usar el valor tipeado. La app puede calcularlo desde el rollo. |
| A7 | Para comparar costos en el tiempo guarda el costo anterior a mano y calcula el % de variación. | AJ y AK en la tabla de Necesaires; también filas 180, 244, 245, 301, 312. | Observada | Es lo que resuelve el historial de cotizaciones. |

#### B. Reglas de consumo (cuánto material)

| # | Regla | Evidencia | Estado | Qué hace el agente |
|---|---|---|---|---|
| B1 | Consumo de cuero = superficie de las piezas × 2 caras (o "tapas") + un desperdicio de 20 % a 28 %. | Mantel 0,80 × 0,45: "0,36 m² + 20 % desp. x dos tapas" en el nombre; 4 productos con medidas dan 20 %, 25 %, 25 % y 28 %. | Observada en esos casos; Inferida como regla general | No aplicar desperdicio encima: ya está adentro. |
| B2 | Muchas veces suma el desperdicio multiplicando por 1,2. | 11 de los 12 consumos con 3 decimales son un número de 2 decimales × 1,2 exacto (0,288 = 0,24 × 1,2; 0,216 = 0,18 × 1,2; 0,192 = 0,16 × 1,2; 0,168; 0,048; 0,264; 0,012). | Observada (el patrón); Inferida (que sea desperdicio de 20 %) | Útil para recuperar el consumo neto: neto ≈ bruto ÷ 1,2 en esos casos. Confirmar. |
| B3 | Los consumos se redondean a 2 decimales (0,05 o 0,1 m² en los valores más comunes). | 216 de 326 consumos con 2 decimales, 85 con 1. | Observada | Aceptar 4 decimales en la base; no forzar redondeo. |
| B4 | El forro se piensa como una proporción del cuero, no se mide aparte. | Forro ÷ cuero: mediana 0,69; 18 productos con forro = cuero y 12 con forro = mitad del cuero. | Inferida | Sugerencia para productos nuevos: forro ≈ 0,7 × cuero, confirmada por una persona. |
| B5 | "Sin forro" se carga como consumo 0, no como otro tipo. | 49 productos con forro 0, entre ellos los 6 que dicen "sin forro" en el nombre, billeteras, bandejas, llaveros y cinturones. | Observada | En la app, "sin forro" es no tener línea de forro. |
| B6 | Para medir un producto nuevo a veces usa las medidas de otro producto de referencia. | "Mantel Individual 48 × 33 … (0,35 × 0,50 - 30/07/19 se toma para costo)". | Observada en ese caso | Registrar "producto de referencia" en la cotización. |

#### C. Reglas de criterio (qué usa para cada producto)

| # | Regla | Evidencia | Estado | Qué hace el agente |
|---|---|---|---|---|
| C1 | **Un producto nuevo se cotiza copiando uno parecido y ajustando.** | Nombres: "como 1660 pero barra ancha", "2037 (514+chica)", "903 +ch", "1787 más grande", "parecido 103", "Varadero pero más grande", "ex art 6"; variantes "/n". | Inferida (fuerte) | Flujo de cotizar "a partir de un producto existente", guardando de cuál salió. |
| C2 | Cuero por defecto: Estándar. Los otros son excepción. | Estándar en 308 de 326; Carpincho en 7 (casi todas billeteras); exóticos en 5. | Observada | Estándar como valor por defecto. |
| C3 | Forro por defecto: tela. Potro solo en carteras y bandoleras. | Tela en 309; potro en 17, todos carteras o bandoleras. | Observada | Tela por defecto; potro sugerido solo en esas categorías. |
| C4 | Flex y goma eva van en productos con estructura (carteras, portafolios, carpetas, necesaires, bolsos), nunca en billeteras, monederos, tarjeteros ni llaveros. | Flex en 67 de 112 carteras y 12 de 14 necesaires; 0 en 17 billeteras, 13 monederos, 8 tarjeteros, 6 llaveros. Flex ≈ 0,47 del consumo de cuero (mediana). | Observada (el patrón); Inferida (que sea "estructura") | Sugerir flex y goma por categoría, no obligarlos. |
| C5 | Herrajes: monto global en USD "a criterio", en dólares enteros. USD 2 parece ser el piso (solo hilo y cemento). | Valores más comunes 2 (45), 5 (44), 4 (36), 3 (34); nota S11 "Hilo, cemento va en HERRAJES usd 2"; meeting: "viene un criterio". | Observada (valores); Inferida (USD 2 = solo hilo y cemento) | Default USD 2; mayor si el producto tiene herrajes. |
| C6 | **Actualiza herrajes subiendo 10 % sobre el valor viejo, a veces varias veces,** en vez de recotizar. | 29 valores son un número redondo × 1,1, × 1,21 (1,1²) o × 1,331 (1,1³): 5,324 = 4,4 × 1,21; 20,4974 = 15,4 × 1,331; 2,662 = 2,2 × 1,21. Están pegados como valores. | Observada (el patrón numérico); Inferida (que sea un ajuste del 10 %) | No replicar como regla. Preguntarle a Gerardo; en la app, un ajuste de precio es un precio nuevo con fecha. |
| C7 | Reb y prep son una tarifa fija de 1.500 por producto. | 325 de 326 (la excepción, Billetera Dólar, tiene todo en 0). | Observada | Default por categoría, editable. |
| C8 | Corte por complejidad o tamaño: 3.000 estándar; 4.000 en bolsos, portafolios grandes, portatrajes y todos los necesaires; 2.000 o 2.500 en piezas chicas o planas (money clip, correas, individuales) y carteras sin forro. | 287 en 3.000; los 16 de 4.000 son esos productos más una cartera ("Cartera de Bolas"); los de 2.000 tienen consumo mediano 0,18. | Observada (valores); Inferida (el criterio) | Default por categoría y tamaño. |
| C9 | **La M.O. tiende a subir por tamaño, pero no es una regla de escalones.** La mediana sigue al consumo de cuero (< 0,2 m² → 6.000; 0,2 a 0,4 → 8.000; 0,4 a 1,2 → 12.000; ≥ 1,2 → 20.000), aunque dentro de cada tramo hay de todo. | 36 valores distintos; solo 212 de 342 filas usan los 4 valores típicos; rangos por tramo muy abiertos (≥ 1,2 m² va de 8.000 a 50.000). La tabla "tentativos" es de 2024 y no se aplica. | Observada (la tendencia y la dispersión); Inferida (que el tamaño influya) | **Importar el valor de cada fila.** Para productos nuevos, a lo sumo mostrar la mediana del tramo como referencia; nunca autocompletar. |
| C10 | M.O. de la planilla = estimación del artesano (horas × valor hora), usada como referencia; el costo real lo pone el taller por producto o lote. | Meeting. | Observada (lo dijo él); el porqué no lo supo explicar | Dos valores separados (ver sección 5). |
| C11 | Valida al taller por proporción con un producto parecido: "si esta me costó 100 y la otra es más chica y con menos detalle, debería costar menos de 85". | Meeting, textual. | Observada | No replicar. Comparar contra el mismo modelo en lotes anteriores. |
| C12 | Negocia con el taller por debajo de lo que pide. | Comentario AE53 (2017): "Sanchez $1.000 pidió, pagamos $750". Otros 6 comentarios con montos pagados. | Observada (un caso) | Guardar precio pedido y precio pagado en la orden. |
| C13 | Compara productos de una misma familia ordenándolos por consumo de cuero. | Tabla de Necesaires ordenada de 0,42 a 0,25 m². | Observada | Vista de comparación por categoría ordenada por consumo. |
| C14 | El margen lo pone una persona al final, fuera del Excel. | Meeting: "al final viene una persona que le asigna un margen"; G17 = 0. | Observada | El precio de venta es otra entidad (`precio_venta`). |
| C15 | Mete notas de costeo dentro del nombre (medidas, fechas, "costo x 5 unidades", kits). | Nombres de las filas 202, 258, 298, 310. | Observada | El importador las separa en campos propios. |

**Cómo usar esta tabla:**
1. Las reglas A describen la fórmula del Excel viejo. Ya no se replican: la columna "Qué hace el agente" de la tabla A es la de la v5 (ver 3.5.4 para lo que rige hoy).
2. Las reglas B y C **no** se automatizan. Alimentan las sugerencias para productos nuevos (la tabla `plantilla_linea` no existe todavía, ver sección 5) y las alertas de calidad, por ejemplo "M.O. fuera del escalón de su tamaño" o "forro mayor que el cuero".
3. Cada regla inferida es una pregunta para Gerardo (la lista, `preguntas-gerardo-robert.md`, no está en el repo [V: no figura en `docs/`]). Cuando la confirme, se cambia "Inferida" por "Confirmada" con la fecha.

---

## 4. Trampas del Excel que un agente puede romper

> Historia del Excel viejo. Son trampas de **leer ese archivo**; las que hablan de "paridad" o de GG se mantienen como contexto del origen de los datos, no como reglas del motor vigente.

1. **Grano largo (H11) está tipeado en 34040**, no es `23 × dólar`. Para la paridad hay que usar 34040 tal cual. Para el futuro: marcarlo como precio en ARS fijo y preguntarle a Gerardo cuál es el bueno.
2. **Lagarto y yacaré cotizan en "USD por cm"** como texto y dan error. Su unidad no es compatible con el consumo en m². No convertir por tu cuenta: el material tiene `unidad_consumo` en m² y el precio tiene `unidad_precio` en cm, así que la regla del backend los bloquea; además van con `cotizable = false` hasta que Gerardo defina la regla.
3. **El `CHOOSE` del cuero tiene una 7ª opción que apunta al Potro del forro** (H13). Ninguna fila usa el tipo 7 hoy. No crear un "cuero 7".
4. **El GG devuelve el texto `"consumo"`** si el subtotal es ≤ 1. En la app eso es un error de validación ("faltan datos de consumo"), no un texto dentro de un campo numérico.
5. **El dólar no afecta todo por igual.** Cuero, potro y herrajes están en USD y suben con el dólar. Flex, goma, tela de forro, corte, reb, prep y M.O. están en ARS y no se mueven. "Actualizar el dólar" **no** actualiza el costo real de lo que está en pesos. El modelo tiene que guardar la moneda de cada insumo.
6. **Los precios por m² de los insumos se tipearon a mano** a partir del precio del rollo (14000 / 1,40 = 10000; 8200 / 1,40 ≈ 5857; 6080 / 1,50 ≈ 4053). Para la paridad usar el valor tipeado; el cálculo desde el rollo es una mejora futura.
7. **El desperdicio ya está "metido" en los consumos** (medido: entre 20 y 28 % más que la superficie útil), no se aplica el 30 % de I3. Si se aplicara encima, se contaría dos veces. **No aplicar desperdicio** hasta que Gerardo lo confirme.
8. **Filas rotas:** 11 filas con `#VALUE!` o `#REF!` (lagarto, yacaré, tipo vacío, `X42 = #REF!`); 13 filas con el costo USD tipeado en lugar de fórmula; la fila 242 está pegada entera como valores. El importador las importa **marcadas como "a revisar"** y no entran en la prueba de paridad.
9. **Floats de Excel:** el Excel calcula en punto flotante (ej. 4052,9999999999995 en vez de 4053). La comparación de paridad usa una tolerancia de **0,01 ARS** sobre el costo. El motor guarda precisión completa y redondea solo para mostrar (2 decimales).
10. **El "modelo" (columna G) no es un ID único:** 10 modelos aparecen dos veces (514, 739, 915, 1525, 1729, 2296, 2413, 2493, 2509, 2670), a veces con productos distintos. La fila 94 tiene modelo sin nombre. Todavía no sabemos si es el código del ERP de Alejandro. Usar `producto.id` como identidad. `codigo_modelo` es texto, **no es único** y no se le agregan sufijos: los repetidos se migran tal cual con marca `modelo_repetido` para que Gerardo decida.
11. **Los ids de material se pisan:** en la tabla MATERIAL los cueros van 1 a 6 y los forros vuelven a empezar en 1 y 2 (Estándar y Potro son ambos "1"). Las fórmulas lo resuelven bien, pero en la base cada material tiene un id único y la fila del Excel se mapea con (etapa, código).
12. **El nombre del producto mezcla datos:** medidas, fechas ("Mochila Bien de Bien 06-01-26"), cliente ("Carpeta UADE"), notas de costeo ("Señalador (costo x 5 unidades)"), kits y componentes. Al migrar, el nombre queda corto y lo demás va a campos propios. Hay typos para corregir ("Cratera", "Cartear", "Trejetero", "Tarjetro", "Capeta"). Los colores de fondo de algunos nombres no tienen leyenda: importarlos como nota.
13. **Hay productos de más de un cuero** ("Carpeta Lorena (dos cueros)", "Sobre bicolor", "Bolso 3 colores") aunque el Excel admite un solo cuero por fila. Por eso la cotización usa **líneas genéricas por etapa**, no columnas fijas: un producto puede tener dos líneas de cuero.
14. **Costeo por unidad:** algunos productos están costeados por varias unidades o como kit. En la app el costo es siempre por unidad de producto; un kit es un producto compuesto. Hasta que Gerardo lo confirme, esas filas entran marcadas.
15. **El dólar no es uno solo en todo el archivo.** La fila 242 (Cartera Hermes ch al corte) está pegada como valores con dólar 1400 (K242 = 24 × 1400, P242 = 19 × 1400) y el grano largo (H11) está fijo con dólar 1480 (23 × 1480). El importador marca esa fila y ese precio, y no los usa para inferir precios.
16. **Filas sin cuero que no dan error:** J38 (Alhajero) y J234 (Cartera Alma) están vacías, el cuero da 0 y el costo sale bajo sin ningún aviso. Entran en las 296 filas "sanas", así que hay que **marcarlas aparte**: la paridad las compara, pero el importador las alerta como "sin consumo de cuero".
17. **Filas de costeo parcial:** la 48 (Billetera Dólar) no tiene corte, reb, prep ni herrajes; la 111 (Cinturón Caggiano, "solo ponemos el cuero") no tiene forro ni herrajes. Son costos válidos pero incompletos: marcarlas "costeo parcial", no completarlas.
18. **El código de modelo se lee como texto.** En G351:G366 es texto ("514/1", "2538/3") y en el resto número. Los 10 códigos repetidos suelen ser el mismo modelo en otro cuero, y hay 6 pares idénticos. La clave natural es **modelo + variante**, leída siempre como texto (sin convertir "514/1" en número ni perder ceros).
19. **Filas fantasma 348 a 350:** tienen fórmulas, no tienen nombre y dan `#VALUE!`. Se descartan sin migrar.
20. **La columna AI no es confiable:** vacía en 75, 111, 112, 276, 278 y 343; tipeada en 13 filas (AI233 = 11 cuando la cuenta da 55,66). El importador **recalcula siempre** el costo con el motor y guarda el valor viejo de AI solo como dato de comparación.
21. **La fila 381 (Necesaire Albert bajito) es un duplicado exacto de la 51**, igual que las otras filas de la tabla de Necesaires. Se migra una sola vez.
22. **Costos sin rótulo en AJ/AK de las riñoneras** (filas 180, 244, 245, 301 y 312): son dos montos en pesos, no un porcentaje (ej. fila 180: 47.478 y 41.224). No se sabe qué son. **No descartarlos:** importarlos como nota y preguntarle a Gerardo.
23. **Comentarios de celda** (AE32, AE50, AE53, AE99, AE108, AE147, AE355 y R140): son pagos a talleristas de 2016-2017 con nombres. Se guardan como nota histórica, **nunca como precio vigente**.
24. **Columnas sin encabezado:** E tiene 115 fechas (22/09/2022 a 25/08/2026) y dos enteros sueltos (E204 = 1, E205 = 2) que no son fechas. B y D tienen nombres de talleristas en unas 60 filas, escritos de forma inconsistente ("Fabián", "fabián", "Fabian, Adrián", "lucio 5/1/23"). Normalizar con cuidado y sin inventar: si no está claro, se guarda el texto original.
25. **Datos metidos en el nombre:** fechas (F122, F221), medidas y notas de costeo (F202), consumos (F205 "0,19", F206 "0,26"), equivalencias de modelo (F237 "= simple", F291 y F292 "= #6 = #6/1"). 24 nombres tienen espacios al final y F94 está vacío (modelo 1915). El importador hace `strip()`, conserva el nombre original y separa esos datos en campos o notas.
26. **Tipos de cuero vacíos sin validación:** H vacío en 82, 86, 94, 98 y 256 (dan `#VALUE!`). En la app, el tipo de cuero y el de forro se eligen de una lista y son obligatorios cuando hay consumo.
27. **Unidades de los insumos:** W5 (flex) y W6 (goma) dividen por 1,40 m² y W7 (tela) por 1,50 m², porque los rollos tienen anchos distintos. G14 dice "U$S" pero en la práctica la tela es un precio en pesos. Cartón (T10, 12.250) no lo usa nadie.
28. **Precisión:** no hay ningún `ROUND` en el archivo, así que el Excel trabaja con todos los decimales de un float. El motor calcula con `Decimal` sin redondear en el medio y la paridad compara con tolerancia de 0,01 ARS en el costo y 0,0001 USD en el costo en dólares. Redondear solo al mostrar. Si esa tolerancia no alcanza en alguna fila, se investiga la fila, no se agranda la tolerancia.

---

## 5. Modelo de datos (DER v3, vigente)

**La fuente de verdad es el código:** `backend/src/backend/models.py` y las migraciones, explicados en `docs/der-v3.md`. Su origen es la pestaña `Diccionario` de `Plantilla Costos Casa Lopez v4.1 (trabajo).xlsx`, que el 2026-10-27 reemplazó al DER v1 y a las reglas del Excel viejo [V: `odd/tasks/app-casa-lopez-v3.md`, S1 y L1]. Si este archivo y el código no coinciden, **gana el código** y se corrige este. `docs/der-v3.md` está algo atrasado: no lista `precio_venta`, `proveedor` ni `documento_proveedor` (migraciones 0006 y 0007) y dice consumos `NUMERIC(10,4)` cuando son `(12,6)` [V: `models.py`]. `docs/der.md`, `der-borrador.sql`, `wo1-modelo-conceptual.md`, `wo2-decisiones.md` y `wo2-staging.md` hablan del DER v1 (11 tablas, `cotizacion_linea`, GG): son **históricos**, no se implementan.

### Migraciones (20, cabeza `0020_proveedor_producto`) [V: `backend/migrations/versions`]
| Revisión | Qué hace |
|---|---|
| `0001_esquema_costos`, `0002_semillas` | DER v1 y sus semillas. Históricas. |
| `0003_der_v3` | Borra las tablas del DER v1 y crea el DER v3. |
| `0004_semillas_v3` | Carga `seed_data/seed_v3.json` (ver sección 7). |
| `0005_gasto_reemplaza_a` | `gasto_periodo.reemplaza_a_id`: una corrección es una fila nueva que apunta a la que reemplaza. |
| `0006_precio_venta` | Tabla `precio_venta`. |
| `0007_proveedores_documentos` | Tablas `proveedor` y `documento_proveedor`. |
| `0008_reventa` | Tablas `producto_reventa` y `compra_reventa`: productos que se compran hechos y se revenden (en la app se llama "Mercadería", código `MER-`) (costo = último costo unitario de compra; ver `backend/src/backend/reventa.py`). |
| `0009_gasto_anulado` | `gasto_periodo.anulado` (boolean, por defecto false): borrar un costo fijo solo marca la fila como anulada; deja de contar en totales, listas, copiar mes y exportación, pero se conserva. |
| `0010_compra_sin_unidades` | `compra_reventa.unidades` pasa a admitir NULL: un cambio de costo o de precio de venta hecho en la grilla de Mercadería es una fila nueva **sin unidades** (actualización de precio, no compra). |
| `0011_precio_material_proveedor` | `precio_material.proveedor_id` (FK nullable a `proveedor`); el texto `proveedor` queda. Backfill solo cuando el texto es exactamente el código de un proveedor. |
| `0012_impuesto_activo` | `impuesto.activo`: desactivar un impuesto no lo borra. |
| `0013_impuestos_vacios` | Borra los tres impuestos sembrados (IVA, IIBB, GANANCIAS): la grilla de impuestos arranca vacía. |
| `0014_gastos_venta_pct` | Agrega la fila de `parametro` `GASTOS_VENTA_PCT` (gastos variables de venta, fracción del precio neto, en 0, sin confirmar). No cambia tablas. Su `downgrade` borra solo esa fila. |
| `0015_precio_venta_margen` | Agrega `precio_venta.margen` (`NUMERIC(6,3)`, fracción del precio, 0.30 = 30 %, NULL = precio tipeado a mano) y un check `margen IS NULL OR (margen >= 0 AND margen < 1)`. Su `downgrade` borra el check y la columna: se pierden los márgenes guardados. |
| `0016_formulario_consumo` | Tablas `formulario_consumo` (código `FCO-nnnn`, artículo, estado `BORRADOR` / `ENVIADO` / `COMPLETADO` / `VALIDADO`, comentario de revisión, quién y cuándo envió, completó y validó) y `formulario_consumo_linea` (sección `CONSUMO` / `HERRAJE`, orden, nombre, cantidad `NUMERIC(12,6)` nullable y >= 0, comentario): la planilla digital de consumos y herrajes de un artículo nuevo. No calcula nada. Su `downgrade` borra las dos tablas: se pierden los formularios y las cantidades cargadas. |
| `0017_formulario_modelo` | Agrega `formulario_consumo.modelo_id` (FK nullable a `modelo`, con índice): la planilla de consumos mide un **modelo**; el producto (modelo + cuero + color) se crea después de validarla. Su `downgrade` borra la columna: se pierde el vínculo hoja-modelo, no las hojas. |
| `0018_pedidos_proveedor` | Tablas `pedido_proveedor` (código `PED-nnnn`, proveedor, fecha de recepción, remito, documento opcional) y `pedido_linea` (material, cantidad de presentaciones, presentación, contenido por presentación, precio por presentación, moneda, `iva_incluido` y el `precio_material_id` que creó), solo se agregan filas. Agrega la unidad `m` (metro) a la lista cerrada: reemplaza los CHECK `ck_material_unidad_de_consumo` y `ck_precio_material_unidad_del_precio`. Su `downgrade` borra las dos tablas (se pierde el vínculo pedido-precio, los precios quedan) y **falla si algún material o precio usa la unidad `m`**. |
| `0019_modelo_insumo` | Tabla `modelo_insumo` (código `MIN-nnnn`, `modelo_id`, `material_id`, `cantidad_por_unidad` `NUMERIC(12,6)` > 0, único por modelo + material): los insumos que lleva un modelo por unidad, en la unidad de consumo del material. Se llena al validar la hoja de consumos. Su `downgrade` borra la tabla: se pierden los insumos guardados y los modelos vuelven a costearse con `herrajes_usd_por_unidad` e `hilo_y_cemento`. |
| `0020_proveedor_producto` | Tabla `proveedor_producto` (código `PPR-nnnn`, `proveedor_id`, `material_id` nullable, `nombre`, `unidad` de la lista cerrada, `cantidad` `NUMERIC(12,6)` > 0 nullable, `precio_referencial` `NUMERIC(14,4)` > 0, `moneda`, `iva_incluido`, `vigente_desde`, `nota`, `creado_por`): lo que vende cada proveedor, con su unidad, la cantidad de una presentación y un precio de referencia. Solo se agregan filas: un cambio de precio, unidad o cantidad es una fila nueva del mismo producto (mismo nombre sin importar mayúsculas ni espacios) y la más nueva es la vigente. El motor no la lee. Su `downgrade` borra la tabla: se pierden las listas de productos de todos los proveedores con su historia. |

Todas tienen `downgrade`, pero bajar de 0020 (borra las listas de productos de los proveedores y su historia de precios), 0019 (borra los insumos por modelo y cambia el costo de esos modelos), 0018 (borra los pedidos de proveedor y falla si algún material o precio usa la unidad `m`), 0017 (pierde el vínculo hoja-modelo), 0016 (borra los dos formularios de consumos y todo lo que cargó el taller), 0015 (borra los márgenes guardados en `precio_venta.margen`), 0014 (borra el valor cargado de `GASTOS_VENTA_PCT`), 0013 (vuelve a crear los impuestos sembrados), 0012 (los impuestos desactivados vuelven a estar activos), 0011 (pierde el vínculo al proveedor), 0010 (falla si hay filas sin unidades), 0009, 0007, 0006 o 0005 borra datos o cambia totales (0009: las filas anuladas vuelven a contar) (ver `docs/produccion.md`, sección 5).

### Tablas (36 en el schema `costos`) [V: `models.py`, `docs/der-v3.md`]
| Grupo | Tablas | Lo que no hay que romper |
|---|---|---|
| Catálogo | `modelo`, `producto`, `receta_linea`, `kit_componente`, `molde`, `modelo_molde`, `modelo_insumo` | `modelo` es qué se fabrica y trae los consumos por unidad (cuero, forro, flex, goma EVA, herrajes en USD, hilo y cemento) y la confección estimada. `producto` es un modelo en un cuero y un color (`modelo_id` puede ser NULL en un kit). `receta_linea` guarda **solo** las líneas `EXTRA` (un segundo cuero, un herraje puntual); las del modelo se calculan. En `modelo`, NULL = dato faltante y 0 = "no lleva". `nombre_del_modelo` es único. |
| Referencias | `etapa` (8 fijas), `categoria`, `color`, `persona`, `taller`, `impuesto`, `parametro`, `material` | `material.cotizable = false` bloquea lagarto y yacaré. Las unidades son una lista cerrada (`m2`, `cm`, `juego`, `unidad`, `USD`, `m`). Los parámetros llevan `fuente_estado`; ninguno está confirmado. |
| Con historia (solo se agregan filas) | `precio_material`, `tipo_cambio`, `precio_venta`, `gasto_periodo` | Un precio es único por material + color + `vigente_desde` (color NULL = todos los colores); el del color gana al genérico y nunca se usa uno de fecha futura. Cada precio guarda `moneda`, `unidad_del_precio` e `iva_incluido`. El dólar es único por fecha + tipo + fuente (fuentes `BNA`, `EXCEL_VIEJO`, `MANUAL`). El precio de venta vigente es el más nuevo. Un gasto se corrige con una fila nueva (`reemplaza_a_id`). |
| Cotización | `cotizacion` | Foto calculada e inmutable (regla de oro 4). La escribe el motor, nadie la edita. |
| Fabricación | `orden_fabricacion` (el "lote"), `orden_item`, `orden_estado`, `registro_tarea` | `orden_item` separa el precio pedido del pagado por unidad. `orden_estado` es el historial de estados (`PLANIFICADA` a `CERRADA`). El precio del taller se edita en el lugar, sin historial [V: `odd/tasks/app-casa-lopez-v3.md`, L14]. |
| Inventario de cuero | `pieza_cuero`, `movimiento_cuero`, `conteo_inventario` | Un movimiento `CORTE` tiene que apuntar a su `orden_item`. |
| Mercadería (tablas `*_reventa`) | `producto_reventa`, `compra_reventa` | Productos comprados hechos y revendidos, fuera del motor de costeo. El costo es el costo unitario de la compra más nueva; cada compra nueva es una fila (solo se agregan). Solo ARS y sin stock (SUPUESTO: validar). Solo `admin`. |
| Proveedores | `proveedor`, `documento_proveedor` | Las facturas e imágenes se guardan en la base (`bytea`, sin object storage). El OCR solo sugiere: **no crea precios**. `precio_material.proveedor` es texto y **no** está vinculado a `proveedor` [V: docstring de la migración 0007]. |
| Formularios de consumos | `formulario_consumo`, `formulario_consumo_linea` | Una planilla por artículo nuevo; el taller carga cantidades en m² o unidades y el admin la valida. Una planilla `VALIDADO` es inmutable (se duplica para cambiarla) y no se borra nada. **No hay costeo ni cálculo** y no toca `receta_linea`; al validar copia las medidas al `modelo` y guarda los insumos en `modelo_insumo` (los que no coinciden con un material vuelven en `sin_material`). Las filas precargadas (14 consumos y 16 herrajes) viven en una constante de `backend/src/backend/formulario.py`, no en la base. SUPUESTO: el rol `taller` no está atado a un taller concreto: cualquier usuario `taller` ve las planillas `ENVIADO` y `COMPLETADO`. |
| Pedidos de proveedor | `pedido_proveedor`, `pedido_linea` | Lo que llegó de un proveedor y cómo (presentación). Solo se agregan filas. Guardar un pedido crea un `precio_material` por línea con `servicios.crear_precio` (precio unitario = precio por presentación ÷ contenido, en la unidad de consumo, `vigente_desde` = fecha de recepción) y todo es atómico: si una línea falla no se guarda nada. Escribe y lee solo `admin` (el `gerente` ya no ve Proveedores). |
| Productos de proveedor | `proveedor_producto` | Lo que vende cada proveedor: nombre, unidad (lista cerrada), cantidad de una presentación y precio de referencia (`precio_referencial`, de esa presentación; el backend calcula `precio_por_unidad`). Solo se agregan filas (regla de oro 10): cambiar el precio es una fila nueva con fecha, la más nueva del producto es la vigente. **Es una referencia, no un costo:** no crea `precio_material` ni toca el motor. `material_id` es NULL mientras el producto no esté en materiales. Lee y escribe solo `admin` (el `gerente` no ve Proveedores). SUPUESTO: validar que el precio es el de la presentación y que la unidad no tiene que coincidir con la del material. |

Reglas transversales:
- `codigo` es la clave de negocio: único y nunca cambia (`MOD-`, `PRD-`, `PRE-`, `GF-`, `PRV-` más número; `REX-`, `LOT-` y `LIT-` son prefijos nuestros, SUPUESTO: validar). Las claves foráneas apuntan a `id`.
- `modelo.modelo_excel_viejo` y `fila_excel_viejo` conservan el código y la fila del Excel viejo; el código de modelo del Excel **no es único** (trampa 10).
- **M.O. en dos lugares:** la estimación del modelo (`confeccion_estimada_ars`) y el precio real del taller (`orden_item`). Se compara contra el mismo modelo en lotes anteriores, no contra "productos parecidos".
- No existe la tabla `marca_calidad` del DER v1: las alertas se calculan en la pantalla Alertas y las marcas `REVISAR` del importador viven en la `nota` del producto [V: `servicios.motivos_de_revision`, `docs/importar-productos.md`].
- Todavía no existen `venta` ni `plantilla_linea`. Copiar y ajustar un producto parecido (regla C1) es un flujo posible, no una tabla.
- Procedencia: los precios llevan `nota_fuente`, el dólar `fuente`; `cotizacion.creado_por`, `precio_venta.creado_por` y `documento_proveedor.subido_por` guardan el id de usuario como texto, sin FK.

### Convenciones técnicas [V: `models.py`, `migrations/env.py`, `README.md`]
- Plata `NUMERIC(14,4)`, consumos **`NUMERIC(12,6)`** (el DER v1 decía `(10,4)`; se ensanchó para no redondear 12 valores de la plantilla), dólar `NUMERIC(12,4)`, porcentajes `NUMERIC(6,3)` guardados como fracción (0.05 = 5 %; SUPUESTO: validar la lectura de `desperdicio_manual`). En SQLAlchemy, `Numeric(p, s, asdecimal=True)`; ids `BigInteger` + `Identity(always=True)`; `created_at timestamptz` en todas las tablas (ya no hay `updated_at`).
- **Todas las tablas van en el schema `costos`**, incluida `alembic_version` (`version_table_schema="costos"`). Alembic solo mira ese schema (`include_name`).
- **Better Auth** (`user`, `session`, `account`, `verification`) queda en `public` con su propia CLI (`pnpm auth:migrate` en `front/`): nunca generar migraciones que lo toquen.
- Migraciones con Alembic. `der-borrador.sql` es histórico. Nunca cambiar la base a mano.
- Las cosas con historia (precios, dólar, precios de venta, gastos, cotizaciones) no tienen `UPDATE`: se agrega una fila con fecha. Única excepción: `gasto_periodo.anulado`, la marca de borrado lógico de un costo fijo (la fila se conserva).
- Plataforma: Railway (ver 9.2).

---

## 5.1 Pantallas y roles

Menú del admin (escritorio) [V: `front/lib/nav.ts`, revisión 2026-11-12]: **Administración** (arriba de todo; su primera pestaña es el **Panel**, en `/admin/panel`: costo-volumen, dólar del día automático y alertas) · **Producción** (Productos, Modelos, Catálogos, Lotes, Formularios de consumos, Inventario de cuero) · **Abastecimiento** (Proveedores, Talleres) · Costos fijos (Mano de obra, Servicios básicos) · Costos variables · Producción · Voz (botón de micrófono en el header de desktop). Ya no existen Grilla completa ni el menú de Modelos. Versión anterior: **Panel del negocio** (costo-volumen) · **1 · Datos de base** (Dólar, Materiales y precios, Cueros, Proveedores, Modelos) · **2 · Productos y costos** (Productos: lista y ficha con cotizaciones y precio de venta) · **3 · Producción** (Lotes, Talleres) · **4 · Fin de mes** (Costos fijos) · **Consultas** (Grilla completa) · **Control** (Alertas) · **Herramientas** (Voz, Administración: usuarios, parámetros, modelos, catálogos, personas e impuestos). Además hay una pantalla **Corte** para el rol taller. Principio de UI: resumen primero (una línea por producto), detalle a demanda; no replicar el ir y venir del Excel.

Roles de la app (`user.role` de Better Auth) [V: `backend/src/backend/auth.py`, `front/lib/permissions.ts`, `odd/tasks/roles-admin-gerente-taller.md`]. Los endpoints niegan por defecto:

| Rol | Qué puede |
|---|---|
| `admin` | Todo: lecturas, escrituras y la administración de usuarios. Es el único que escribe. |
| `gerente` | Solo lectura, y solo de **Productos** (lista y ficha, con su rentabilidad y precios de venta), **Modelos** y el **simulador de Escenarios** (`/escenarios`; su `POST /cvu/escenario` calcula sin guardar nada, por eso lo abre `LECTURA_PRODUCTOS`). Es el rol por defecto de un usuario nuevo. **No** accede a Panel (`/admin/panel`), Lotes, Formularios de consumos, Inventario de cuero, Proveedores ni Talleres (pedido del usuario, 2026-11-13; la API responde 403 y el menú no los lista). Detalle en `docs/roles.md`. |
| `taller` | Corte, Cueros, Voz y la **lista** de productos con sus costos (no la ficha). Por voz confirma solo `registrar_precio_taller`. No ve lo pagado por m² de cuero. Completa los **Formularios** de consumos que le envían (`docs/formularios.md`). |

Los nombres viejos se leen mapeados: `cotizador` → `admin`, `corte` → `taller`, `consulta` → `gerente`. Un usuario sin rol reconocido cae en `/sin-acceso`. SUPUESTO: qué persona real (Gerardo, Alejandro, quien reemplace a Gerardo) tiene qué rol no figura en el repo; el rol `taller` y su alcance están marcados "validar" en la spec de roles.

Etapas, en este orden: CUERO, FORRO, FLEX, GOMA_EVA, HERRAJES, HILO_CEMENTO, CORTE, CONFECCION [V: `etapa` en `seed_v3.json`]. Las categorías son una lista abierta (16 sembradas) y el tamaño es CHICO, MEDIANO o GRANDE.

---

## 6. Supuestos abiertos (NO resolverlos por tu cuenta)

Todos van como **parámetros configurables** con el valor que hoy usa el Excel, y un comentario `# SUPUESTO: validar con Gerardo`.

| # | Tema | Valor del Excel viejo | Pregunta pendiente |
|---|---|---|---|
| 1 | GG | 11 % sobre el subtotal | ¿Qué es? ¿Gastos generales? (no parece IVA) |
| 2 | Ganancia 27 % | 0, no se usa | ¿Se usa para el precio de venta? ¿Dónde? |
| 3 | Desperdicio | no se aplica | ¿Ya está dentro del consumo? |
| 4 | Consumos | los del Excel | ¿Son medidos o "a ojo"? Propuesta: estándar por producto; productos nuevos con la mediana de su categoría y tamaño, siempre confirmada por una persona. |
| 5 | Lagarto / yacaré | bloqueados | ¿Unidad real del precio (cm, cm², m²)? ¿De dónde sale? |
| 6 | Herrajes | USD tipeado por fila | ¿Qué incluye? ("Herraj. hilo cemento", USD 2) |
| 7 | Corte, reb, prep | tipeados por fila | ¿Qué son exactamente? ¿Quién da el dato? |
| 8 | Mano de obra | tipeada por fila | ¿Artesano (horas × tarifa) o taller (por producto/lote)? Hoy se compara con productos "comparables", que es un criterio subjetivo. |
| 9 | Código de modelo | campo de texto | ¿Es el código del ERP de Alejandro? |
| 10 | Recotización | — | ¿Cuándo se recotiza? ¿Al cambiar el dólar, un precio, cada X tiempo? |
| 11 | Impuestos | no modelados | IVA, IIBB y ganancias: van como constantes separadas del costo cuando se definan. |
| 12 | Dólar | manual | ¿Qué cotización (BNA oficial, blue, MEP)? |
| 13 | IVA en precios de compra | se toman como vienen en el Excel | ¿USD 24/m², $14.000 la plancha, etc. son con o sin IVA? Puede cambiar todos los costos. Si se discrimina, se agrega `incluye_iva` en `precio_material`. |
| 14 | Presentación de compra | plancha | ¿Flex y tela se compran en plancha o en rollo? Cambia `presentacion` y `contenido_presentacion`. |

La lista completa de preguntas, ordenada por sección y prioridad, estaba en `preguntas-gerardo-robert.md`, que no está en el repo [V: no figura en `docs/`]; pedírsela a Agustin.

**Cómo quedó cada uno en el modelo v3** (revisión 2026-11-10). Las preguntas siguen abiertas con Gerardo; lo de abajo es lo que el código hace hoy mientras tanto:
- **1 GG:** eliminado del costo por decisión del modelo v3; el 11 % queda solo como `GG_PCT_EXCEL`, referencia. La pregunta ya no bloquea nada [V: `odd/tasks/app-casa-lopez-v3.md` S1; `seed_v3.json`].
- **2 Ganancia 27 %:** no existe un parámetro de ganancia. El precio de venta es una tabla propia (`precio_venta`, lo fija una persona) y la rentabilidad sale de costo-volumen (margen de contribución y punto de equilibrio) [V: `models.py`, `costeo.py`]. De dónde salía el 27 % sigue sin respuesta.
- **3 Desperdicio:** `FACTOR_DESPERDICIO_DEFAULT` = 0 y `material.desperdicio_manual` por material. Sigue abierto si el consumo ya lo trae.
- **4 Consumos:** los de `modelo`, con `origen_de_los_consumos` (`EXCEL`, `MOLDE`, `ESTIMADO`, `MEDIDO`) y la marca `validado` (ninguno validado en el seed).
- **5 Lagarto / yacaré:** `cotizable = false`, sin precio sembrado.
- **6, 7 y 8:** HILO_CEMENTO se separó de HERRAJES; CORTE vale 0 (sueldo en costos fijos); CONFECCION une REB, PREP y M.O. (ver 3.5.4). Los códigos REB y PREP ya no existen como etapas. Qué eran exactamente sigue abierto.
- **9 Código de modelo:** `modelo.codigo` (`MOD-nnnn`) y `producto.codigo` (`PRD-nnnn`) son claves internas; el código del Excel es `modelo_excel_viejo`. Sigue sin saberse si es el del ERP de Alejandro.
- **10 Recotización:** la app marca RECOTIZAR si el costo se desvía más de `TOLERANCIA_DESVIO_PCT` (0,05) o el dólar se movió más de `VARIACION_DOLAR_RECOTIZAR_PCT` (0,10). Ambos están sembrados como "Propuesta, a confirmar con Robert" (SUPUESTO).
- **Escenario CVU (multiproducto):** el aporte por unidad del escenario es precio neto - costo variable - gastos de venta (`GASTOS_VENTA_PCT` × precio neto, en 0) - IIBB (alícuota del impuesto activo con código `IIBB` y base VENTA × precio neto; sin alícuota cuenta 0 y avisa `IIBB_SIN_ALICUOTA`). También muestra el aporte por hora de taller cuando el modelo tiene `horas_de_confeccion` (SUPUESTO: validar con el contador y Robert). Sigue sin existir `venta`: el volumen es el que se escribe en el escenario.
- **11 Impuestos:** existe la tabla `impuesto` (IVA 21 %, no es costo: supuesto del DER, a validar con el contador; IIBB y Ganancias sin alícuota) y `ARREGLOS_PCT` = 0.
- **12 Dólar:** `tipo_cambio.tipo` (`VENDEDOR` o `COMPRADOR`); el botón y `backend.actualizar_dolar` cargan el vendedor del BNA (SUPUESTO: validar con Gerardo, ver `docs/dolar-bna.md`). El cron todavía no está configurado.
- **13 IVA en precios de compra:** existe `precio_material.iva_incluido` (por defecto `false`); sigue sin saberse si los precios del Excel lo incluyen.
- **14 Presentación de compra:** el modelo v3 no guarda plancha ni rollo; solo precio por unidad de consumo.

Regla: si una tarea del kanban necesita una de estas respuestas, se implementa con el parámetro y se deja anotado en el work order que falta validar. **No se "elige" un valor nuevo.**

---

## 7. Datos iniciales e importadores

El importador del Excel al DER v1 (cotización por producto, `dato_origen`, fixture de paridad) **no existe en el repo** [V: no hay script ni `tests/fixtures/excel_paridad.json`]. Lo que hay hoy:

1. **Semillas v3** (`backend/scripts/generate_seed_v3.py`). Lee `Plantilla Costos Casa Lopez v4.1 (trabajo).xlsx` y escribe `backend/migrations/seed_data/seed_v3.json`, que se commitea. La migración `0004_semillas_v3` carga ese JSON y **nunca lee el xlsx**. Se corre aislado y sin confiar en el archivo: `uv run --with openpyxl python -I backend/scripts/generate_seed_v3.py "<plantilla.xlsx>" backend/migrations/seed_data/seed_v3.json`. Contenido: 8 etapas, 16 categorías, 7 personas, 3 talleres (de ejemplo), 3 impuestos, 8 parámetros, 13 materiales, 11 precios (fechas 2026-09-01 y 2026-09-03), 1 dólar (1545, `EXCEL_VIEJO`, 2026-09-01), 325 modelos y 15 gastos fijos [V: `seed_v3.json`]. Montos y cantidades van como string y se cargan como `Decimal`.
2. **Productos desde el Excel** (`backend/scripts/importar_productos.py`, guía completa en `docs/importar-productos.md`). Pasa la lista de la hoja `Marroquineria1` (filas 22 a 347) a `producto`: solo productos, **no** precios, costos ni cotizaciones. Enlaza cada fila con su `modelo` por `fila_excel_viejo`, deja nombre, cuero y color, y marca con `REVISAR` (en la `nota`) lo dudoso: error en origen, sin nombre, lagarto o yacaré, sin tipo de cuero, modelo repetido, posible kit. Pasa por `servicios.crear_producto` y se puede correr dos veces sin duplicar. Las columnas sin encabezado (B, D, E) y los comentarios de celda de AE van a la `nota` como texto, **nunca como precio vigente**.
   - **Guardas:** por defecto es un *dry-run*. Para escribir hacen falta `--entorno staging|production` **y** `--confirmar`, y `DATABASE_URL`. Si existe `RAILWAY_ENVIRONMENT_NAME` tiene que ser igual a `--entorno`; sin esa variable (corrida local) solo se acepta `staging`. Nunca imprime la URL ni las credenciales [V: `importar_productos.py`, `docs/importar-productos.md`].
   - En production solo se escribe desde dentro del contenedor de production (`railway ssh`), con backup verificado y autorización (ver 9.2).
3. **Datos de ejemplo** (`backend/scripts/cargar_ejemplo.py`). Filas sintéticas con la palabra `EJEMPLO` en la nota, **solo staging** (rechaza cualquier otro entorno) [V: `cargar_ejemplo.py`, función `main`].

Las reglas de importación de la v5 (marcas `dolar_congelado`, `costo_tipeado`, cotización en `borrador`, deduplicar Necesaires, etc.) eran para el DER v1 y no están implementadas. Las trampas de la sección 4 siguen sirviendo para entender por qué una fila sale marcada.

---

## 8. Pruebas de aceptación (la paridad se descartó)

- **Decisión:** el modelo v3 se hace **sin prueba de paridad con el Excel**; el usuario la descartó el 2026-10-28 y pidió que solo funcione la lógica [V: `odd/tasks/app-casa-lopez-v3.md`, T2 y L6]. No hay fixture del Excel ni test de paridad en el repo.
- **Lo que hay en cambio:** un test por regla del motor y de la receta (`backend/tests/test_costeo.py`, `test_receta.py`, `test_servicios.py`, `test_roles.py`, etc.). Se corren con `uv run --directory backend pytest -q` y, para el frontend, `cd front && corepack pnpm lint && corepack pnpm build`.
- **Tests de integración:** necesitan una Postgres descartable local en `TEST_DATABASE_URL`; sin esa variable se saltean [V: `backend/tests/conftest.py`]. El CI de GitHub Actions hoy corre el backend sin Postgres [V: `.github/workflows/ci.yml`]; agregarlo es la spec S4 de `odd/tasks/produccion-listo.md`.
- Los números del Excel (fila 22: 43.024,27 ARS = 27,85 USD, etc., sección 3) quedan como ejemplos históricos. Si algún día se quiere volver a comparar contra el Excel, es una decisión de Robert y Agustin, no del agente.
- Nunca se ajusta un test para que pase: si falla, se busca la causa.

---

## 9. Estado del proyecto y producción

### 9.1 Dónde estamos (según `odd/tasks/*.md` y `git log`)
El plan original (DER, importador, motor con paridad, API, pantallas) quedó superado por el modelo v3. Hoy [V: `odd/tasks/app-casa-lopez-v3.md`, `git log --oneline`]:
- **Hecho en código:** DER v3 y migraciones 0003 a 0007; motor y recetas v3; API con login fail-closed y roles; frontend (Better Auth, módulos de la sección 5.1, panel admin); costo-volumen y precio de venta; fabricación, talleres y costos fijos con correcciones; inventario de cuero; proveedores con facturas y OCR; carga por voz; copia a Google Sheet; dólar del BNA (botón y comando); importador de productos con guardas.
- **Pendiente o sin probar con servicios reales:** conectar el Google Sheet real y probar voz y OCR con modelo real (a 2026-10-28 y según `docs/voz.md` y `docs/sheets-sync.md`; SUPUESTO: puede haber cambiado); cron del dólar; activar backups en Railway; las respuestas de Gerardo (sección 6).
- **En curso:** cierre de la auditoría de producción en `odd/tasks/produccion-listo.md` (healthcheck real, cerrar `/db/estado` y `/api/demo/*`, cabeceras de seguridad, CI con Postgres, filtros de productos). Mirar ese archivo para el estado actual.
- **Más adelante (no ahora):** integración con el ERP, sugerir cuándo producir según demanda y costo, detalle de herrajes.

### 9.2 Producción y despliegue
Detalle y comandos: `docs/produccion.md` (promoción, rollback y backups), `docs/wo2-staging.md` (aplicar migraciones a mano) y el `README.md`. Sin valores secretos en este archivo: las URLs y claves se piden a Railway o a Agustin.

- **Ambientes [V: `docs/produccion.md`, `README.md`, `odd/tasks/railway-staging-deploy.md`]:** proyecto Railway `casa-lopez` con `staging` y `production`; servicios `backend` (raíz `/backend`), `frontend` (raíz `/front`) y un servicio Postgres.
- **Staging** despliega solo al llegar un commit a `main`, y solo si el CI de GitHub Actions pasa (Railway "Wait for CI" en los triggers de staging). El CI no bloquea el commit: un commit roto puede entrar a `main`, pero no se despliega [V: `odd/tasks/ci-gated-staging-deploy.md`, `README.md`].
- **Production es manual** y no se activa el auto-deploy. Se despliega un SHA que ya pasó por staging con `railway redeploy -e production -s <servicio> --commit <SHA> -y` [V: comando tal como figura en `odd/tasks/produccion-listo.md`; `docs/produccion.md` usa además `--from-source`].
- **Migraciones en el deploy:** el pre-deploy corre `uv run alembic upgrade head`; está en `backend/railway.toml` y, según el equipo, también configurado en el servicio del dashboard (SUPUESTO: no se puede verificar desde el repo; `docs/produccion.md` sección 0 explica por qué conviene: Railway deja de leer `railway.toml` el 2026-12-01). Si la migración falla, el deploy no sigue. El healthcheck es `/api/health` (120 s) [V: `backend/railway.toml`, `backend/tests/test_railway_config.py`].
- **Desde dónde se corre Railway:** los comandos `railway ...` se corren desde el **checkout principal**, el único vinculado al proyecto; los worktrees nuevos no lo están [V: lo dice `odd/tasks/produccion-listo.md`; no se probó en un worktree].
- **Operar dentro del contenedor:** `railway ssh -e <ambiente> -s backend`, y lo primero es `test "$RAILWAY_ENVIRONMENT_NAME" = production || exit 1` (o `staging`) [V: `docs/produccion.md`].
- **Nada en production sin backup previo y sin autorización explícita de Agustin:** ni migrar a mano, ni importar, ni `alembic downgrade` [V: `docs/produccion.md` secciones 3 y 7]. Los backups de Postgres se activan en el dashboard (servicio Postgres, pestaña Backups; el CLI no tiene comandos para eso); propuesta: Diario + Semanal y uno manual antes de cada promoción. **Estado: sin confirmar que estén activados.**
- **Guardas de los scripts:** `importar_productos.py` (`--entorno` + `--confirmar`, ver sección 7), `cargar_ejemplo.py` y `verificar_db` solo corren en staging o local [V: los tres scripts]. Los scripts de staging nunca se apuntan a production.
- **Roles en la app:** `admin`, `gerente` y `taller` (sección 5.1). El `taller` ve la lista de productos con costos, no la ficha.
- **Estado de production:** SUPUESTO. El equipo dice que production corre el modelo v3; `docs/produccion.md` (2026-11-10) daba la base en `0004_semillas_v3`, informado por Agustin y sin verificar, y el `README.md` decía que todavía no había un deploy exitoso. Antes de apoyarse en esto: `railway deployment list -e production -s backend` y `alembic current` dentro del contenedor.
- **Pendientes de la auditoría:** healthcheck real que mire la base, `/db/estado` y `/api/demo/*` públicos, cabeceras de seguridad, CI con Postgres, rotar la credencial de admin de staging, observabilidad, cron del dólar y pasar `railway.toml` a Infrastructure as Code (`docs/produccion.md` sección 8; el estado vivo está en `odd/tasks/produccion-listo.md`).

---

## 10. Cómo trabajar con Agustin

- Responder en **español rioplatense**, simple y paso a paso, con ejemplos del Excel ("como en la fila 22..."). Sin jerga sin explicar.
- **Marcar siempre qué es supuesto** y qué está verificado. Si algo se infirió, decirlo.
- Decir con honestidad cuánto lleva algo. Si una tarea no entra en el sprint, decirlo antes de empezar.
- Antes de un cambio grande al DER o al motor, explicar el porqué en dos o tres líneas y esperar el ok.
- Cuando convierta archivos (PDF, Word, Excel, PowerPoint) para leerlos, usar `markitdown` primero.
- Los commits y PRs referencian el work order de La Fábrica. Si un work order contradice este archivo, se pregunta antes de seguir.

---

## 11. Checklist antes de cada PR

- [ ] ¿Toqué el motor o la receta? Corrí `uv run --directory backend pytest -q` y pasa (y agregué el test de la regla nueva).
- [ ] ¿Algún monto pasó por `float`? (No debería.)
- [ ] ¿Agregué una regla de negocio nueva? Está como parámetro y marcada `SUPUESTO`.
- [ ] ¿Modifiqué una cotización guardada? (No se puede: se agrega otra.)
- [ ] ¿Cambié el DER? Hay migración de Alembic (con `downgrade`) y se actualizó `docs/der-v3.md`. ¿La migración va a production? Revisar `docs/produccion.md` antes.
- [ ] ¿El PR explica en simple qué cambia para el usuario?

---

## Anexo: memorias iniciales para Engram

Listas para cargar como memorias persistentes (una por línea o bloque).

### Decisiones
- `decision`: Stack Next.js 16 + Better Auth, FastAPI + SQLAlchemy + Alembic, Postgres, en Railway. LLM solo para interpretar voz y leer facturas, nunca para calcular costos.
- `decision` (histórico, reemplazada): El motor replicaba el Excel con GG de 11 %. Vigente: sin GG; ocho etapas; total = subtotal + kit + IVA (si es costo) + arreglos; USD = total / dólar de la fecha (ver 3.5.4).
- `decision`: Sin prueba de paridad con el Excel (2026-10-28): el motor se prueba regla por regla. Mejoras como parámetros.
- `decision`: Dinero con Decimal y NUMERIC. Nunca float. El frontend no calcula plata.
- `decision`: Cotizaciones inmutables: una por producto + fecha + tipo (INICIAL, RECOTIZACION, FINAL); guardan dólar, un monto por etapa y totales. No hay marca "vigente".
- `decision`: Necesaires no son una tabla aparte: es una categoría de producto.
- `decision`: Consumo del Excel = consumo estándar por producto; productos nuevos se sugieren con la mediana de su categoría y tamaño, confirmada por una persona.
- `decision`: Activo/archivado de un producto lo decide una persona.
- `decision`: Ignorar la zona AJ373 del Excel.
- `decision` (histórico): Orden del sprint inicial: DER, importador, motor, API, pantallas.
- `decision`: El DER v3 (plantilla v4.1, desde 2026-10-27) es la fuente de verdad: `models.py` + `docs/der-v3.md`; 28 tablas en `costos`, migraciones 0001 a 0007. El DER v1 (`docs/der.md`) es histórico.
- `decision`: `codigo` (MOD-, PRD-, etc.) es la clave de negocio única e inmutable; el código de modelo del Excel es `modelo.modelo_excel_viejo` y no es único.
- `decision`: precio, moneda, unidad e `iva_incluido` viven en `precio_material`; `material` solo dice etapa, unidad de consumo y si es cotizable.
- `decision`: En `modelo`, un consumo NULL es dato faltante y un 0 significa "no lleva".
- `decision`: El dólar y los precios iniciales del seed tienen fecha 2026-09-01 (Rouez y Acropol, 2026-09-03).
- `decision`: Tablas en el schema "costos"; Better Auth en "public". Railway: staging se despliega solo desde main con CI; production es manual con backup y autorización.
- `decision` (histórico): REB y PREP no se renombraban hasta que Gerardo dijera qué son. En v3 ya no son etapas: se unieron en CONFECCION.
- `decision`: Roles `admin`, `gerente` y `taller` (2026-11-05); el `taller` ve la lista de productos con costos pero no la ficha.
- `decision`: Los comandos de Railway se corren desde el checkout principal; production se despliega con `railway redeploy -e production -s <servicio> --commit <SHA> -y`.

### Supuestos abiertos (validar con Gerardo antes de cambiarlos)
- `supuesto` (histórico): GG 11 % probablemente era Gastos Generales, no IVA. Se eliminó del costo en el modelo v3; queda como referencia `GG_PCT_EXCEL`.
- `supuesto`: La ganancia 27 % valía 0 y no se usaba; el Excel terminaba en costo. En v3 el precio de venta es la tabla `precio_venta`.
- `supuesto`: El desperdicio del 30 % no se aplica; ya está dentro de los consumos (20-28 %).
- `supuesto`: Lagarto y yacaré tienen precio en USD por cm; bloqueados hasta definir la unidad.
- `supuesto`: M.O. real la cobra el taller por producto/lote; el artesano cotiza en horas. Hoy se usa "productos comparables" (subjetivo).
- `supuesto`: No sabemos si el "modelo" del Excel es el código del ERP.
- `supuesto`: No sabemos qué son exactamente corte, reb y prep ni quién da el dato.

### Trampas
- `trampa`: Grano largo (H11) está tipeado 34040, no 23 × dólar (Excel viejo). El seed no trae un precio para ese material como tal.
- `trampa`: Flex, goma EVA y tela de forro son precios en ARS; el paso por USD del Excel se cancela.
- `trampa`: El dólar solo mueve cuero, potro y herrajes; lo que está en pesos no se actualiza solo.
- `trampa`: El CHOOSE del cuero tiene una 7ª opción que apunta al Potro. No existe un cuero 7.
- `trampa`: El GG devuelve el texto "consumo" si el subtotal es ≤ 1: en la app es error de validación.
- `trampa`: 11 filas con error, 13 con costo USD tipeado, fila 242 pegada como valores (Excel viejo): el importador de productos las deja con marca `REVISAR`.
- `trampa` (histórico): Caso de paridad descartado: fila 22 con dólar 1700 daba 44744,77 ARS = 26,32 USD (solo suben cuero y herrajes).
- `trampa`: Los ids de cuero y forro se pisan en el Excel (Estándar y Potro son "1"); en la base cada material tiene id único.
- `trampa`: Hay productos de varios cueros: en v3 el segundo cuero va como línea `EXTRA` (`receta_linea`).
- `trampa`: Los comentarios de celda de la columna AE son la única traza de costo real del taller; importarlos.
- `baseline`: Gerardo cotiza un producto nuevo copiando uno parecido y ajustando (nombres como "como 1660 pero…", "514+chica").
- `baseline`: Consumo = superficie × 2 caras + 20-28 % de desperdicio, muchas veces × 1,2. Forro ≈ 0,7 del cuero.
- `baseline`: M.O. tiende a subir con el tamaño (medianas 6, 8, 12 y 20 mil) pero tiene 36 valores distintos: se importa por fila, no hay escalones. Reb y prep fijos en 1.500; corte por producto (1.500 a 4.000, casi siempre 3.000).
- `baseline`: Herrajes en USD "a criterio"; USD 2 es el piso (hilo y cemento); los actualiza subiendo 10 % sobre el valor viejo (× 1,1, × 1,21, × 1,331).
- `baseline`: Valida al taller por proporción con un producto parecido ("menos de 85 si la otra costó 100"). No replicar.
- `trampa` (histórico): Caso de paridad descartado: fila 22, Portafolio Simple Ch., costo 43024,27 ARS = 27,85 USD con dólar 1545 y GG de 11 %.

### Personas y forma de trabajo
- `contexto`: Gerardo arma los costos y se va pronto; es la fuente de verdad. Alejandro (dueño) quiere margen real y todo masticado.
- `contexto`: Robert es el compañero y jefe de Agustin; las decisiones de alcance y producto se hablan con él.
- `contexto`: M.O. tiene dos valores: estimación del artesano (en la cotización) y precio real del taller (en la orden de fabricación).
- `contexto`: Agustin prefiere explicaciones simples en español rioplatense, con ejemplos del Excel, y que se marque qué es supuesto.
