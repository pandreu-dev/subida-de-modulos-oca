# Especificación de cálculo — Tipologías de coste del Informe Operativo Financiero

> **Para qué es este documento.** Definir, tipología por tipología, **cómo se debe calcular cada coste** del informe operativo, con nombres de modelos y campos de Odoo reales, para poder **implementarlo (Verónica + IA)**.
> **Módulo:** `zambudio_informe_operativo_financiero` · **Modelo:** `aunna.wip.annual.report` · **Fichero:** `models/aunna_wip_annual_report.py`.
> **Estado:** propuesta funcional. Todo cambio se prueba **primero en PRE** (`grupo_zambudio_prod_pruebas`) antes de PRO.
> ⚠️ Hay **decisiones abiertas** marcadas como **[DECIDIR]** que deben cerrarse con Verónica/negocio antes de programar. No implementar esas partes "a ojo".

---

## 0. Las 6 tipologías (resumen)

| # | Tipología | Fuente principal | Fecha de imputación |
|---|-----------|------------------|---------------------|
| 1 | **Horas internas** | Partes de horas (`account.analytic.line`) | Fecha del parte |
| 2 | **Horas externas** | Partes de horas (`account.analytic.line`) | Fecha del parte |
| 3 | **Contratas (Fix price)** | Pedidos de compra tipo *Contrata fix price* | Recepción / confirmación (ver [DECIDIR-A]) |
| 4 | **Contratas (Por administración)** | Pedidos de compra tipo *Contrata por administración* | Recepción / confirmación (ver [DECIDIR-A]) |
| 5 | **Materiales** | Pedidos recepcionados (resto de tipos) + material de almacén | Fecha de recepción de cada albarán |
| 6 | **Gastos de Viaje** | Pedidos tipo *Gastos de viaje* + gastos (`hr.expense`) Dietas/Kilometraje | Recepción / fecha del gasto |

> **Cambio estructural.** Hoy el bloque de Costes es: `Horas internas`, `Horas externas`, `Pedidos` (total, desglosado por Tipo de pedido), `Stock interno` (materiales de albarán) y `Gastos`. **Se sustituye** por las 6 tipologías de arriba: la fila genérica *Pedidos* desaparece y su contenido se reparte entre **Contratas Fix / Contratas Admin / Materiales / Gastos de Viaje** según el tipo de pedido.

---

## 1. Reglas comunes a TODAS las tipologías

Aplican a las 6 salvo que se diga lo contrario:

1. **Ámbito:** el informe se calcula para **una cuenta analítica** (la del proyecto) y **una compañía** (`company_id` del informe), **mes a mes**.
2. **Signo:** los costes se guardan **en negativo** (un coste de 1.000 € = `-1000`).
3. **Ratio analítico (reparto):** un apunte puede estar repartido entre varias cuentas analíticas (`analytic_distribution = {cuenta: %}`). Solo cuenta **el % que corresponde a la cuenta del informe**. Ej.: apunte de 1.000 € con `{proyecto: 60, otra: 40}` → cuenta **600 €**. Método existente: `_analytic_distribution_ratio`.
   - **Excepción:** solo las **Horas** se toman por su **importe íntegro** (el parte ya está imputado al proyecto). Los **pedidos de compra** y los **gastos (`hr.expense`) sí** se ponderan por su distribución analítica (un gasto puede repartirse entre varios proyectos).
4. **Solo dato consolidado**, cada fuente en su estado definitivo: **facturas e ingresos/WIP** → solo apuntes contables **publicados**; **partes de horas** → solo **validados** (los partes **no** generan apuntes contables —el módulo COSTE TH no está instalado—: el coste sale del propio parte); **pedidos de compra** → solo **confirmados**; **gastos** → solo aprobados/pagados.

---

## 2. [DECISIÓN CLAVE] Cómo se identifica el tipo de pedido → tipología

Las tipologías 3-6 dependen de saber, para cada pedido de compra, **a qué tipología pertenece**. Hoy el informe agrupa por `order.aunna_purchase_order_type_id` (modelo `aunna.purchase.order.type`) de forma **genérica** (una sub-fila por cada tipo, sin saber si es contrata, material o viaje).

**Recomendación (limpia y a prueba de Community):** añadir en el modelo **`aunna.purchase.order.type`** un campo de clasificación, p. ej.:

```
tipologia_coste = selection([
    ('contrata_fix',   'Contrata (Fix price)'),
    ('contrata_admin', 'Contrata (Por administración)'),
    ('gastos_viaje',   'Gastos de viaje'),
    ('materiales',     'Materiales / otros'),
])
```

Así el informe mapea cada pedido con `order.aunna_purchase_order_type_id.tipologia_coste` en vez de comparar por nombre (frágil). **[DECIDIR]** confirmar este enfoque y **rellenar el campo** en cada tipo de pedido existente + en los **dos nuevos** (`Contrata (Fix price)` y `Contrata (Por administración)`) que salen de desdoblar el tipo *Servicios*.

