# Zambudio - Tipo de proyecto

Añade el campo **Tipo de proyecto** a los proyectos: un desplegable con la tipología
comercial del proyecto.

## Qué resuelve

Poder clasificar cada proyecto por su modelo comercial (precio cerrado, por tiempo y
materiales, o recurrente), para filtros, informes y (a futuro) lógica de negocio que
dependa de ese tipo.

## Cómo funciona

- Hereda `project.project` y añade el campo `zambudio_project_type` (Selection):
  - `closed` — **Proyecto cerrado** (precio cerrado)
  - `time_materials` — **Tiempo & Materiales**
  - `recurring` — **Recurrente**
- Se muestra en el formulario del proyecto (columna derecha). La vista se ancla con
  `priority` alta para que aparezca junto al resto de campos aunque los añadan otras
  vistas heredadas.

## Configuración

No requiere configuración. El campo queda disponible al instalar.

## Cómo probar

1. Abre cualquier proyecto.
2. Comprueba que aparece **Tipo de proyecto** y que puedes elegir uno de los tres valores.

## Notas

- Es un módulo **independiente** a propósito: su concepto (tipología del proyecto) no
  tiene que ver con `zambudio_project_billable` (check Facturable) ni con
  `zambudio_project_unique_name` (nombre único). Cada módulo hace una sola cosa.
- El campo se crea **sin valor por defecto** (vacío hasta que el usuario lo informe).

**Depende de:** `project`.
