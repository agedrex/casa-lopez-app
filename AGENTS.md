# AGENTS.md — Casa López · App de costos

> Contexto obligatorio para cualquier agente de código que trabaje en este repo (Codex CLI, Gentle AI, etc.).
> Leelo entero antes de tocar el DER, el importador o el motor de costeo.
> Última revisión: 2026-10-11 (v5, 2026-10-12: sincronizado con el DER v1 de la WO 1). Fuente: Excel `COSTOS1 en vigencia al 01-09-2026.xlsx`, meeting del equipo e informe de hallazgos.

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

**Sprint:** 3 semanas (15 días hábiles). Cierre esperado: **Gerardo cotiza 2 o 3 productos nuevos sin abrir el Excel.**

**Alcance de la primera versión:** "una forma más amena de usar este Excel", no un cambio del proceso. Se respetan las etapas (es el idioma de Gerardo y de los talleres) y se les ponen nombres claros. El valor nuevo es lo que el Excel no tiene: fechas, historia, costo real y margen real.

**Métrica tentativa:** qué porcentaje de las tareas de Gerardo se automatiza o mejora (sin definir del todo).

**Riesgo principal:** que Gerardo no tenga tiempo antes de irse. Todo lo que el código necesite de él se junta en una lista de preguntas y se prioriza lo bloqueante.

**Stack (acordado, puede cambiar después):** Next.js (frontend) · FastAPI (API y motor de costeo) · Postgres. LLM opcional, solo para clasificar o explicar, **nunca** para calcular costos.

**Gestión del trabajo:** el MCP de La Fábrica (kanban, work orders, documentos fundacionales y blueprints). Git y GitHub para el código.

---

## 2. Reglas de oro (no negociables)

1. **Paridad con el Excel primero, mejoras después.** El motor tiene que dar el mismo costo que el Excel en todas las filas sanas antes de "mejorar" cualquier criterio. Las mejoras entran como parámetros, nunca cambiando la fórmula base en silencio.
2. **No inventar reglas de negocio.** Si algo no está en este archivo o en el Excel, no se asume: se marca como `SUPUESTO` y se pregunta. Ver la sección 6.
3. **Dinero con `Decimal`, nunca `float`.** Python `decimal.Decimal`, Postgres `NUMERIC`. En el frontend no se calcula plata: el backend devuelve los montos ya calculados como string. El recálculo en vivo del formulario llama a la API (o a un endpoint de "previsualizar" sin guardar).
4. **Las cotizaciones son inmutables y versionadas.** Una cotización guardada no se edita: se crea una nueva versión. Hay una sola vigente por producto. Cada cotización guarda una foto de todo lo que usó (dólar, GG, precios de materiales, consumos), para poder reproducir el número años después.
5. **Nada subjetivo sin consenso.** Si una decisión depende del criterio de una persona (qué producto es "comparable", si un consumo es razonable, qué M.O. usar), la app no la toma sola: la propone y una persona la confirma.
6. **El motor es una función pura.** Recibe datos, devuelve un desglose. No lee la base, no lee la hora, no llama a internet. Así se testea contra el Excel sin trampas.
7. **Cada cambio al motor corre la prueba de paridad.** Si la paridad se rompe, el cambio no entra.
8. **El motor es el único que calcula.** Subtotal, GG, costo y USD los calcula el backend. Ni el frontend ni un usuario pueden escribirlos. Si alguien quiere otro número, cambia un dato de entrada y queda registrado quién y por qué.
9. **Cada precio guarda su moneda y su unidad de origen.** Nada se convierte "por las dudas". La conversión a pesos se hace en el motor, con el dólar de la cotización, solo cuando el material está en USD.
10. **Todo tiene fecha.** Precios, dólar, GG, margen, cotizaciones, órdenes y ventas. Sin fecha no hay margen real.
11. **Nada se borra.** Archivar un producto lo oculta de las listas, pero conserva su historia. Lo que se corrige en la migración queda marcado, no se tira.

---

