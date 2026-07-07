# Guia del Informe WIP anual/mensual

Modulo: `aunna_wip_annual_report`

Esta guia explica **que hace el informe**, **que representa cada fila**, **como se
calcula cada valor real** y **como esta montado el modulo por dentro**. Esta pensada
tanto para el usuario funcional como para quien tenga que mantener el codigo.

---

## 1. Contexto: que es este informe

El WIP (*Work In Progress*, obra/servicio en curso) mide el **ingreso que ya se ha
reconocido contablemente pero todavia no se ha facturado** (o al reves) para un
proyecto o una cuenta analitica.

Este modulo NO calcula ni contabiliza el WIP: eso lo hacen
`aunna_wip_budget_calc` (calculo) y `aunna_wip_accounting` (asientos). Aqui solo se
**lee la contabilidad ya publicada** y se presenta, mes a mes, una comparativa entre:

- lo **previsto** por el usuario (columna editable), y
- lo **real** segun los apuntes contables (columna calculada).

Se encuentra en **Contabilidad > Informes > Informe WIP mensual** y
**Contabilidad > Informes > Configuracion informes WIP**.

---

## 2. Conceptos (filas) y su orden

Cada mes tiene **3 conceptos**, en este orden fijo:

| Orden | Concepto            | Que mide                                                        |
|-------|---------------------|-----------------------------------------------------------------|
| 1     | Ingreso reconocido  | Ingreso imputado a la cuenta de ingreso WIP (p. ej. `705001`).  |
| 2     | Facturacion         | Ingreso facturado al cliente (facturas y abonos).               |
| 3     | WIP real acumulado  | Acumulado de `Ingreso reconocido - Facturacion`.                |

El orden lo define la constante `METRICS` en
[models/aunna_wip_annual_report.py](../models/aunna_wip_annual_report.py):

```python
METRICS = [
    ("recognized_income", "Ingreso reconocido", 10),
    ("invoice", "Facturacion", 20),
    ("real_wip", "WIP real acumulado", 30),
]
```

El numero (10/20/30) es la **secuencia**; determina el orden en todas las vistas y en
la matriz horizontal. Cambiar el orden aqui lo cambia en todo el modulo.

> **Nota historica:** antes existia una cuarta fila, **ER/OE** (pedidos de venta).
> Se retiro en la version `19.0.7.0.0`. La migracion
> [migrations/19.0.7.0.0/post-migration.py](../migrations/19.0.7.0.0/post-migration.py)
> borra esa fila de los informes ya creados y reordena los conceptos restantes.

---

## 3. Columnas: Prev., Real y Dif.

Para cada mes y cada concepto hay tres columnas:

- **Prev.** (Previsto): lo escribe el usuario a mano. Es su prevision/objetivo.
- **Real**: lo calcula el modulo desde la contabilidad publicada. Es de solo lectura.
- **Dif.** (Diferencia): `Real - Prev`. Se calcula automaticamente.

El boton **Recalcular reales** (`action_recalculate_real_values`) es el que actualiza
la columna **Real**. La columna **Prev.** nunca se toca por codigo.

---

## 4. Como se calcula cada valor REAL

Todo el calculo real parte de **una unica cuenta analitica** (la del informe) y de la
**compania** del informe. El importe de cada apunte se **reparte segun su distribucion
analitica**: si un apunte esta al 60% en la cuenta analitica del informe, solo se
cuenta el 60% de su importe (ver seccion 6).

Los importes de ingreso se toman como `credito - debito` (`-balance`), de modo que un
ingreso (credito) suma en positivo.

### 4.1 Ingreso reconocido

Metodo: `_amount_recognized_income`.

- Cuenta: la **cuenta de ingreso WIP** configurada en la compania
  (`res.company.aunnna_wip_income_account_id`, p. ej. `705001`). Si la compania no la
  tiene configurada, el Ingreso reconocido sale **0** y se avisa en *Notas de calculo*.
