# Aunnna WIP - Calculo de presupuesto analitico

## Objetivo

Este modulo calcula el WIP de presupuestos analiticos a una fecha concreta.

La necesidad funcional es poder calcular el teorico, el alcanzado y el WIP de un presupuesto analitico en una fecha pasada o deseada, sin depender del dia actual ni de pedidos de venta.

El modulo no contabiliza. Solo calcula y guarda snapshots de calculo.

## Que es WIP en este modulo

WIP se calcula como:

```text
WIP = Teorico validado - Alcanzado
```

Donde:

- Teorico validado: importe teorico que deberia haberse alcanzado a la fecha de corte. Por defecto coincide con el teorico calculado, pero puede ajustarse manualmente antes de contabilizar.
- Alcanzado: importe real imputado en analitica hasta la fecha de corte.
- WIP a contabilizar: diferencia entre teorico validado y alcanzado.

## Dependencias

El modulo depende de:

- `account`
- `analytic`
- `account_budget`
- `project`

Estas dependencias permiten trabajar con presupuestos analiticos, cuentas analiticas, lineas analiticas, companias, moneda y proyectos.

## Modelos principales

### `budget.analytic`

El modulo hereda el presupuesto analitico y anade:

- `wip_recalculation_date`: fecha de corte usada para recalcular WIP.
- `wip_last_calculation_id`: ultimo calculo WIP generado.
- `wip_calculation_count`: contador de calculos WIP asociados.

Tambien anade acciones para:

- Abrir el asistente de calculo.
- Calcular WIP.
- Ver calculos WIP asociados.

### `aunna.wip.calculation`

Modelo propio que guarda cada snapshot de calculo WIP.

Campos principales:

- Presupuesto analitico.
- Compania.
- Moneda.
- Fecha de calculo.
- Origen: manual o automatico.
- Estado: calculado o cancelado.
- Lineas del calculo.
- Teorico calculado.
- Teorico validado.
- Alcanzado.
- WIP calculado.
- WIP a contabilizar.
- Notas.

### `aunna.wip.calculation.line`

Modelo propio que guarda el detalle por linea de presupuesto.

Campos principales:

- Linea de presupuesto origen.
- Cuenta analitica.
- Proyecto.
- Periodo desde y hasta.
- Presupuestado.
- Teorico calculado.
- Teorico validado.
- Alcanzado.
- WIP calculado.
- WIP a contabilizar.
- Motivo del ajuste.
- Indicador de ajuste manual.
- Nota de calculo.

## Formula del teorico

El teorico se calcula de forma proporcional por dias:

```text
Si fecha de corte < fecha inicio: teorico = 0
Si fecha de corte >= fecha fin: teorico = importe presupuestado
Si fecha de corte esta dentro del periodo:
teorico = importe presupuestado * dias transcurridos / dias totales
```

El calculo incluye tanto el dia de inicio como el dia de corte.

## Calculo del alcanzado

El alcanzado se calcula buscando lineas en `account.analytic.line`:

- Fecha mayor o igual que el inicio de la linea presupuestaria.
- Fecha menor o igual que la fecha de corte.
- Misma compania o sin compania.
- Cuenta analitica relacionada con la linea del presupuesto.

Si la linea analitica esta vinculada a un apunte contable, solo se tiene en cuenta si el asiento esta publicado cuando el campo de estado existe.

El importe alcanzado se obtiene sumando el campo `amount`.

## Deteccion de lineas de presupuesto

El modulo intenta ser compatible con distintas estructuras de presupuesto analitico.

Busca lineas en campos habituales como:

- `budget_line_ids`
- `line_ids`
- `budget_analytic_line_ids`
- `analytic_budget_line_ids`
- `crossovered_budget_line_ids`

Si no encuentra esos campos, busca un One2many que contenga campos de importe compatibles.

## Deteccion de importe presupuestado

El modulo contempla varios nombres de campo posibles:

- `budget_amount`
- `budgeted_amount`
- `planned_amount`
- `amount`
- `planned_amount_currency`

Esto permite adaptarse mejor a variaciones de Odoo o de modulos instalados.

## Deteccion de cuenta analitica y proyecto

Para cada linea del presupuesto, el modulo busca campos Many2one o Many2many hacia `account.analytic.account`.

Con la cuenta analitica principal intenta localizar un proyecto relacionado si existe un campo Many2one hacia cuenta analitica en `project.project`.

## Uso funcional

1. Entrar en Contabilidad.
2. Abrir un presupuesto analitico.
3. Pulsar `Calcular WIP`.
4. Indicar la fecha de calculo en el asistente.
5. Confirmar el calculo.
6. Revisar el snapshot generado.
7. Revisar las lineas, teorico, alcanzado y WIP.
8. Si el usuario tiene permisos de jefe de proyecto, puede ajustar importes antes de contabilizar con el modulo contable.

## Menus y botones

En el presupuesto analitico:

- Boton `Calcular WIP`.
- Boton `Calculos WIP`.

En Contabilidad:

- Menu `Calculos WIP` bajo transacciones contables.

## Ajuste manual

Los importes ajustables por linea son:

- Teorico validado.
- WIP a contabilizar.
- Motivo del ajuste.

Cuando se cambia el teorico validado, el WIP se recalcula como:

```text
WIP a contabilizar = Teorico validado - Alcanzado
```

Solo pueden modificar lineas los usuarios con grupo de jefe de proyecto o superusuario.

No se permite modificar un calculo cancelado ni un calculo que ya tiene asiento contable creado por el modulo de contabilizacion.

## Permisos

Se definen permisos para:

- Usuarios contables.
- Jefes de proyecto.

Los usuarios contables pueden consultar calculos y lanzar el asistente.

Los jefes de proyecto pueden editar lineas de calculo para validar o ajustar el WIP antes de contabilizar.

## Tests

El modulo incluye pruebas basicas para:

- Prorrateo del teorico.
- Recalculo del WIP cuando se ajusta el teorico.

## Archivos relevantes

- `models/budget_analytic.py`: logica de calculo sobre presupuestos.
- `models/wip_calculation.py`: modelos de snapshot y lineas WIP.
- `wizard/wip_calculate_wizard.py`: asistente de fecha de calculo.
- `views/budget_analytic_views.xml`: botones en presupuesto analitico.
- `views/wip_calculation_views.xml`: vistas y menu de calculos WIP.
- `security/ir.model.access.csv`: permisos.
- `tests/test_wip_formula.py`: pruebas de formula.