## 3. Cómo funciona el Excel (verificado celda por celda)

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

**Ejemplo real, fila 22 (Portafolio Simple Ch., modelo 6):** cuero 37080 × 0,25 = 9270; forro tela 4053 × 0,2 = 810,6; herrajes 4 USD = 6180; flex 0,45 m² = 4500; goma 0; corte 3000 + reb 1500 + prep 1500; M.O. 12000. Subtotal 38760,6; GG 4263,67; **costo 43024,27 ARS = 27,85 USD**. Este caso tiene que ser el primer test del motor.

### 3.5 Fórmula del motor (decidida para la paridad)
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

### 3.5.1 Segundo caso de prueba: recotización
Misma fila 22 con dólar 1700: cuero 0,25 × 24 × 1700 = 10200; herrajes 4 × 1700 = 6800; forro, flex, corte, reb, prep y M.O. **no cambian** (están en pesos). Subtotal 40310,6 → **costo 44744,77 ARS = 26,32 USD**. Este test prueba que el motor respeta la moneda de cada insumo. Fíjate que el costo en USD **baja** cuando sube el dólar, porque la parte en pesos pesa menos en dólares.

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

### 3.6 Otros bloques de la hoja
- **Filas 351-366: variantes.** Código de modelo con barra (`103/1`, `2538/3`): son variantes de un producto base. En el DER: `producto.producto_base_id`.
- **Filas 368-370: M.O. "tentativa" por tamaño** (fecha 31/7/2024): Bolso grande 20000, Portafolio mediano 12000, Cartera chica 8000. Es una referencia, no una regla.
- **Filas 374-381: tabla de Necesaires.** Es un duplicado de filas del bloque central con dos columnas extra (AJ costo anterior, AK % de variación). **No es otra tabla:** "necesaire" es una categoría de producto. Al importar, deduplicar.
- **Zona AJ373 en adelante:** ignorar (decisión de Agustin).
- **Hoja `Hoja1`:** vacía.
- Columnas A a E traen datos sueltos (índice, notas como "esta", nombres de personas, fechas). Se importan como notas o metadatos, no como reglas.

### 3.7 Reglas implícitas de Gerardo (su baseline)

Son las reglas que el Excel aplica sin decirlo: de fórmula, de criterio o de forma de pensar. Sirven para entender cómo cotiza Gerardo hoy y como **referencia de paridad**. No son reglas aprobadas para la app: las que son criterio se convierten en sugerencias o parámetros, nunca en automatismos, hasta que Gerardo y Alejandro las confirmen.

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
1. En la paridad, las reglas A se replican al pie de la letra.
2. Las reglas B y C **no** se automatizan. Alimentan las sugerencias para productos nuevos (`plantilla_linea`, fase 2) y las alertas de calidad, por ejemplo "M.O. fuera del escalón de su tamaño" o "forro mayor que el cuero".
3. Cada regla inferida es una pregunta para Gerardo (ver `preguntas-gerardo-robert.md`). Cuando la confirme, se cambia "Inferida" por "Confirmada" con la fecha.

---

## 4. Trampas del Excel que un agente puede romper

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

## 5. Modelo de datos (DER v1)

**La fuente de verdad es `docs/der.md` (DER v1, 2026-10-12, WO 1).** Su porqué está en `wo1-modelo-conceptual.md`, sección 2. Si este archivo y `der.md` no coinciden, **gana `der.md`** y se corrige este. El DER es **provisional**: Robert lo autorizó para la base demo de staging mientras Gerardo responde las preguntas. No se cambia sin pasar por un work order.

### Fase 1: primera migración (11 tablas)

