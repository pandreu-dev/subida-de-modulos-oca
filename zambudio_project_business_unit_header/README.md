# Zambudio - Unidad de negocio en cabecera de proyecto

Hace más visible la **Unidad de negocio** en el formulario de proyecto, según pidió
Manuel: se **duplica en la cabecera** el campo que está en la pestaña *Ajustes*, y en la
cabecera va en **solo lectura** (solo se cambia desde el de Ajustes).

## Qué hace

- Vista heredada de `project.edit_project`: añade el campo **`x_plan5_id`** ("Unidad de
  negocio", un plan analítico) en la **cabecera**, junto a *Gerente de proyecto*.
- El campo de la cabecera es **`readonly`** → no se edita ahí; el editable sigue siendo el
  de la pestaña **Ajustes → ANALÍTICO → Unidad de negocio** (ese NO se toca).

## Notas

- `x_plan5_id` es el mismo campo que ya usa `zambudio_project_delegation` en su vista de
  búsqueda; no se crea ni se modifica el campo, solo se muestra.
- Si se prefiere el campo en otro punto de la cabecera (p. ej. tras "Tiempo asignado"),
  es cambiar el ancla del `position="after"` en
  `views/project_project_views.xml` (una línea).

## Dependencias

- `project`
