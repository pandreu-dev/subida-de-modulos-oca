# Zambudio - Ocultar apuntes WIP de partes de horas

Oculta de las listas de **Partes de horas** los apuntes analíticos generados desde
asientos (el **ingreso reconocido WIP**, cuenta 705), que no son partes de horas reales.

## Qué resuelve

En Odoo, cualquier `account.analytic.line` con `project_id` se considera un **parte de
horas**. Los apuntes del asiento WIP, si llevan proyecto, aparecen en Partes de horas
(app, pedido de venta, tablero del proyecto) y confunden: no son partes reales, no se
pueden validar, e incluso llegaban a contar como horas.

## Cómo funciona

Discriminador seguro: un parte **real** nunca se genera desde un asiento, así que su
`move_line_id` siempre está vacío. Los apuntes de asiento (WIP, etc.) **sí** llevan
`move_line_id`. El módulo añade `('move_line_id','=',False)` en las vistas de partes:

- **Acciones almacenadas** de `account.analytic.line` que filtran por `project_id` (app
  Partes de horas): se parchean en cada instalación/actualización, vía `<function>`
  (`ir.actions.act_window._zambudio_hide_move_lines_from_timesheets`). Idempotente.
- **Botón "Partes de horas" del pedido de venta** (`sale.order.action_view_timesheet`) y
  **del tablero del proyecto** (`project.project.action_project_timesheets`): construyen
  su dominio en Python, así que se reinyecta el marcador heredando esos métodos.

La vista de **Apuntes analíticos** (sin filtro por `project_id`) **no se toca**: no oculta
ningún parte real y no afecta a la contabilidad.

## Configuración

No requiere configuración.

## Cómo probar

1. Partes de horas (Todos / A validar / Mis partes), botón Partes de horas de un pedido de
   venta, y tablero del proyecto → NO deben aparecer las líneas "WIP ...".
2. Los partes de horas reales siguen apareciendo.

## Nota importante

Desde que `aunna_wip_project_link_fix` (Opción B, jul-2026) **quita el `project_id`** de
los apuntes WIP, esas líneas **ya no son partes de horas de raíz**, así que este módulo
**deja de ser imprescindible**. Se puede mantener instalado como **red de seguridad** (no
hace daño: si no hay líneas WIP con proyecto, no oculta nada).

**Depende de:** `hr_timesheet`, `sale_timesheet`.