| Tabla | Para qué | Lo que no hay que romper |
|---|---|---|
| `categoria` | Lista abierta: cartera, portafolio, billetera, necesaire… | `nombre` único. |
| `producto` | Cada artículo. Una variante apunta a su base con `producto_base_id`. | **`id` es la única identidad estable.** `codigo_modelo` es texto y **no es único**. `codigo_erp` es nullable y único (vacío hasta que Alejandro diga cuál es). `fila_excel` es única y sirve para trazar. `nombre_original` guarda la columna F tal cual. El estado (activo/archivado) lo cambia una persona. |
| `etapa` | Datos fijos: CUERO, FORRO, HERRAJES, REFUERZO, CORTE, REB, PREP, MANO_OBRA. | **REB y PREP no se renombran** hasta que Gerardo diga qué son. Flex y goma son una sola etapa, REFUERZO. |
| `material` | Cada cosa que se compra, con `tipo`, `unidad_consumo` y `codigo_excel` (`cuero:1`, `forro:1`, `insumo:W5`). `cotizable = false` bloquea lagarto y yacaré. | **No tiene `proveedor_id` ni moneda.** El proveedor y la moneda viven solo en `precio_material`. |
| `proveedor` | Mínimo viable: nombre, CUIT, dirección, teléfono, contacto, categorías, activo. | CUIT único, nullable. |
| `precio_material` | La oferta de un proveedor a una fecha. Solo se agregan filas. | `proveedor_id` nullable (no sabemos a quién se le compra el cuero). Guarda `precio` por `unidad_precio`, `moneda`, y la presentación de compra (plancha 1 × 1,40 m a $14.000). |
| `tipo_cambio` | Dólar por fecha y fuente. | Único por (`fecha`, `fuente`). |
| `parametro` | **Tabla nueva.** Claves `GG_PCT` y `GANANCIA_PCT`, con `vigente_desde` y `estado_validacion` (supuesto o confirmado). | Semilla: GG 11 y ganancia 0, ambos `supuesto`. La ganancia **no entra en el costo**. |
| `cotizacion` | La foto del costo de un producto. Versionada, inmutable. | Una sola `vigente` por producto (índice único parcial). Guarda `tc_valor` y `gg_pct` como foto. En la migración, `fecha` = **2026-09-01**; la columna E del Excel va a `dato_origen` (jsonb), junto con B, D, AI original, AJ/AK y comentarios. |
| `cotizacion_linea` | Un renglón del costo: etapa, material, cantidad, precio en moneda original, total en pesos. | `orden` permite dos líneas de cuero. **`cantidad` NULL = dato faltante (con marca). Un 0 en el Excel no crea línea: significa "no lleva".** |
| `marca_calidad` | Alertas sobre datos dudosos, con la celda de origen. | Al menos uno de producto, cotización o material. |

### Fase 2: definida, todavía no se migra

`taller`, `orden_fabricacion` (el "lote"), `precio_venta`, `venta` y `plantilla_linea`. Esperan a que Gerardo responda sobre M.O., talleres y lotes, y Alejandro sobre ventas y ERP. **No las crees antes** ni las inventes distintas: están definidas en `der.md`, sección 7.
- `orden_fabricacion` separa `precio_pedido_unitario` de `precio_pagado_unitario` (comentario AE53: "pidió $1.000, pagamos $750").
- La "receta" de un producto existente no necesita tabla: son las cantidades de su cotización vigente. Recotizar copia esas cantidades y actualiza precios y dólar. `plantilla_linea` es solo para sugerir productos nuevos.

### Reglas que siguen valiendo
- `cotizacion_linea.material_id` obligatorio si la etapa lo requiere (cuero, forro, refuerzo); lo valida el backend.
- **Una línea solo usa un precio si `unidad_precio = material.unidad_consumo`** (regla del backend). Así el lagarto en cm no se multiplica por un consumo en m².
- **M.O. en dos lugares:** la cotización guarda la estimación de la planilla; el precio real del taller vivirá en `orden_fabricacion` (fase 2). Se compara contra el mismo modelo en lotes anteriores, no contra "productos parecidos".
- **Consumo:** se migra como bruto con `incluye_desperdicio = true` (supuesto). La cantidad neta y el desperdicio por material se agregan como columnas solo si Gerardo lo confirma.
- **GG y margen** son parámetros con fecha. Ojo: un recargo de 27 % sobre costo 100 da precio 127 (margen real 21 %); un margen de 27 % sobre el precio da 137. Está sin definir.
- **Procedencia:** precios, dólar, parámetros y líneas llevan `fuente` y `fuente_detalle` (por ejemplo `Marroquineria1!W5`).