- Filtro de apuntes (`account.move.line`):
  - `account_id` = cuenta de ingreso WIP,
  - asiento **publicado** (`parent_state = posted`),
  - de la **compania** del informe,
  - `date` dentro del mes,
  - con `analytic_distribution` informada (imputa a alguna cuenta analitica),
  - excluyendo lineas de seccion/nota.
- Importe: `sum( (credito - debito) x ratio_analitico )` de esos apuntes.

En la practica, esto recoge los asientos WIP generados por `aunna_wip_accounting`
contra la cuenta `705001` (y cualquier otro apunte manual contra esa cuenta con
imputacion analitica).

### 4.2 Facturacion

Metodo: `_amount_invoices`.

- Origen: **facturas y abonos de cliente** (`account.move.move_type` en
  `out_invoice`, `out_refund`).
- Filtro de apuntes:
  - asiento **publicado**,
  - de la **compania** del informe,
  - `date` dentro del mes,
  - con `analytic_distribution` informada,
  - solo lineas de **ingreso**: cuenta de tipo `income` / `income_other` **o** cuyo
    codigo empieza por `7`,
  - excluyendo lineas de seccion/nota.
- Importe: `sum( (credito - debito) x ratio_analitico )`.

Es decir, cuanto se ha **facturado** de ese proyecto/cuenta analitica en el mes.

### 4.3 WIP real acumulado

Metodo: dentro de `_collect_period_real_values` / `_collect_real_values`.

- Formula mensual: `WIP_mes = WIP_mes_anterior + (Ingreso reconocido_mes - Facturacion_mes)`.
- Es un **acumulado**, no un valor mensual aislado.
- **Saldo inicial**: el primer mes visible del informe arrastra todo lo anterior al
  rango, calculado con `_amount_recognized_income_before` y `_amount_invoices_before`
  (mismos filtros, pero con `date <` el primer mes). Asi, si filtras de marzo a
  diciembre, el acumulado de marzo ya incluye enero y febrero y no se reinicia.
- En los **totales** de la matriz horizontal, el total del WIP acumulado es el valor
  del **ultimo mes** (no la suma de meses), porque ya es un acumulado
  (`_horizontal_metric_totals`).

---

## 5. Rango de fechas y meses visibles

- El informe tiene `Desde` (`date_from`) y `Hasta` (`date_to`). Al cambiar `year`, se
  ajustan automaticamente a 1-ene / 31-dic de ese ejercicio.
- Se recorren los meses del rango con `_iter_month_starts()` (del primer dia del mes de
  `date_from` al primer dia del mes de `date_to`).
- Al ampliar/cambiar el rango se **crean** las lineas mensuales que falten, pero **no se
  borran** las anteriores: asi se conservan los importes `Prev.` ya escritos aunque
  cambies temporalmente el periodo visible.
- La matriz horizontal y el Excel **ocultan los meses totalmente vacios** (sin prev, sin
  real, sin diferencia). Si todos estan vacios, se muestran todos.

---

## 6. El "ratio analitico": como se reparte un apunte

Metodo: `_analytic_distribution_ratio`.

La `analytic_distribution` de un apunte es un diccionario `{cuenta(s): porcentaje}`.
En Odoo 19 la clave puede ser una sola cuenta (`"41"`) o varias separadas por comas
(una por plan analitico, p. ej. `"41,7"`). El modulo:

1. Busca en cada clave si aparece el id de la cuenta analitica del informe.
2. Suma los porcentajes de las claves que la contienen.
3. Divide entre 100 para obtener el ratio (0.0 a 1.0).

El importe que cuenta el informe es `importe_del_apunte x ratio`. Ejemplo: un apunte de
1.000 con distribucion `{"41": 100}` y la cuenta analitica del informe = 41 -> cuenta
1.000. Si fuera `{"41": 30, "7": 70}` -> cuenta 300.

