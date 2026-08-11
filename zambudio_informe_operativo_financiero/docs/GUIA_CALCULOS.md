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

Se encuentra en **Proyecto > Informes > Informe operativo financiero** y
**Proyecto > Informes > Apuntes informe operativo financiero**.

---

## 2. Conceptos (filas) y su orden

La "Vista horizontal" se muestra agrupada por secciones (Ingresos / Costes / PM /
WIP), como el cuadro de referencia. Los conceptos con dato contable son:

| Seccion  | Concepto            | Que mide                                                                     |
|----------|---------------------|------------------------------------------------------------------------------|
| Ingresos | Venta de servicios  | Ingreso reconocido (asientos WIP) en cuentas **705**, SIN facturas.          |
| Ingresos | Venta de productos  | Ingreso reconocido en el resto del grupo **70** (700...), SIN facturas.      |
| Ingresos | *Total ingresos*    | Servicios + Productos = ingreso reconocido via asientos WIP.                 |
| WIP      | Facturacion         | Facturas de cliente en cuentas del grupo **70** (aparte, no entra en Ingresos). |
| WIP      | WIP                 | Ingreso reconocido acumulado - facturacion acumulada.                        |

Las filas de **Costes** salen de las mismas fuentes que el panel de **Rentabilidad**
del proyecto, y **PM** se calcula a partir de Ingresos y Costes. Desde `19.0.22.0.0` el
bloque de Costes se **reagrupa por TIPOLOGIA** (regla de Laura: la forma de calcular NO
cambia, solo se reagrupa el coste de pedidos por Tipo de pedido). Ya **no** existe la
fila generica "Pedidos" con sub-filas por tipo: cada tipologia es su propia fila:

- **Horas internas / externas**: coste de los **partes de horas** del proyecto, separados
  por el plan analitico "Horas internas"/"Horas externas" (lo asigna una automatizacion
  segun el Tipo empleado). **No cambia** (`_amount_timesheet_cost`).
- **Contratas (Fix price)**: coste de pedidos de compra de tipo **SERVICIOS** y
  **SUBCONTRATA (Fix price)**.
- **Contratas (Por administración)**: pedidos de tipo **SUBCONTRATA (T&M)**.
- **Materiales**: pedidos de tipo **DOCUMENTACION, EPI, HARDWARE, HERRAMIENTA, MATERIAL**
  **+** el material de almacen (antigua fila "Stock interno", `_amount_materials`:
  apuntes analiticos `timesheet_invoice_type = other_costs`, sin duplicar valoracion).
- **Gastos de Viaje**: pedidos de tipo **GASTOS DE VIAJE** **+** gastos `hr.expense` de
  categoria **Kilometraje** y **Dietas** (`_amount_travel_expenses`; el resto de gastos
  queda FUERA del informe).
- **Licencias software**: pedidos de tipo **SOFTWARE (Licencias)**.
- **Otros costes**: pedidos de tipo **OTROS**, mas cualquier pedido con tipo no mapeado
  o **sin tipo** (catch-all, para no perder coste). El tipo **FLOTA VEHICULOS** queda
  EXCLUIDO (no se cuenta; no imputa a proyecto).

El coste de pedidos se calcula igual que antes (`_purchase_order_costs_by_type`, sin
tocar) y se reagrupa por el NOMBRE del `aunna.purchase.order.type` segun el mapeo
`PURCHASE_TYPE_TYPOLOGY` (comparacion en MAYUSCULAS y sin espacios sobrantes) mediante
el helper `_purchase_costs_by_typology`. Todos los costes van en negativo y ponderados
por el % de distribucion analitica (salvo las Horas, importe integro).

Las filas de dato editable/almacenado las define `METRICS` en
[models/aunna_wip_annual_report.py](../models/aunna_wip_annual_report.py):

```python
METRICS = [
    ("services_income", "Venta de servicios", 10),
    ("products_income", "Venta de productos", 20),
    ("internal_hours", "Horas internas", 30),
    ("external_hours", "Horas externas (SCR)", 40),
    ("contratas_fix", "Contratas (Fix price)", 50),
    ("contratas_admin", "Contratas (Por administración)", 60),
    ("materiales", "Materiales", 70),
    ("gastos_viaje", "Gastos de Viaje", 80),
    ("licencias_software", "Licencias software", 90),
    ("otros", "Otros costes", 100),
    ("invoice", "Facturacion", 110),
    ("real_wip", "WIP", 120),
]
```

El mapeo NOMBRE de `aunna.purchase.order.type` -> tipologia vive en la constante
`PURCHASE_TYPE_TYPOLOGY` del mismo archivo.

