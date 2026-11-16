# Mejoras: producto, panel de negocio, proveedores
Tres mejoras independientes, un worktree y una rama por cada una; cada una se mergea a main y todo llega a staging.

## Specs
- S1 (Producto): "En el menú del producto en sí no me gusta que aparezca el código. Eso no me convence. Diría que sería el nombre del material en sí." (mostrar el nombre del material, no el código)
- S2 (Producto): "al final estaría faltando el tema de las horas. Por más que no es un tema, no es parte del costo ni nada, está bueno también el tener el tema de las horas que lleva a ser el producto." (mostrar horas del producto, fuera del costo)
- S3 (Producto): "quita USD 1,00 · $ 1.570,00    Fijo en 1 USD, dólar de referencia 1.570,00 y que solo este el precio de referencia en pesos"
- S4 (Producto): "falta un campo para completar el color"
- S5 (Panel): "siento que se está complicando mucho el tema de tener los costos del negocio, fábrica y tienda. Ese menú de margen que hiciste en cada uno no me convence y no me gusta." (quitar el menú/form de margen de cada uno)
- S6 (Panel): "tiene que ser una grilla, un lugar y un dashboard para poder llevar lo que ya tenemos de los costos. Pero también tiene que ser una forma de llevar los gastos que tiene el negocio, los costos asociados a la fábrica y a la tienda, cada uno por su lado. Es como tener solo el menú de costos, pero uno para la fábrica y otro para la tienda, en el que pueda añadir todos los gastos"
- S7 (Panel): "Esa grilla que existe en gastos del negocio, me gustaría que esté en la parte de costos, ya sea para la fábrica o la tienda."
- S8 (Panel): "toda la mercadería que se añada mes a mes se tiene que añadir en la tienda directamente porque la mercadería se compraba directamente a tienda."
- S9 (Panel, NO implementar ahora): "Y lo que te mencioné del porcentaje y eso que va de la fábrica, la tienda y todo eso, dejémoslo aparte." También: lotes terminados que pasan a costo de tienda con 20%/30%: "después vamos a ir a eso".
- S10 (Proveedores): "El menú de proveedores sigue siendo muy complejo. Me gusta que ahora solo tenga el tema de que seleccionas qué productos provee. Eso está perfecto." (conservar)
- S11 (Proveedores): "en cada uno puedas añadir cuál más te ofrece. ... Imagínate una grilla que tenga el material. El precio de acuerdo a su unidad"
- S12 (Proveedores): "El form de pedidos recibidos debería ser algo mucho más acotado y limitado... Tiene que ser un form mucho más simple."
- S13 (Proveedores): "quitemos el texto de Lo que llegó de este proveedor: qué materiales, cómo vinieron y cuánto costó cada unidad. Cada línea carga el precio del material desde la fecha de recepción. Un pedido no se edita ni se borra: si hay un error, se registra otro."

## Tasks
- T1 S1-S4 worker, worktree ../projecto-casa-lopez-worktrees/mejora-producto, rama feat/mejora-producto: [x] mergeado a main
- T2 S5-S9 worker, worktree ../projecto-casa-lopez-worktrees/mejora-panel-costos, rama feat/mejora-panel-costos: [x] mergeado a main
- T3 S10-S13 worker, worktree ../projecto-casa-lopez-worktrees/mejora-proveedores, rama feat/mejora-proveedores: [x] mergeado a main

## Log
- L1 (usuario, original): ver Specs; pedido: "un worktree por cada una. Luego todas estas, un merge a main. Que cada gente encaré su part y lo merge a main y que finalmente todo llegue a staging para que lo pueda ver y probar."