---

## 3. Definición de cada tipología

### 3.1 Horas internas
- **Qué es:** coste de las horas de **empleados internos** imputadas al proyecto (coste SCR = coste/hora del empleado).
- **Fuente:** `account.analytic.line` con `project_id` = proyecto del informe, `date` dentro del mes, **parte validado** (`validated`).
- **Clasificación interna/externa:** en Odoo 19 un parte de horas puede llevar **varias cuentas analíticas a la vez, una por cada plan analítico** (plan Proyecto, plan P&L, plan Departamento…). La etiqueta **"Horas internas"** no va en la cuenta del proyecto, sino en el **plan de P&L**; por eso el cálculo la busca entre esos planes, no solo en la principal. La pone **una automatización** ("Horas internas Apuntes analíticos") según el **Tipo de empleado = Interno**.
- **Importe:** suma de `line.amount` (ya es coste en negativo: horas × coste/hora). **No** se pondera por ratio.
- **Método actual:** `_amount_timesheet_cost(inicio, fin, "Horas internas")`.
- **Cambio pedido:** *"se calcula como ahora"* — sin cambios en el cálculo de Horas internas (ya confirmado: la automatización clasifica bien y el coste sale del parte).

### 3.2 Horas externas
- **Qué es:** coste de horas de **empleados de otra compañía del grupo** (subcontratas) imputadas al proyecto.
- **Fuente y cálculo:** idéntico a Horas internas, pero la cuenta de plan es **"Horas externas"**. Método: `_amount_timesheet_cost(inicio, fin, "Horas externas")`.
- **Clasificación:** la automatización **"Horas externas Apuntes analíticos"** (modelo `account.analytic.line`, al guardar) asigna esa cuenta cuando: `Proyecto` definido **y** `Tipo empleado = Externo` **y** `Subtipo empleado = Subco GZ`.
- **Cambio pedido (YA HECHO en la automatización):** solo cuentan como Horas externas las de **Subcos GZ**. El coste de subcontratas externas que **no** son del grupo **no se contabiliza aquí**.
- ⚠️ **[VERIFICAR]** Los externos que **no** son Subco GZ dejan de recibir la cuenta "Horas externas" y, al ser `Tipo = Externo`, **tampoco** los coge la automatización de internas → quedan **fuera de las dos** (es lo deseado). Confirmar que ninguna otra regla los reclasifica.
- **El informe NO cambia** para esta tipología: el cambio vive en la automatización, no en el código del informe.

### 3.3 Contratas (Fix price)
- **Qué es:** servicios de terceros a **precio fijo** (pedidos de servicio *fix price*).
- **Fuente:** `purchase.order.line` de pedidos con `order_id.state in ('purchase','done')`, imputados a la analítica del informe, cuyo **tipo de pedido = Contrata (Fix price)** (ver §2).
- **Importe / fecha (hoy, servicios):** `price_subtotal` del pedido, imputado en la **fecha de confirmación** (`date_approve`, o `date_order`), ponderado por ratio, en negativo. Método actual: rama "servicios" de `_purchase_order_costs_by_type`.
- **[DECIDIR-A] "parte recepcionada":** el correo pide *"parte recepcionada de los pedidos de la categoría Contrata (fix price)"*. Un servicio no genera albarán, pero la línea de pedido tiene **`qty_received`**. Hay que decidir:
  - **(a)** mantener el criterio actual (subtotal en la confirmación), o
  - **(b)** imputar **`qty_received` × precio unitario** (lo realmente "recepcionado"), en la fecha en que se marca la recepción.
  Para *Fix price* suele valer (a); para *Por administración* encaja mejor (b). **Cerrar con Verónica.**

### 3.4 Contratas (Por administración)
- **Qué es:** servicios de terceros contratados **por administración** (se paga según avance/horas).
- **Fuente y cálculo:** idéntico a 3.3 pero **tipo de pedido = Contrata (Por administración)**.
- **[DECIDIR-A]** igual que arriba; aquí es donde más sentido tiene el criterio **(b) por `qty_received`**.

### 3.5 Materiales
- **Qué es:** coste de materiales, tanto los **comprados directamente con cargo al proyecto** como los que se **trasladan desde el almacén**.
- **Definición pedida:** *"parte recepcionada de los pedidos recepcionados en el proyecto de cualquier categoría EXCEPTO contratas y gastos de viaje"*.
- **Fuentes (son DOS, y hay que reconciliarlas):**
  1. **Compra directa (bienes):** rama "bienes" de `_purchase_order_costs_by_type` para tipos de pedido **distintos de** contrata_fix, contrata_admin y gastos_viaje → se imputa **lo recibido en cada albarán** (`stock.move` en estado `done`, `picking_type_code = 'incoming'`), **cantidad recibida × precio unitario del pedido**, en la **fecha de la recepción**; las devoluciones (`outgoing`) restan.
  2. **Material trasladado desde almacén:** hoy lo captura `_amount_materials` = `account.analytic.line` con `timesheet_invoice_type = 'other_costs'`, `amount < 0`, `category != 'vendor_bill'` y **sin** `move_line_id` (para no duplicar valoración de stock).
