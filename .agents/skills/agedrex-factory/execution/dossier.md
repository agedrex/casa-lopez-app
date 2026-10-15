# Dossier de ejecución (MCP)

La fuente persistida de ejecución es **un dossier por WO**, independiente de la revisión del WO.
`sf_context` trae el contenido fuente (FRD, Blueprint, WO); `sf_dossier` conserva el trabajo del
ejecutor. Los archivos locales de `execution/plantillas/` son andamios opcionales, no otra fuente
de verdad: copiá su contenido a los campos del dossier. No pongas secretos en los artefactos.

1. `sf_dossier(wo="WO-1", action="read", project="slug")`: leer el registro actual. Si no
   existe, `sf_dossier(wo="WO-1", action="create", checklist="...", context="...",
   implementation_plan="...", project="slug")`. La creación duplicada se rechaza.
2. Antes de editar, leé `version`. `sf_dossier(wo="WO-1", action="update",
   expected_version=1, checklist="...", implementation_plan="...", project="slug")`.
   Solo los campos provistos cambian; los demás permanecen intactos. Un conflicto por versión
   exige volver a leer y reconciliar, nunca sobrescribir a ciegas.
3. Cada ronda de revisión se agrega con `append_review="Ronda N: ..."` y la versión vigente.
   No reemplaces el log completo: las rondas previas son evidencia. El append también incrementa
   la versión y detecta concurrencia. Anotá evidencia y motivos para cada `[SKIP]`.

`sf_update` cambia estado y metadatos del WO; `sf_run` registra tokens/tiempo; ninguno reemplaza
el dossier. Crear o actualizar exige acceso de developer o analyst al proyecto (owner incluido);
la lectura exige acceso al proyecto. `created_by`, `updated_by`, `created_at` y `updated_at`
identifican la mutación, mientras que el audit log registra cada creación y actualización.
