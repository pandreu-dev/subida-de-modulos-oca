# Zambudio Project Task Auto Tags

Modulo Odoo 19 que sustituye dos automatizaciones de Odoo Studio sobre `project.task`.

## Objetivo

Al crear o escribir una tarea, si su **proyecto** tiene la etiqueta `Interno` o
`Formacion`, se anade esa misma etiqueta a la **tarea**.

## Como funciona

- Override de `create` (`@api.model_create_multi`, itera `vals_list`) y `write`.
- Ambos delegan en el helper privado `_zambudio_apply_project_tags()`.
- Sin `base.automation` ni `ir.actions.server`: solo Python en el modelo.
- Anti-recursion mediante la bandera de contexto `skip_zambudio_tags`.
- Referencias por **nombre** (`TAG_INTERNAL_NAME`, `TAG_TRAINING_NAME`), nunca por
  id de BD.
- Multi-etiqueta seguro: escribe solo si falta la etiqueta.

## Diferencia con Studio (importante)

La automatizacion original usaba la operacion m2m `set` (REEMPLAZAR), que podia
borrar otras etiquetas de la tarea. Aqui se **anade** la etiqueta con
`Command.link`, respetando el resto de etiquetas existentes.

## Asunciones a confirmar

- Nombres de etiqueta exactos: `Interno` y `Formacion` (Studio referenciaba los
  ids 35 y 60 respectivamente).
- Las etiquetas viven en el modelo `project.tags` y el campo m2m es `tag_ids` en
  `project.task` y `project.project`.
