# Correccion de alcanzado en presupuestos de ingreso

## Metodo afectado

`budget.analytic._aunna_wip_get_achieved_amount`

Archivo:

`models/budget_analytic.py`

## Problema

El calculo de `Alcanzado` usaba siempre `account.analytic.line`.

Para presupuestos de ingreso esto podia dejar fuera facturas de cliente publicadas con `analytic_distribution` en la linea contable de ingreso, porque la fuente real del ingreso es `account.move.line`.

## Dominio anterior

Fuente:

`account.analytic.line`

Criterios principales:

- fecha,
- compania,
- campos analiticos detectados en la linea analitica,
- exclusion de WIP.

## Dominio corregido para ingresos

Fuente:

`account.move.line`

Criterios:

- `parent_state = posted` o `move_id.state = posted`,
- fecha dentro del periodo,
- compania correcta,
- cuenta de ingreso 7xx o cuenta configurada en la linea de presupuesto,
- `analytic_distribution` contiene las dimensiones definidas en presupuesto.

## Cruce de dimensiones

Solo se exigen dimensiones con valor en el presupuesto o linea presupuestaria.

Si el presupuesto solo define Proyecto, una factura con Proyecto 100% y P&L/Departamento/Division vacios no queda excluida.

## Signo

En facturas de cliente, la linea de ingreso suele tener `balance` negativo. Para mostrar el alcanzado de ingresos en positivo se usa:

```text
alcanzado = -balance
```

Si no existe `balance`, se usa:

```text
alcanzado = credit - debit
```

## Ejemplo esperado

Una factura de cliente publicada con linea 700000 y distribucion analitica al proyecto `S00032 - NOKIA SPAIN` debe entrar en el `Alcanzado/Real` del presupuesto de ingresos si:

- la fecha esta dentro del periodo,
- la compania coincide,
- el presupuesto es de ingreso,
- la cuenta contable es de ingreso.