### Convenciones técnicas
- Plata `NUMERIC(14,4)`, consumos `NUMERIC(10,4)`, dólar `NUMERIC(12,4)`, porcentajes `NUMERIC(6,3)`. En SQLAlchemy, `Numeric(14, 4, asdecimal=True)`; ids `BigInteger` + `Identity()`.
- `created_at timestamptz` en todas las tablas; `updated_at` en `producto`.
- **Todas las tablas van en el schema `costos`**, incluida la tabla de versiones de Alembic (`version_table_schema="costos"`). Alembic solo mira ese schema. **Better Auth (WO 4) queda en `public`** con su propia CLI: nunca generar migraciones que toquen `user`, `session`, `account` o `verification`. `cotizacion.creado_por` guarda el id de usuario como texto, sin FK por ahora.
- Migraciones con Alembic (WO 2). `der-borrador.sql` es una prueba, **no** la migración. Nunca cambiar la base a mano.
- Plataforma: Railway, environment `staging`. Producción no se toca sin autorización.
- Las cosas con historia (precios, dólar, parámetros, cotizaciones) no tienen `UPDATE`: se agrega una fila con fecha.

---

## 5.1 Pantallas y roles (arquitectura de información)

| Sección | Para quién | Qué hace |
|---|---|---|
| Tablero | Alejandro | Costo actual en ARS y USD, variación desde la última cotización, margen teórico y real, alertas |
| Productos | Todos | Buscador y filtros (categoría, tamaño, estado, alertas). Ficha con costo por etapa, historial, órdenes, precio de venta |
| Cotizar | Cotizador | Paso a paso por etapa con valores sugeridos por la plantilla y total en vivo (calculado por la API) |
| Materiales y precios | Cotizador | Catálogo con unidad y moneda, precios nuevos, dólar del día, recotización masiva con variación por etapa |
| Fabricación | Cotizador, Alejandro | Órdenes por taller con cantidad, fecha y precio real, contra la cotización |
| Talleres y proveedores | Cotizador | Agenda básica de activos |
| Calidad de datos | Cotizador | Productos migrados con alertas para ir limpiándolos |
| Configuración | Administrador | Etapas, categorías, plantillas, GG, margen, desperdicio por material |

Roles: **cotizador** (Gerardo y quien lo reemplace), **dueño** (Alejandro: ve todo y aprueba cambios de GG o margen), **administrador** (nosotros). Principio de UI: resumen primero (una línea por producto), detalle a demanda; no replicar el ir y venir del Excel.

Taxonomía: etapas fijas en este orden: material exterior, material interior, accesorios y detalles (herrajes, refuerzos, insumos de armado), refinamiento (corte, reb, prep; en la base los códigos son CORTE, REB y PREP y no se renombran a "rebajado" ni "preparación" hasta que Gerardo lo confirme), mano de obra, gastos generales, costo. Categorías inferidas de los nombres (lista abierta, a validar): cartera (unas 120), portadocumentos, portavalores, portarretratos, portafolio, carpeta, billetera, monedero, necesaire, bolso, tarjetero, sobre, morral, mochila, bandolera, riñonera, llavero, bandeja, organizador, alhajero, mantel o individual, cinturón y correa, otros. Tamaño: chico, mediano, grande.

---

## 6. Supuestos abiertos (NO resolverlos por tu cuenta)

Todos van como **parámetros configurables** con el valor que hoy usa el Excel, y un comentario `# SUPUESTO: validar con Gerardo`.

| # | Tema | Valor de paridad | Pregunta pendiente |
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

La lista completa de preguntas, ordenada por sección y prioridad, está en `preguntas-gerardo-robert.md`.

