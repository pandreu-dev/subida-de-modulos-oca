# Analisis WIP

## Revisado

- `aunna_wip_budget_calc` calcula lineas WIP y guarda `project_id` en `aunna.wip.calculation.line`.
- `aunna_wip_accounting` crea `account.move` y `account.move.line` con `analytic_distribution`.
- El problema era que la distribucion analitica no garantiza que `account.analytic.line.project_id` quede informado.

## Solucion aplicada

- Se marcan las lineas contables WIP con:
  - `aunna_wip_project_id`
  - `aunna_wip_calculation_line_id`
- Si la distribucion analitica WIP llega con el proyecto al `0%`, se normaliza a `100%`.
- Tras publicar el asiento, se localizan las lineas analiticas generadas por `move_line_id`.
- Si existe `project_id` en `account.analytic.line`, se rellena con el proyecto origen WIP.
- La reversion WIP tambien recibe el mismo enlace.
- Si el asiento ya existia, al abrirlo desde el calculo WIP se intenta reconstruir el enlace desde la distribucion analitica de sus lineas.

## No se modifica

- Calculo WIP.
- Importes.
- Cuentas.
- Distribucion analitica valida. Solo se corrige el caso `0%`.
