# 06 · WIP / Informe operativo financiero / P&L analítico

## Módulos implicados
```
aunna_wip_accounting            -> asientos WIP (ingreso reconocido, cuenta 705), con reversión
aunna_wip_budget_calc           -> teórico / facturado(alcanzado) / diferencia WIP a una fecha
aunna_wip_project_link_fix      -> normaliza apuntes de ingreso WIP; evita que cuenten como partes
zambudio_wip_hide_timesheets    -> oculta apuntes WIP de las listas de partes de horas
zambudio_informe_operativo_financiero -> informe por proyecto (previsión vs real, horizontal + Excel)
project_delivery_analytic_valuation   -> coste de material de albarán al panel del proyecto
aunna_project_cost_account_moves      -> asientos técnicos "COSTE TH" (SE DEJA SIN INSTALAR)
```

## Objetivos del WIP
- Calcular **ingreso reconocido**, **facturado/alcanzado** y **diferencia WIP**.
- El **P&L** se basa en apuntes contables: por eso los partes de horas generan **apunte
  analítico** pero no aparecen directamente en el P&L.

## Terminología del informe (renombrada)
- "Ingresos" → **"Avance"**; "Total ingresos" → "Total avance".
- "Materiales" → **"Stock interno"**.
- Etiquetas de presupuesto: Teórico→**Avance teórico**, Alcanzado→**Facturado**,
  "WIP a contabilizar"→"Avance reconocido total", etc.
- ⚠️ Se conservó el marcador **"WIP"** en el **diario contable** y en las exclusiones de
  búsqueda (`name/ref not ilike 'WIP'`): **no renombrar** esos marcadores.

## Decisiones y lógica clave
- **Coste de horas del informe** = del **propio parte** (horas × coste/hora del empleado),
  **no** de los asientos COSTE TH. Por eso `aunna_project_cost_account_moves` se deja sin
  instalar (instalarlo duplicaría el coste en Apuntes analíticos).
- **Coste de pedidos por RECEPCIÓN de albarán** (bienes): cantidad recibida × precio del
  pedido, imputado en la **fecha de cada recepción**. Servicios: por **fecha de
  confirmación**. (Desarrollado en `zambudio_informe_operativo_financiero`, validado por
  Manuel.)
- **Ingresos diferidos**: el informe **excluye** los asientos de diferimiento
  (`deferred_original_move_ids`) para no contar de más.
- **Partes de horas**: solo se reflejan los **validados**.
- **Incidencia resuelta (link_fix, Opción B):** los apuntes de ingreso reconocido WIP
  llevaban `project_id` y se contaban como partes de horas (¡hasta como horas!). Solución:
  el módulo **retira el `project_id`** de esas líneas (y pone horas a 0, desmarca
  validado). El vínculo con el proyecto se mantiene por la **cuenta analítica**.

## Detalle técnico útil
- Reversión-acumulado: el ingreso reconocido acumulado se postea cada mes con una
  **reversión** al día 1 del mes siguiente → el incremento mensual del informe sale bien.
- `account.analytic.line.amount` de un parte = horas × coste/hora del empleado.
- El P&L "Horas internas/externas" va en el plan analítico **`x_plan3_id`** (ver 07).

## Casos concretos (referencia)
- Redondeo 55 € → correcto.
- Caso 484 € mostraba 400 € → pendiente de revisión.
- Proyecto de ejemplo: **S00032**. Coste/hora empleado de ejemplo: **55 €**.
