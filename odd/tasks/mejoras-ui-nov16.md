# mejoras-ui-nov16 — 10 mejoras de UI (2026-11-16)
Objetivo: todo mergeado a main y desplegado a staging (auto por CI). Worktrees en ../projecto-casa-lopez-worktrees/. Tests: `pnpm lint && pnpm build` (front), pytest (backend si se toca).

## Specs (textos del usuario, verbatim)
- S1 "fusionemos Panel y Negocio porque siento que podrian ir juntos. Siempre priorizando que es una App de Costos y que lo que tiene Panel es prioridad pero dan informacion muy parecida"
- S2 "Impuestos quiero que lo movamos como una pestana a Costos Variables"
- S3 "Que no se llame Ajustes sino solo usuario y lo de Google Sheet que este aparte."
- S4/S5 Form de producto: "Modelo, Nombre, Cuero, Color, Confecionamiento, Nota. La fecha y eso deberia ser en automatico y tambien dejemos lo de marcar. Que el diseno del form sea algo mas simple y quitemos eso de Elija un modelo y defina lo propio del producto (cuero, color y demás). Las medidas y consumos los dicta el modelo."
- S6 "En la Grilla de Producto aumentemos la columna de Cuero y Color"
- S7 Grilla de modelos: "todas las columnas relacionadas a los materiales y uso, ... cuero (metros cuadrados), flex (metros cuadrados) y herrajes, sigan en dólares [herrajes en USD; en cantidad de herrajes si corresponde]... respeten el mismo orden que tiene el formulario y que tengan la misma información que tiene el formulario que se crea a la hora de hacer un nuevo modelo. Que la columna horas y validación ya no estén [horas sí se mantiene dentro del modelo específico, no en la grilla]; validación es repetitivo con estado"
- S8 Lotes: "más simple... Quitemos ese resumen de En casa o en taller... Al crear un nuevo Lote hay un form de Mas opciones que quiero que quites. y la fecha deberia ser en automatico. y el nombre del lote deberia ser el codigo con la fecha en que se creo. Tambien tienen un form de cargar cuero nuevo que no me gusta"
- S9 Taller: "barra de la izquierda... no esté tan dividido. Que solo tenga el menú 'Lotes y modelos'. títulos un poco más grandes y se entienda la diferencia entre herrajes y consumo y no quiero que haya el de añadir una fila. Del lado del taller no se debería poder subir una foto. solo debería haber el botón Guardar y Enviar y quitemos eso que dice 'Al completar, la hoja pasa al administrador y ya no la podés editar, salvo que te la devuelva con comentarios'. Las filas vacías no hace falta borrarlas."
- S10 "en el menú del taller la grilla de lotes y modelos tenga el mismo diseño [que] modelos. Lo mismo para el diseño de Lotes del lado del administrador"

## Tasks (worktree → branch)
- T1 S1,S2,S3 (+ nav.ts incl. TALLER_NAV de S9) — shell — delegated — pending
- T2 S4,S5,S6 — productos — delegated — pending
- T3 S7,S9(hoja del taller) — modelos — delegated — pending
- T4 S8,S10 — lotes (después de mergear T3, usa su diseño de grilla) — delegated — pending

## Log
L1 (2026-11-16) Usuario: lista de 10 mejoras (ver Specs) + "si es necesario, al worktree, que trabaje cada una parte y luego las merge a main... todo esté en el main y ya hayas plegado un staging".
Route: T1-T3 paralelo (superficies disjuntas, varios archivos c/u); T4 secuencial por dependencia de diseño.