Regla: si una tarea del kanban necesita una de estas respuestas, se implementa con el parámetro y se deja anotado en el work order que falta validar. **No se "elige" un valor nuevo.**

---

## 7. Importador del Excel

- Script en Python (`openpyxl`) que lee el Excel original y genera los datos iniciales.
- Lee **valores y fórmulas** (dos pasadas: `data_only=True` y `False`) para saber qué celdas son fórmula y cuáles están tipeadas.
- Sigue las reglas de migración de `der.md`, sección 5. En resumen:
- Importa materiales y precios en su moneda real (cueros 1, 2, 6 y potro en USD por m²; grano largo ARS 34.040 por m² con marca `dolar_congelado`; tela, flex, goma y cartón en ARS por m² con la plancha como presentación; lagarto y yacaré en USD por cm, `cotizable = false`), productos (bloque central + variantes, deduplicando necesaires) y una cotización por producto con dólar 1545 y **fecha 2026-09-01** (Rouez y Acropol, 2026-09-03). Los consumos van como líneas de esa cotización, **no** como `plantilla_linea` (es fase 2).
- Herrajes: una línea sin material, cantidad 1, unidad `global`, precio en USD. Corte, reb, prep y M.O.: una línea cada una, cantidad 1, unidad `producto`, en ARS.
- **Un 0 no crea línea; una celda vacía donde debería haber dato crea la línea con `cantidad` NULL** y una marca.
- Filas con error: producto creado, cotización en `borrador` con lo que se sabe y marca. Fila 242: líneas con el precio tipeado en ARS, sin `precio_material_id`, marca `dolar_congelado`.
- Variantes "/n": `producto_base_id` solo si hay exactamente un producto con ese código base; si hay dos (514) o ninguno (1/65, 149/2, 500/1, 553/1, 620/1), queda NULL con marca.
- Columna E → `dato_origen.fecha_costeo_excel`; AI → `dato_origen.ai_excel`.
- Cada fila problemática entra con su `marca_calidad` ("error en origen", "costo tipeado", "modelo duplicado", "sin fecha", "multi-cuero", "costeo por varias unidades"); no se descarta nada en silencio.
- Lee también los **comentarios de celda** (columna AE y R140) y las columnas B, D y E, y los guarda como notas (los comentarios, como historia, no como precios).
- Lee G como texto, descarta las filas 348 a 350 y deduplica la tabla de Necesaires (374 a 381) contra el bloque central.
- Recalcula siempre el costo; AI del Excel queda solo como comparación.
- Tipos de `marca_calidad` (lista de `der.md`): error_origen, costo_tipeado, dolar_congelado (242, H11), sin_consumo_cuero (38, 234), costeo_parcial (48, 111), unidad_incompatible, modelo_repetido, variante_sin_base, base_ambigua, costeo_varias_unidades, multi_cuero, costo_alternativo_sin_rotulo (AJ/AK de 180, 244, 245, 301, 312), sin_tipo_cuero.
- Proveedores y fechas de insumos: Rouez (flex) y Acropol (goma eva) con fecha 03/09/2026; el resto con 01/09/2026, fuente "manual Excel".
- Al terminar imprime un resumen: cuántos productos, cuántos sanos, cuántos marcados y por qué.
- Genera un fixture `tests/fixtures/excel_paridad.json` con, por fila sana: entradas y el costo ARS y USD que dio el Excel.

---

## 8. Prueba de aceptación: paridad

- Test automático (`pytest`) que corre el motor sobre cada fila del fixture y compara el costo ARS y USD contra el Excel con tolerancia de 0,01.
- **Filas sanas** = el costo USD (columna AI) sale de una fórmula y no da error. Mi reconteo: 296 en el bloque central, más las variantes y necesaires con fórmula; el informe habla de 315. El importador reporta el número exacto y ese número queda fijo en el test.
- Casos de prueba fijos, ya verificados con el SQL borrador en Postgres 16:
  - Fila 22 (Portafolio Simple Ch.): **43.024,27 ARS = 27,85 USD**.
  - Fila 22 con dólar 1.700: **44.744,77 ARS = 26,32 USD** (solo suben cuero y herrajes).
  - Fila 85 (Cartera Bugatti portafolio, carpincho y forro potro en USD): **201.003,24 ARS = 130,10 USD**.