---

## 7. Modelos de datos (parte tecnica)

- `aunna.wip.annual.report`: el informe (ejercicio, rango, compania, proyecto/cuenta
  analitica, vista horizontal en HTML, notas de calculo).
- `aunna.wip.annual.report.period.line`: **el detalle mensual real** (un registro por
  mes y concepto). Es lo que se ve en `Detalle mensual`, en la lista `Informe WIP
  mensual`, en el pivote y lo que alimenta la matriz horizontal y el Excel. Tiene
  `prev_amount`, `real_amount`, `diff_amount` y flags para filtrar
  (`in_report_range`, `is_empty`, `has_prev_amount`, `has_real_amount`,
  `is_current_year`, `is_current_month`, trimestre, etc.).
- `aunna.wip.annual.report.line`: representacion interna con las 12 columnas de meses
  (ene..dic) del ejercicio del informe. No se muestra en ninguna vista; se mantiene por
  compatibilidad. El dato "oficial" que se ve es el de las lineas mensuales
  (`period_line_ids`).

`_ensure_metric_lines` y `_ensure_period_lines` garantizan que existan las filas
correctas: crean las que falten, **eliminan las de conceptos obsoletos** (p. ej. ER/OE)
y **resincronizan la secuencia** al orden de `METRICS`. Se ejecutan al crear/guardar el
informe y al recalcular, por lo que los informes se auto-corrigen solos.

---

## 8. Vista horizontal y Excel

- La **Vista horizontal** (`horizontal_summary_html`) es una matriz de solo lectura:
  conceptos en filas, meses en columnas (cada mes con Prev./Real/Dif.) y una columna de
  Total. La primera columna (Concepto) queda fija al hacer scroll horizontal.
- Se regenera al guardar el informe o una linea mensual. El boton **Actualizar vista
  horizontal** (`action_refresh_horizontal_summary`) fuerza la regeneracion.
- El boton **Exportar Excel** (`action_export_horizontal_xlsx`) descarga esa misma
  matriz en `.xlsx` (requiere la libreria `xlsxwriter`), con cabeceras, primera columna
  congelada, autofiltro y formato numerico.

---

## 9. Configuracion necesaria

1. **Cuenta de ingreso WIP** por compania (Configuracion WIP del modulo
   `aunna_wip_accounting`). Sin ella, el **Ingreso reconocido** y por tanto el **WIP
   acumulado** salen a 0.
2. **Cuenta analitica** del informe: se puede indicar directamente o a traves de un
   **proyecto** (el modulo localiza la cuenta analitica del proyecto, campo `account_id`
   en Odoo 19). Sin cuenta analitica, el informe no deja recalcular.

---

## 10. Flujo de uso

1. Ir a **Configuracion informes WIP** y crear un informe: ejercicio, rango, compania y
   proyecto o cuenta analitica.
2. (Opcional) Escribir los importes **Prev.** en `Detalle mensual`.
3. Pulsar **Recalcular reales** para traer la contabilidad publicada.
4. Revisar en `Detalle mensual`, en la `Vista horizontal` o en la lista `Informe WIP
   mensual` (filtrable y agrupable por mes, concepto, proyecto, cuenta analitica o
   compania).
5. (Opcional) **Exportar Excel**.

---

## 11. Resumen de acciones (botones)

| Boton                        | Metodo                             | Que hace                                        |
|------------------------------|------------------------------------|-------------------------------------------------|
| Recalcular reales            | `action_recalculate_real_values`   | Recalcula la columna Real desde la contabilidad.|
| Ver detalle mensual          | `action_open_period_lines`         | Abre la lista de lineas mensuales del informe.  |
| Actualizar vista horizontal  | `action_refresh_horizontal_summary`| Regenera la matriz HTML.                        |
| Exportar Excel               | `action_export_horizontal_xlsx`    | Descarga la matriz en `.xlsx`.                  |