- **[DECIDIR-B] Reconciliar fuentes / evitar doble conteo.** Un mismo pedido de material que genera albarán puede aparecer en (1) **y** en (2). Hay que decidir la fórmula final de Materiales:
  - Opción A: Materiales = **solo (1)** (pedidos recepcionados de tipos "material") — encaja literal con la frase del correo.
  - Opción B: Materiales = **(1) compra directa + (2) traslados de almacén** — encaja con *"tanto los que se compran… como los que se trasladan desde el almacén"*, pero exige un criterio para **no contar dos veces** el mismo material.
  **Cerrar con Verónica** cuál es la fuente de verdad de "material trasladado desde almacén".

### 3.6 Gastos de Viaje
- **Qué es:** gastos de pedidos de la categoría **"Gastos de viaje"** (alojamientos, transporte con cargo al proyecto) **+** gastos del **módulo Gastos** (`hr.expense`) de categorías **Dietas** y **Kilometraje**.
- **Fuente 1 — pedidos:** rama de `_purchase_order_costs_by_type` para el **tipo de pedido = Gastos de viaje** (parte recepcionada, igual criterio [DECIDIR-A]).
- **Fuente 2 — gastos de empleado:** `hr.expense` en estado `('posted','in_payment','paid')`, imputados a la analítica del informe, **filtrando por categoría** (producto del gasto) **= Kilometraje o Dietas**. Importe íntegro, en negativo, `date` del gasto. Método base actual: `_amount_expenses` (hoy suma **todos** los gastos sin filtrar categoría).
- **Cambios respecto a hoy:**
  1. El módulo `zambudio_informe_operativo_financiero` **no depende de `hr_expense`** en su manifest → **añadir la dependencia** (`hr_expense`) para leer los gastos.
  2. Filtrar `hr.expense` por **categoría Kilometraje/Dietas** (hoy no filtra).
- **[DECIDIR-C]** Nombres/identificadores exactos de las categorías de gasto **"Kilometraje"** y **"Dietas"** (son productos `product.product`/categoría de gasto — pasar el nombre o `id` real). Y **[DECIDIR]** qué pasa con los gastos `hr.expense` que **no** son Kilometraje/Dietas: ¿se excluyen del informe? (en el nuevo esquema no hay fila genérica "Gastos").

---

## 4. Resumen de DECISIONES a cerrar (checklist para la reunión)

| Ref | Decisión | Quién |
|-----|----------|-------|
| §2 | ¿Añadimos campo `tipologia_coste` a `aunna.purchase.order.type` y lo rellenamos? Crear los 2 tipos nuevos de Contrata | Verónica + negocio |
| [DECIDIR-A] | "Parte recepcionada" en servicios (Contratas/Viaje): ¿subtotal en confirmación o `qty_received` × precio? | Verónica |
| [DECIDIR-B] | Materiales: ¿solo compra directa recibida, o también material de almacén? ¿Cómo se evita doble conteo? | Verónica |
| [DECIDIR-C] | Nombres/ids exactos de categorías de gasto **Kilometraje** y **Dietas**; qué pasa con el resto de gastos | Verónica |

---

## 5. ⚠️ Impacto si os vais a Odoo Community

La clasificación **Horas internas/externas** la hace hoy una **automatización creada con Studio** (Enterprise). En **Community, Studio no existe** y no se puede editar. Esas reglas (`base.automation`) hay que **rehacerlas** como reglas de automatización nativas (`base_automation`, que sí está en Community) o en **código del módulo**. Es la pieza más crítica de las horas: tenerlo en cuenta antes de migrar.

---

## 6. Dónde vive cada cosa (guía rápida para implementar)

| Tipología | Método actual a tocar | Modelo/fuente |
|-----------|-----------------------|---------------|
| Horas internas/externas | `_amount_timesheet_cost` (+ automatización) | `account.analytic.line` |
| Contratas Fix / Admin | `_purchase_order_costs_by_type` (rama servicios) + mapeo §2 | `purchase.order.line` |
| Materiales | `_purchase_order_costs_by_type` (rama bienes) + `_amount_materials` | `purchase.order.line` + `account.analytic.line` |
| Gastos de Viaje | `_purchase_order_costs_by_type` (tipo viaje) + `_amount_expenses` (filtrado) | `purchase.order.line` + `hr.expense` |
| Estructura de filas | `METRICS` + `REPORT_GROUPS` | (constantes del módulo) |