- Si la paridad no da, se busca la causa en el Excel antes de tocar el motor. Nunca se ajusta el test para que pase.

---

## 9. Plan del sprint (orden de trabajo)

1. **DER** (2 días, revisarlo con Gerardo).
2. **Importador** (2 días).
3. **Motor + paridad** (1 día; el código es corto, el tiempo se va en igualar al Excel).
4. **API** FastAPI (2-3 días).
5. **Pantallas** Next.js: lista y ficha de producto (2), formulario de cotizar con recálculo en vivo y validaciones (2).
6. **Precios y dólar** con recotización (2-3).
7. **Órdenes de fabricación y precio de venta** (2), **tablero y calidad** (3-4): versión mínima o sprint 2.
8. **Prueba con Gerardo** (2-3).

Total estimado 18-24 días contra 15 disponibles: órdenes y tablero quedan mínimos. Switch gradual: lo nuevo se cotiza en la app; lo viejo solo registra venta.

**Más adelante (no ahora):** proveedores completos (hay un Excel aparte, con datos desde 2004), scraping del dólar, integración con el ERP, sugerir cuándo producir según demanda y costo.

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

- [ ] ¿Toqué el motor? Corrí la prueba de paridad y pasa.
- [ ] ¿Algún monto pasó por `float`? (No debería.)
- [ ] ¿Agregué una regla de negocio nueva? Está como parámetro y marcada `SUPUESTO`.
- [ ] ¿Modifiqué una cotización guardada? (No se puede: nueva versión.)
- [ ] ¿Cambié el DER? Hay migración de Alembic.
- [ ] ¿El PR explica en simple qué cambia para el usuario?

---

## Anexo: memorias iniciales para Engram

Listas para cargar como memorias persistentes (una por línea o bloque).

### Decisiones
- `decision`: Stack Next.js + FastAPI + Postgres. LLM solo para clasificar o explicar, nunca para calcular costos.
- `decision`: El motor de costeo replica el Excel: subtotal = cuero + forro + herrajes + flex + goma + corte + reb + prep + M.O.; costo = subtotal × 1,11; USD = costo / dólar.
- `decision`: Paridad con el Excel primero (tolerancia 0,01 ARS en filas sanas); mejoras de criterio después, como parámetros.
- `decision`: Dinero con Decimal y NUMERIC. Nunca float. El frontend no calcula plata.
- `decision`: Cotizaciones inmutables y versionadas; una vigente por producto; guardan foto de dólar, GG y precios usados.
- `decision`: Necesaires no son una tabla aparte: es una categoría de producto.
- `decision`: Consumo del Excel = consumo estándar por producto; productos nuevos se sugieren con la mediana de su categoría y tamaño, confirmada por una persona.
- `decision`: Activo/archivado de un producto lo decide una persona.
- `decision`: Ignorar la zona AJ373 del Excel.
- `decision`: Orden del sprint: DER, importador, motor, API, pantallas. Órdenes y tablero mínimos o al sprint 2.
- `decision`: DER v1 (2026-10-12) es la fuente de verdad: docs/der.md. Fase 1 = 11 tablas (categoria, producto, etapa, material, proveedor, precio_material, tipo_cambio, parametro, cotizacion, cotizacion_linea, marca_calidad). Fase 2 = taller, orden_fabricacion, precio_venta, venta, plantilla_linea.
- `decision`: producto.codigo_modelo es texto y no es único; codigo_erp nullable y único; fila_excel única. La identidad es producto.id.
- `decision`: material no tiene proveedor ni moneda; ambos viven en precio_material.
- `decision`: En cotizacion_linea, cantidad NULL = dato faltante; un 0 del Excel no crea línea.
- `decision`: Cotizaciones migradas con fecha 2026-09-01; la columna E va a dato_origen.
- `decision`: Tablas en el schema "costos"; Better Auth en "public". Railway staging.
- `decision`: Etapas REB y PREP no se renombran hasta que Gerardo diga qué son.

