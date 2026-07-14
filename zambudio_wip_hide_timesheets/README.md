# Zambudio - Ocultar apuntes WIP de partes de horas

## Problema

El modulo `aunna_wip_project_link_fix` rellena el `project_id` en los apuntes
analiticos generados por los asientos de **ingreso reconocido WIP** (cuenta 705), para
que en **Apuntes analiticos** se agrupen bajo su proyecto (y no como "Ninguno").

Efecto colateral: en Odoo, cualquier `account.analytic.line` con `project_id` se
considera un **parte de horas**, por lo que esas lineas "WIP ..." aparecen en la vista
de **Partes de horas** y confunden (no son partes reales, no se pueden validar).

## Solucion

Se anade `('move_line_id', '=', False)` al dominio de las acciones de Partes de horas.

- Un parte de horas **real** nunca se genera desde un asiento, asi que su
  `move_line_id` siempre esta vacio -> **no se oculta ningun parte real**.
- Los apuntes generados desde asientos (WIP y similares) **si** llevan `move_line_id`
  -> se ocultan de Partes de horas.
- La vista de **Apuntes analiticos** (dominio sin `project_id`) **no se toca**: las
  lineas WIP siguen visibles ahi, agrupadas por proyecto (no se rompe lo de
  `aunna_wip_project_link_fix`).

El parcheo lo hace `ir.actions.act_window._zambudio_hide_move_lines_from_timesheets`,
que se ejecuta en cada instalacion/actualizacion (via `<function>`) sobre todas las
acciones de `account.analytic.line` cuyo dominio filtra por `project_id`. Es
idempotente.

## Prueba

1. Instalar el modulo.
2. Ir a **Partes de horas** (Todos / A validar / Mis partes).
3. Comprobar que ya NO aparecen las lineas con descripcion "WIP ..." (ingreso
   reconocido), pero SI siguen los partes de horas reales.
4. Ir a **Contabilidad > Apuntes analiticos**, agrupar por proyecto: las lineas WIP
   siguen ahi bajo su proyecto.