La estructura visual agrupada se define en la constante `REPORT_GROUPS` del mismo
archivo.

> **Notas historicas:** en `19.0.7.0.0` se retiro la fila **ER/OE** (pedidos de venta).
> En `19.0.8.0.0` se reformo el bloque de ingresos: se separo Venta de servicios /
> Venta de productos y se retiro **Ingreso reconocido** (queda dentro de Venta de
> servicios, ya que 705001 es una cuenta 705). Cada cambio tiene su migracion en
> [migrations/](../migrations/).

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

Todos los filtros comunes de apuntes (`account.move.line`) son: asiento
**publicado** (`parent_state = posted`), de la **compania** del informe, `date`
dentro del mes, con `analytic_distribution` informada y excluyendo lineas de
seccion/nota. El importe se toma como `credito - debito` (`-balance`) y se reparte
por el **ratio analitico** (ver seccion 6).

### 4.1 Venta de servicios / Venta de productos

Metodo: `_amount_income_by_code(analytic, desde, hasta, codigo)`.

Los Ingresos se toman de los **asientos WIP (ingreso reconocido)** y **excluyen las
facturas/abonos de cliente** (`move_type not in (out_invoice, out_refund)`, ver
`_non_customer_invoice_domain`). Asi una factura no infla "Venta de productos".

- **Venta de servicios** (`"705%"`): apuntes en cuentas cuyo codigo empieza por
  **705** (p. ej. `705001` ingreso reconocido del WIP), en asientos que **no** son
  factura de cliente.
- **Venta de productos**: `Total ingresos - Venta de servicios`, donde
  **Total ingresos** = apuntes del grupo **70** completo (`"70%"`) sin facturas. Es
  decir, el resto del grupo 70 (700...) reconocido via asiento WIP.
- **Total ingresos** = ingreso reconocido del grupo 70 (sin facturas de cliente). La
  fila **"Ingreso"** del P&L incluye ademas las facturas, por lo que ya **no tiene por
  que coincidir**; lo facturado se ve en la fila **Facturacion**.

### 4.2 Facturacion

Metodo: `_amount_invoices`.

- **Facturas y abonos de cliente** (`move_type` en `out_invoice`, `out_refund`) en
  cuentas del **grupo 70** (`"70%"` = 700 y 705.0), imputados a la analitica.
- Importe: `sum( (credito - debito) x ratio_analitico )`.

Es cuanto se ha **facturado** del proyecto en el mes.

### 4.3 WIP

Metodo: dentro de `_collect_period_real_values` / `_collect_real_values`.

- Formula mensual (definicion del negocio):
  `WIP_mes = WIP_mes_anterior + Total ingresos_mes - Facturacion_mes`, donde
  `Total ingresos` es el **ingreso reconocido** del mes (asientos WIP, sin facturas) y
  `Facturacion` son las facturas de cliente del mes.
- Es un **acumulado** de `ingreso reconocido - facturacion`. El ingreso reconocido se lee
  en **bruto** (no descuenta la factura), asi que al facturar el WIP **baja**; queda a 0
  cuando lo facturado alcanza lo reconocido, y **negativo** si se factura de mas.
- **Saldo inicial**: el primer mes visible arrastra lo anterior al rango, con
  `_amount_income_by_code_before(..., "70%") - _amount_invoices_before(...)`.
- En el **Total** de la matriz horizontal, el WIP muestra el valor del **ultimo mes**
  (no la suma), por ser un acumulado.

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

1. Ir a **Proyecto > Informes > Informe operativo financiero** y crear un informe:
   ejercicio, rango, compania y proyecto o cuenta analitica.
2. (Opcional) Escribir los importes **Prev.** en `Detalle mensual`.
3. Pulsar **Recalcular reales** para traer la contabilidad publicada.
4. Revisar en `Detalle mensual`, en la `Vista horizontal` o en la lista `Apuntes informe
   operativo financiero` (filtrable y agrupable por mes, concepto, proyecto, cuenta
   analitica o compania).
5. (Opcional) **Exportar Excel**.

---

## 11. Resumen de acciones (botones)

| Boton                        | Metodo                             | Que hace                                        |
|------------------------------|------------------------------------|-------------------------------------------------|
| Recalcular reales            | `action_recalculate_real_values`   | Recalcula la columna Real desde la contabilidad.|
| Ver detalle mensual          | `action_open_period_lines`         | Abre la lista de lineas mensuales del informe.  |
| Actualizar vista horizontal  | `action_refresh_horizontal_summary`| Regenera la matriz HTML.                        |
| Exportar Excel               | `action_export_horizontal_xlsx`    | Descarga la matriz en `.xlsx`.                  |