### Supuestos abiertos (validar con Gerardo antes de cambiarlos)
- `supuesto`: GG 11 % probablemente es Gastos Generales, no IVA.
- `supuesto`: La ganancia 27 % vale 0 y no se usa; el Excel termina en costo.
- `supuesto`: El desperdicio del 30 % no se aplica; ya está dentro de los consumos (20-28 %).
- `supuesto`: Lagarto y yacaré tienen precio en USD por cm; bloqueados hasta definir la unidad.
- `supuesto`: M.O. real la cobra el taller por producto/lote; el artesano cotiza en horas. Hoy se usa "productos comparables" (subjetivo).
- `supuesto`: No sabemos si el "modelo" del Excel es el código del ERP.
- `supuesto`: No sabemos qué son exactamente corte, reb y prep ni quién da el dato.

### Trampas
- `trampa`: Grano largo (H11) está tipeado 34040, no 23 × dólar. Usarlo tal cual para la paridad.
- `trampa`: Flex, goma EVA y tela de forro son precios en ARS; el paso por USD del Excel se cancela.
- `trampa`: El dólar solo mueve cuero, potro y herrajes; lo que está en pesos no se actualiza solo.
- `trampa`: El CHOOSE del cuero tiene una 7ª opción que apunta al Potro. No existe un cuero 7.
- `trampa`: El GG devuelve el texto "consumo" si el subtotal es ≤ 1: en la app es error de validación.
- `trampa`: 11 filas con error, 13 con costo USD tipeado, fila 242 pegada como valores: se importan marcadas y no entran en la paridad.
- `trampa`: Test de recotización: fila 22 con dólar 1700 da 44744,77 ARS = 26,32 USD (solo suben cuero y herrajes).
- `trampa`: Los ids de cuero y forro se pisan en el Excel (Estándar y Potro son "1"); en la base cada material tiene id único.
- `trampa`: Hay productos de varios cueros: la cotización usa líneas genéricas por etapa, no columnas fijas.
- `trampa`: Los comentarios de celda de la columna AE son la única traza de costo real del taller; importarlos.
- `baseline`: Gerardo cotiza un producto nuevo copiando uno parecido y ajustando (nombres como "como 1660 pero…", "514+chica").
- `baseline`: Consumo = superficie × 2 caras + 20-28 % de desperdicio, muchas veces × 1,2. Forro ≈ 0,7 del cuero.
- `baseline`: M.O. tiende a subir con el tamaño (medianas 6, 8, 12 y 20 mil) pero tiene 36 valores distintos: se importa por fila, no hay escalones. Reb y prep fijos en 1.500; corte por producto (1.500 a 4.000, casi siempre 3.000).
- `baseline`: Herrajes en USD "a criterio"; USD 2 es el piso (hilo y cemento); los actualiza subiendo 10 % sobre el valor viejo (× 1,1, × 1,21, × 1,331).
- `baseline`: Valida al taller por proporción con un producto parecido ("menos de 85 si la otra costó 100"). No replicar.
- `trampa`: Test base: fila 22, Portafolio Simple Ch., costo 43024,27 ARS = 27,85 USD con dólar 1545.

### Personas y forma de trabajo
- `contexto`: Gerardo arma los costos y se va pronto; es la fuente de verdad. Alejandro (dueño) quiere margen real y todo masticado.
- `contexto`: Robert es el compañero y jefe de Agustin; las decisiones de alcance y producto se hablan con él.
- `contexto`: M.O. tiene dos valores: estimación del artesano (en la cotización) y precio real del taller (en la orden de fabricación).
- `contexto`: Agustin prefiere explicaciones simples en español rioplatense, con ejemplos del Excel, y que se marque qué es supuesto.
