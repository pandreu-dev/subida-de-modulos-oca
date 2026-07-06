# Analisis WIP

## Revisado

- `aunna_wip_budget_calc` calcula lineas WIP y guarda `project_id` en `aunna.wip.calculation.line`.
- `aunna_wip_accounting` crea `account.move` y `account.move.line` con `analytic_distribution`.
- El problema era que la distribucion analitica no garantiza que `account.analytic.line.project_id` quede informado.

## Solucion aplicada

- Se marcan las lineas contables WIP con:
  - `aunna_wip_project_id`
  - `aunna_wip_calculation_line_id`
- Si la distribucion analitica WIP llega con el proyecto al `0%`, se reemplaza por la cuenta analitica del calculo al `100%`.
- Si un asiento antiguo no trae distribucion en la linea de ingreso WIP, se identifica por la cuenta de ingreso WIP configurada y se reconstruye igual.
- Tras publicar el asiento, se localizan las lineas analiticas generadas por `move_line_id`.
- Si existe `project_id` en `account.analytic.line`, se rellena con el proyecto origen WIP.
- Si el apunte analitico ya existe pero quedo a `0,00` por una distribucion mal interpretada, se reconstruye desde la linea contable WIP corregida y con el importe real del asiento.
- La reversion WIP tambien recibe el mismo enlace.
- Si el asiento ya existia, al abrirlo desde el calculo WIP se intenta reconstruir el enlace desde la distribucion analitica de sus lineas.

## No se modifica

- Calculo WIP.
- Importes.
- Cuentas.
- Distribucion analitica valida. Solo se corrige el caso `0%`.
