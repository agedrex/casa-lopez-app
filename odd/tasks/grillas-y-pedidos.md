# Grillas autoguardadas + pedidos como fuente de materiales
Dos frentes en worktrees separados, merge a main.

## Specs
- S1: "Quitemos de toda la aplicacion: Sin cambios todavía. / Descartar / Guardar cambios" — todas las grillas se autoguardan; solo se puede seleccionar una fila y aparece el botón para eliminarla.
- S2: En el formulario de pedidos, no mostrar el ID del material: un campo simple "Material", con opción de añadir otro.
- S3: "en la grilla de materiales y precios no se debería actualizar nada" — los precios se actualizan solo desde un pedido de proveedor.
- S4: Un pedido nuevo afecta el stock de materiales.
- S5: En cada material se ve, por pedido, con qué precio llegó (historial), para tener el costo real al armar producto/lote.

## Tasks
- T1 (S1) worktree grillas-autoguardado: autoSave siempre activo, sin Descartar/Guardar.
- T2 (S2-S5) worktree pedidos-materiales: ver exploración.

## Log
- L1: pedido original del usuario (ver conversación 2026-11-16).
