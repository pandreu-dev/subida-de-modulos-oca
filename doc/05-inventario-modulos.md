# 05 · Inventario de módulos y plan de re-despliegue

> Estado a **2026-07-22**, tras la restauración de PRO al 20/07 07:04.
> La verdad exacta de "qué hay instalado" se saca con la consulta SQL de
> [02-operativa-comandos.md](02-operativa-comandos.md) o inspeccionando un backup (04).

## ✅ Ya en PRO (estaban antes del 20/07 → sobrevivieron a la restauración)

| Módulo | Qué hace |
|--------|----------|
| `aunna_product_labels` | Formatos de etiqueta en el asistente de productos |
| `aunna_pyg_hide_total_analytic` | Oculta la columna "Total" en el informe de P&L |
| `aunna_stock_move_product_category_column` | Categoría del producto en líneas de albarán |
| `aunna_stock_negative_control` | Bloquea stock negativo (producto/categoría/ubicación/almacén) |
| `aunna_stock_picking_departments` | Departamentos (BR) en albaranes y pedidos de compra |
| `instalador_modulos_github_v19` | Clona e instala módulos OCA desde una URL de GitHub |
| `project_delivery_analytic_valuation` | Lleva el coste de material de albarán al panel del proyecto |

## 🔄 A RE-ACTUALIZAR en PRO (estaban instalados en versión vieja → `-u`)

| Módulo | Qué hace |
|--------|----------|
| `aunna_wip_accounting` | Crea y revierte los asientos contables del WIP |
| `aunna_wip_budget_calc` | Calcula teórico, facturado/alcanzado y WIP a una fecha |
| `aunna_purchase_order_type` | Añade "Tipo de pedido" en solicitudes y pedidos de compra |
| `aunna_public_holiday_timesheet_bridge` | Partes de horas automáticos desde festivos (ver 08: lentitud) |

## ⬆️ A INSTALAR en PRO (nuevos, se perdieron con la restauración)

| Módulo | Qué hace | Nota |
|--------|----------|------|
| `aunna_wip_project_link_fix` | Evita que los apuntes de ingreso WIP cuenten como partes de horas | |
| `zambudio_informe_operativo_financiero` | Informe operativo financiero por proyecto (previsión vs real, Excel) | Coste de pedidos por recepción validado por Manuel |
| `zambudio_timesheet_approval_by_project` | Validación de partes solo por jefe de proyecto / aprobador | |
| `zambudio_project_type` | Campo Tipo de proyecto (Cerrado / Tiempo & Materiales / Recurrente) | |
| `zambudio_project_unique_name` | Impide nombres de proyecto duplicados | **v19.0.1.1.0** (deja pasar plantillas) |
| `zambudio_project_sale_naming` | Proyecto + cuenta analítica = "nº pedido - descripción de la línea" | **v19.0.2.1.0** (arreglado) |
| `zambudio_product_company_from_user` | Producto en la compañía del usuario mono-compañía | Requiere OK de Laura + Tomás |
| `zambudio_wip_hide_timesheets` | Oculta apuntes WIP de las listas de partes | **Opcional** (red de seguridad tras link_fix) |

## ❌ NO instalar (decisiones tomadas)

| Módulo | Motivo |
|--------|--------|
| `zambudio_project_billable` | Laura pidió **revertir el "facturable por defecto"**. En **v19.0.1.4.0** ya no lo fuerza (solo sincroniza + cliente obligatorio si es facturable). Con plantillas, el proyecto ya hereda el cliente del pedido. |
| `aunna_project_cost_account_moves` (COSTE TH) | Manuel: **prescindible**. El coste de horas del informe sale del propio parte (horas × coste/hora), no de estos asientos. Instalarlo **duplicaría** el coste. |
| `aunna_dynamic_standard_cost` | **Descatalogado** (carpeta `DESCATALOGADO_...`, manifest renombrado). Valora inventario a último precio de compra; pendiente de decisión de administración. |

## ⚠️ Antes de instalar #6 y #7 (sale_naming, unique_name)
Fueron **arreglados en local el 21-22/07**; el servidor aún tiene la versión vieja.
**Subir el código nuevo** (git push local → git pull servidor) y **Actualizar lista de
aplicaciones** antes de instalarlos. Ver [03](03-despliegue-y-actualizacion.md).

## Configuración que NO viaja con el código (rehacer aparte)
- Cuentas analíticas **"Horas internas" / "Horas externas"** (nombre exacto, por compañía).
- Empleados: **Coste por hora** + **Tipo empleado**.
- **Automatizaciones de Studio** (asignan Horas internas/externas por tipo de empleado),
  incluida la corrección multicompañía de CITRIC (ver 07).
- **Tipos de pedido de compra**.
- Cuentas WIP (diario, ingreso 705, diferido) y el **`ir.config_parameter` del diario WIP**.
> A 22/07 Pablo ya rehizo las **horas** y las **automatizaciones**. Verificar el resto.
