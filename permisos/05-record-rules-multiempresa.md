# Record rules y aislamiento multiempresa (AUNNA / CITRIC / MONTOYA / ii)

> Documento operativo del entregable `new/permisos`. Enfocado en **aislar las compañías dentro de una única base de datos** (`grupo_zambudio_prod`). Complementa a [[04-blindaje-datos-maestros]] (blindaje de UdM/producto Horas) y [[02-catalogo-de-roles]] (roles y mínimo privilegio). Todo cambio se prueba **primero en PRE** (`grupo_zambudio_prod_pruebas`, `erp-pre.zambudio.es`) y luego a PRO (`erp.zambudio.es`).
>
> Convención: los xmlids del núcleo Odoo que no he podido confirmar contra fuente van marcados **(verificar en PRE)**. Los **dominios** de record rule sí son estables entre versiones.

---

## 0. Resumen ejecutivo (lo que hay que grabarse)

1. Una sola BD, varias compañías. El aislamiento **NO** lo dan los permisos de app (grupos), lo dan las **record rules por compañía** + el campo **`company_ids` del usuario** + **`check_company=True`** en los campos relacionales.
2. El control más eficaz y más barato contra fugas cross-company es **no dar `company_ids` de más**: un usuario que solo opera en CITRIC no debe tener AUNNA en su lista de compañías permitidas. Ninguna record rule protege tanto como esto.
3. Datos maestros **globales** (UdM, moneda) no tienen compañía: solo se protegen con permisos ([[04-blindaje-datos-maestros]]). Datos maestros **contables** (diarios, cuentas, analíticas, secuencias) se separan por compañía **y** se blindan con permisos.
4. El incidente real de la **cuenta 90 de AUNNA colándose en CITRIC** vino de un `account.analytic.distribution.model` con `company_id = False`. Se blinda haciendo **todos los modelos de distribución conscientes de compañía** (90→AUNNA id 1, 271→CITRIC id 2) y reforzando `check_company=True`.
5. Mucha configuración (Studio, `base_automation`, modelos de distribución analítica) **no viaja con código**: hay que recrearla consciente de compañía en cada entorno y auditarla ([[07-auditoria-trazabilidad-hardening]]).

> ⚠️ **Cambios de Odoo 19 confirmados que afectan a este documento** (detalle de grupos/privilegios en [[02-catalogo-de-roles]]):
> - En `res.users` el m2m de grupos pasó de `groups_id` a **`group_ids`** (grupos directos), y existe **`all_group_ids`** (directos + heredados por `implied_ids`). En `res.groups` el inverso pasó de `users` a **`user_ids`**. El rename se propaga a `ir.actions.*`, `ir.ui.view` e `ir.ui.menu`.
> - Las **definiciones de grupo** usan ahora el modelo **`res.groups.privilege`** con **`privilege_id`** en `res.groups` (sustituye al `category_id` directo de v17/18; la categoría de módulo cuelga ahora del `privilege_id`). Esto **no** cambia la sintaxis de las record rules de este documento, pero sí la de cualquier grupo que definas.
> - En dominios de record rule que dependan del grupo del usuario, usa **`user.has_group('modulo.xmlid')`** (API estable entre versiones), nunca el m2m renombrado.

---

## 1. Modelo de datos multiempresa: los tres conceptos que NO hay que confundir

| Concepto | Campo / variable | Qué es | Se lee como |
|---|---|---|---|
| **Compañía activa** | `res.users.company_id` | La compañía "en la que trabajas ahora". **Una sola.** Default al crear registros. | `self.env.company` |
| **Compañías permitidas** | `res.users.company_ids` (m2m) | Todas las compañías a las que el usuario puede acceder. | — |
| **Compañías seleccionadas** | `allowed_company_ids` (contexto) | Subconjunto de `company_ids` **marcado en el selector** (arriba a la derecha). Puede ser 1 o varias a la vez. | `self.env.companies` |

Reglas mecánicas clave:

- `env.company` = **la primera** de `allowed_company_ids` (la activa). `env.companies` = **todas** las marcadas.
- `allowed_company_ids` viaja en el **contexto desde el navegador**. Si un usuario tiene AUNNA + CITRIC marcadas a la vez, **ve y puede tocar registros de ambas simultáneamente**, y los defaults (distribución analítica, diarios, cuentas) se resuelven contra la **activa** (`env.company`). **Esta es la raíz mecánica de la fuga de la cuenta 90**: un usuario con AUNNA activa creando un parte de CITRIC → el default sale de AUNNA.
- **Nunca** confíes en `env.company` para seguridad de escritura. Para seguridad se usa `company_ids` en las record rules (ver §3) y `check_company=True` (ver §6).

### Compañías del grupo (una sola BD)

| Compañía | id | Rol |
|---|---|---|
| AUNNA IT (Select Asterisco SL) | **1** | Principal |
| CITRIC NETWORKS SL | **2** | Secundaria |
| MONTOYA | (verificar en PRE) | Secundaria |
| ii | (verificar en PRE) | Secundaria |

> Confirma los ids de MONTOYA e ii en PRE antes de escribir cualquier dominio o modelo de distribución que los referencie: `SELECT id, name FROM res_company ORDER BY id;`

---

## 2. Cómo se evalúan `company_id` y `company_ids` DENTRO de una record rule

En el contexto de evaluación de un `ir.rule` (método `_eval_context`), Odoo 19 inyecta:

| Variable en el dominio | Valor | Tipo |
|---|---|---|
| `user` | el `res.users` actual (con `sudo`, contexto vacío) | recordset |
| `company_id` | `self.env.company.id` (la **activa**) | entero |
| `company_ids` | `self.env.companies.ids` (las **seleccionadas** = `allowed_company_ids`) | lista de enteros |

> ⚠️ Como `user` viene con **contexto vacío**, dentro del dominio de una regla `user.company_id` puede no coincidir con la compañía realmente activa en la sesión. Por eso el aislamiento multiempresa se hace **siempre con la variable `company_ids`** (que sí refleja el selector), **no** con `user.company_id` ni con `company_id` singular.

Patrón canónico multiempresa (usa `company_ids` **plural**):

```python
['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
```

Lectura: *"ve el registro si **no tiene compañía** (dato compartido) **o** si su compañía está entre las que el usuario tiene seleccionadas"*. El `('company_id','=',False)` es lo que permite que **productos y UdM compartidos** sean visibles desde cualquier compañía.

> ⚠️ Si usas grupos dentro de un dominio, hazlo con `user.has_group('modulo.xmlid')`, **no** con el m2m de grupos (renombrado a `group_ids` en v19). `has_group` es API estable.

---

## 3. Record rules multiempresa NATIVAS por app (inventario a auditar)

Todas las apps de negocio traen **una regla global** por modelo con el mismo dominio. Son **globales** (`global = True`, sin grupos), por lo que **se combinan con AND** con cualquier otra regla: refuerzan y **no se pueden saltar dando otro grupo**. (Recuerda la mecánica: las reglas **globales** se combinan entre sí y con el bloque de grupos mediante **AND**; las reglas **de grupo** se combinan entre ellas mediante **OR**.)

> ⚠️ Los xmlids de abajo **hay que confirmarlos en PRE** con la query de auditoría de esta sección: solo asumo estables los **dominios**, no los identificadores exactos. He marcado los que menos he podido confirmar, pero **verifica todos** antes de referenciarlos en código.

| Modelo | xmlid de la regla nativa | Dominio |
|---|---|---|
| `sale.order` | `sale.sale_order_comp_rule` (verificar en PRE) | `['|',('company_id','=',False),('company_id','in',company_ids)]` |
| `purchase.order` | `purchase.purchase_order_comp_rule` (verificar en PRE) | idéntico |
| `account.move` | `account.account_move_comp_rule` (verificar en PRE) | idéntico |
| `account.journal` | `account.journal_comp_rule` (verificar en PRE) | idéntico |
| `stock.picking` | `stock.stock_picking_rule` (verificar en PRE) | idéntico |
| `stock.warehouse` | `stock.stock_warehouse_comp_rule` (verificar en PRE) | idéntico |
| `project.project` | `project.project_comp_rule` (verificar en PRE) | idéntico |
| `project.task` | `project.task_comp_rule` (verificar en PRE) | idéntico |
| `account.analytic.line` | `analytic.analytic_line_rule` (verificar en PRE) | idéntico |
| `account.analytic.account` | `analytic.analytic_account_rule` (verificar en PRE) | idéntico |
| `hr.employee` | `hr.hr_employee_comp_rule` (verificar en PRE) | idéntico |
| `mrp.production` | `mrp.mrp_production_comp_rule` (verificar en PRE) | idéntico |

**Hecho clave:** en v19 todas usan `('company_id','in',company_ids)` (en versiones muy antiguas algunas usaban `child_of user.company_id`; **no** copies ese patrón viejo). Cualquier record rule custom que escribas para reforzar aislamiento **debe seguir el patrón `company_ids`** para no chocar (recuerda: globales = AND, una regla mal escrita puede dejar a la gente sin ver **nada**).

### Query de auditoría (solo lectura, segura en PRO)

Ejecútala en PRE **y** en PRO para inventariar el estado real y confirmar los xmlids marcados:

```sql
SELECT r.id, m.model, r.name, r.domain_force, r.global,
       r.perm_read, r.perm_write, r.perm_create, r.perm_unlink
FROM ir_rule r
JOIN ir_model m ON m.id = r.model_id
WHERE r.domain_force ILIKE '%company_id%'
ORDER BY m.model;
```

Para recuperar el **xmlid exacto** de cada regla (así confirmas los marcados arriba):

```sql
SELECT d.module || '.' || d.name AS xmlid, m.model, r.name
FROM ir_model_data d
JOIN ir_rule r ON r.id = d.res_id AND d.model = 'ir.rule'
JOIN ir_model m ON m.id = r.model_id
ORDER BY m.model;
```

> Una desinstalación/reinstalación de un módulo puede dejar reglas huérfanas o faltantes. Si a un modelo de negocio le **falta** su regla de compañía, hay fuga silenciosa. Compara el inventario contra esta tabla.

---

## 4. Qué COMPARTIR vs qué SEPARAR — tabla maestra

Regla mental: **maestros técnicos sin compañía (UdM, moneda) = solo se protegen con permisos**; **maestros contables (diarios, cuentas, analíticas, secuencias) = compañía + permisos**.

| Dato maestro | Modelo | ¿Tiene compañía? | Decisión | Mecanismo de protección | Motivo |
|---|---|---|---|---|---|
| Productos | `product.template` / `product.product` | `company_id` opcional (default False) | **COMPARTIR** (`company_id=False`) | Contabilizar con campos `company_dependent` (§5); blindar write/unlink con permisos | Un solo catálogo, incluido el producto de servicio "Horas"; evita duplicarlo |
| Categorías de producto | `product.category` | No | Compartido | Permisos ([[04-blindaje-datos-maestros]]) | Global |
| **Unidades de medida** | `uom.uom` / `uom.category` | **NO tiene campo compañía. Global.** | Compartido obligatorio | **Solo permisos**: write/unlink=0 salvo custodio | La UdM "Horas" es system-wide; su alteración rompió TODOS los partes. No se aísla por compañía |
| Monedas | `res.currency` | Global | Compartido | Solo permisos | Igual que UdM |
| **Cuentas contables** | `account.account` | v17+/v19 usa **`company_ids` (m2m)** | **SEPARAR** en la práctica (una cuenta por compañía), salvo plan común deliberado | Reglas de compañía + permisos + `check_company` | Cuenta 90 = AUNNA, 271 = CITRIC |
| **Diarios** | `account.journal` | `company_id` (single) | **SEPARAR** siempre | Regla nativa `journal_comp_rule` + permisos | Numeración/secuencias y asientos por compañía |
| **Cuentas analíticas** | `account.analytic.account` | `company_id` opcional | **SEPARAR** las de P&L de compañía; compartir solo si es deliberado | Regla de compañía + `check_company` en los enlaces | La 90 (AUNNA) inyectada en CITRIC fue el fallo; la 155 hubo que pasarla a `company_id=2` |
| Planes analíticos | `account.analytic.plan` | Sin compañía (agnóstico) | **Compartido** | Permisos | El plan "Horas internas/externas" (`x_plan3_id`) es común; lo que separa es la **cuenta** dentro del plan |
| **Modelos de distribución analítica** | `account.analytic.distribution.model` | `company_id` opcional | **SEPARAR SIEMPRE** (nunca `company_id=False` si apunta a cuenta de compañía) | `company_id` obligatorio + query de control (§7) | **Vector directo del incidente cuenta 90** |
| **Secuencias** | `ir.sequence` | `company_id` | **SEPARAR** por compañía | Permisos + separar por compañía | Numeración de documentos por compañía |
| Impuestos | `account.tax` | `company_id` | Separar | Regla de compañía + permisos | Por compañía |
| Posiciones fiscales | `account.fiscal.position` | `company_id` | Separar | Regla de compañía + permisos | Por compañía |
| Almacenes | `stock.warehouse` | `company_id` | Separar | `stock_warehouse_comp_rule` | Logística por compañía |
| Fechas de cierre fiscal | lock dates en `res.company` | Por compañía nativamente | Separado | Nativo | En Odoo moderno no existe `account.period`; son lock dates por compañía |

---

## 5. `company_dependent=True` — valores distintos por compañía en el MISMO registro

Permite **compartir el catálogo pero contabilizar separado**, sin duplicar productos.

- Un campo `company_dependent=True` (típico en `product.template`: `property_account_income_id`, `property_account_expense_id`, plazos de pago, y en v17+ el `standard_price`) **no guarda un valor único**: guarda **un valor por compañía**.
- **Cambio en Odoo 17+ (aplica a v19):** ya **no** se almacenan en `ir.property`. Se guardan en una **columna `jsonb`** en la propia tabla del modelo, indexada por id de compañía.
- Consecuencia de gobernanza: si editas la cuenta de ingresos de un producto **estando en AUNNA**, solo cambias el valor de AUNNA; CITRIC conserva el suyo. Un producto **compartido** (`company_id=False`) puede así tener **contabilización distinta por compañía** sin duplicarlo. **Es la forma correcta** de compartir el producto "Horas" y aun así contabilizarlo separado en cada compañía.

> Al tocar un campo `company_dependent` de un producto compartido, ten siempre presente **qué compañía tienes activa**: solo modificas la de esa compañía.

---

## 6. `check_company=True` — el guardián cross-company de ESCRITURA

Las record rules filtran, **por operación** (`perm_read` / `perm_write` / `perm_create` / `perm_unlink`), **qué registros** puedes ver o tocar. Lo que **NO** hacen es impedir **mezclar compañías dentro de un mismo registro** al guardar. Para eso está `check_company`.

- Un campo relacional declarado con `check_company=True` entra en la constraint `_check_company` (que se dispara vía `_check_company_auto=True` en el modelo).
- Al guardar, Odoo verifica que **el `company_id` del registro coincide con el de todos los relacionados** que tengan `check_company=True` (o que el relacionado tenga compañía False = compartido).
- Es **exactamente** el origen del mensaje del incidente CITRIC:
  > *"El proyecto, la tarea y las cuentas analíticas del parte de horas deben pertenecer a la misma compañía."*
  Lo lanza `_check_company` sobre `account.analytic.line` porque el parte apuntaba a la cuenta 90 (AUNNA) estando el parte en CITRIC.

Declaración de referencia (ya en uso en el repo, `aunna_project_cost_account_moves/models/res_company.py`):

```python
account_id = fields.Many2one('account.account', check_company=True)
journal_id = fields.Many2one('account.journal', check_company=True)
analytic_account_id = fields.Many2one('account.analytic.account', check_company=True)
```

**Norma de desarrollo:** en cualquier módulo custom `zambudio_*` / `aunna_*` que enlace **cuenta, diario, cuenta analítica, almacén o partner de facturación** a un documento de compañía, poner **siempre** `check_company=True` (y asegurar que el modelo tiene `_check_company_auto=True`, que Odoo activa solo si hay al menos un campo con `check_company`). Es la segunda línea de defensa (la primera son las reglas de lectura) y es la que **habría bloqueado** la inyección de la 90 en CITRIC en el momento de guardar.

---

## 7. El problema estrella: distribución analítica cross-company (cuenta 90)

### Cadena del fallo (documentada en [[05-record-rules-multiempresa]])

1. Los documentos que llevan analítica (líneas de asiento/factura, líneas de venta/compra y, en la creación de partes, la resolución de la analítica del parte) obtienen su `analytic_distribution` **por defecto calculado** a partir de los modelos de distribución (`account.analytic.distribution.model`). *(El mecanismo exacto por el que el parte de horas hereda la 90 en tu configuración concreta —modelo de distribución vs. automatización Studio— hay que verificarlo en PRE; ver punto c.)*
2. Un modelo de distribución **matchea** si sus criterios (partner, producto, categoría, prefijo de cuenta) casan **y** su `company_id` es `False` **o** coincide con la compañía **activa** (`env.company`).
3. Un modelo con **`company_id = False`** que apunta a la **cuenta 90 (AUNNA)** matchea **también en CITRIC** → inyecta la 90 → `_check_company` revienta el parte de CITRIC.
4. Como el usuario (Manuel, uid 52) tenía AUNNA como compañía **activa**, todo se resolvía en contexto AUNNA aunque el empleado/proyecto fuera CITRIC.

### Blindaje (recomendaciones concretas)

**a) Todo `account.analytic.distribution.model` debe tener `company_id` seteado.** Prohibir `company_id=False` en cualquier modelo que referencie cuentas de P&L de compañía. Crear el par consciente de compañía:

| company_id | Cuenta P&L "Horas internas/externas" (plan `x_plan3_id`) |
|---|---|
| 1 (AUNNA) | cuenta **90** |
| 2 (CITRIC) | cuenta **271** |
| MONTOYA (id: **verificar en PRE**) | cuenta P&L de horas equivalente a la 90/271 (**crear/identificar; verificar en PRE**) |
| ii (id: **verificar en PRE**) | cuenta P&L de horas equivalente a la 90/271 (**crear/identificar; verificar en PRE**) |

**b) Diagnóstico (query real, solo lectura):**

```sql
-- Modelos de distribución que apuntan a la 90:
SELECT id, company_id, account_prefix, partner_id, product_id,
       product_categ_id, analytic_distribution
FROM account_analytic_distribution_model
WHERE analytic_distribution::text LIKE '%90%'
ORDER BY id;

-- LOS PELIGROSOS: sin compañía apuntando a la 90 (deben ser CERO):
SELECT id, company_id, analytic_distribution
FROM account_analytic_distribution_model
WHERE company_id IS NULL
  AND analytic_distribution::text LIKE '%90%';
```

> ⚠️ `analytic_distribution` es un JSON indexado por **id de cuenta analítica**, no por su código contable. El `LIKE '%90%'` casa por **texto** y puede dar falsos positivos (p. ej. el id 190) o falsos negativos. Úsalo como primer filtro y **confirma** cruzando contra `account_analytic_account` el id real de la cuenta "90" en PRE antes de actuar.

Si la segunda query devuelve filas, hay fuga latente. Cualquier `UPDATE`/reasignación de `company_id` se hace **primero en PRE**.

**c) Automatizaciones de Studio.** Las `base_automation` / server actions que fijan distribución **no viajan con código** y a menudo están escritas contra la 90 fija. Hay que **rehacerlas conscientes de compañía** (leer `env.company` y elegir 90 vs 271 vs la de MONTOYA/ii). **Esta es la vía más probable de reintroducir el bug tras un despliegue.**

**d) `check_company=True`** en el campo cuenta de cualquier custom sobre `account.analytic.line` (ya presente en `aunna_project_cost_account_moves`).

**e) Reducir compañías simultáneas.** Si un fichador de CITRIC **no tiene AUNNA en `company_ids`**, la 90 nunca se le puede resolver. Es el control más eficaz.

---

## 8. Reforzar el aislamiento por app — normas y ejemplos

### 8.1 Norma general para record rules custom

Toda regla custom de compañía debe ser **global** y seguir el patrón canónico, para que sume (AND) y **nadie la esquive con otro grupo**:

```xml
<record id="rule_mimodelo_multicompany" model="ir.rule">
    <field name="name">MiModelo: aislamiento multi-compañía</field>
    <field name="model_id" ref="model_mi_modelo"/>
    <field name="groups" eval="[]"/>
    <field name="domain_force">
        ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
    </field>
</record>
```

> ⚠️ **`global` es un campo CALCULADO, nunca se escribe.** En `ir.rule`, `global = not groups_id` y es de **solo lectura**: poner `<field name="global" eval="True"/>` **no hace nada** (el `eval` se ignora) y la regla acabaría siendo **de grupo** (combinada con OR = esquivable dando otro grupo). Para que una regla sea **global de verdad**, déjala **sin grupos**: `<field name="groups" eval="[]"/>` (lista de grupos vacía = global). Por eso todos los ejemplos de este documento usan `groups eval="[]"` y **nunca** `global eval="True"`. Recuerda: solo el **uid 1** (superusuario) ignora las record rules; `base.group_system` **no** las ignora.

> ⚠️ **No fijes `perm_*` restrictivos en una regla de aislamiento.** Al omitir `perm_read/write/create/unlink`, Odoo los deja en `True` (la regla aplica a todas las operaciones), que es lo que quieres aquí. Si pones alguno a `False`, esa operación **deja de estar filtrada por esta regla** y puedes abrir un agujero en vez de cerrarlo. Una regla de compañía filtra las 4 operaciones con el mismo dominio.

> ⚠️ Precaución de "dejar a todos sin datos": si tu modelo de enlace interno **nunca** debe tener registros sin compañía, puedes usar `[('company_id','in',company_ids)]` sin el `'|', ('company_id','=',False)` (es lo que hace `aunna_project_cost_account_moves/security/project_cost_move_link_rules.xml`). Pero si algún registro queda con `company_id=False`, **se ocultará a todos**. Para modelos de negocio con datos compartidos, incluye siempre la rama `('company_id','=',False)`.

### 8.2 Tabla app → qué reforzar

| App | Modelos a vigilar | Regla nativa esperada | Refuerzo recomendado |
|---|---|---|---|
| **Ventas** | `sale.order`, `sale.order.line` | `sale.sale_order_comp_rule` | Confirmar que existe; equipos de ventas por compañía (`crm.team.company_id`) |
| **Compras** | `purchase.order` | `purchase.purchase_order_comp_rule` | Idem; separar SoD (quien compra no paga — ver [[02-catalogo-de-roles]]) |
| **Stock** | `stock.picking`, `stock.warehouse`, `stock.location` | `stock_picking_rule`, `stock_warehouse_comp_rule` (verificar en PRE) | Ubicaciones y almacenes por compañía; `check_company` en movimientos |
| **Contabilidad** | `account.move`, `account.journal`, `account.account`, `account.tax` | `account_move_comp_rule`, `journal_comp_rule` | Diarios y secuencias por compañía; lock dates por compañía |
| **Analítica** | `account.analytic.line`, `account.analytic.account`, `account.analytic.distribution.model` | `analytic_line_rule`, `analytic_account_rule` (verificar en PRE) | **`company_id` en todos los modelos de distribución (§7)**; `check_company` en enlaces |
| **Proyecto** | `project.project`, `project.task` | `project_comp_rule`, `task_comp_rule` | `check_company` proyecto↔tarea↔analítica (encaja con `zambudio_project_*`) |
| **Partes de horas** | `account.analytic.line` (los timesheet), producto "Horas", UdM "Horas" | `analytic_line_rule` | UdM y producto compartidos y **blindados por permisos** ([[04-blindaje-datos-maestros]]); distribución consciente de compañía |
| **RRHH** | `hr.employee`, `hr.department` | `hr.hr_employee_comp_rule` (verificar en PRE) | Empleados por compañía; datos personales al mínimo de personas |
| **Gastos** | `hr.expense`, `hr.expense.sheet` | `hr_expense.*_comp_rule` (verificar en PRE) | Compañía del gasto = compañía del empleado; aprobador ≠ solicitante |
| **Fabricación** | `mrp.production`, `mrp.bom` | `mrp.mrp_production_comp_rule` (verificar en PRE) | Escalado desde `stock.group_stock_user` |

### 8.3 Ejemplo: separar diarios por compañía (refuerzo explícito)

Normalmente basta la regla nativa `journal_comp_rule`. Si se ha perdido o quieres reforzarla:

```xml
<record id="zambudio_journal_company_rule" model="ir.rule">
    <field name="name">Diarios: solo compañías seleccionadas</field>
    <field name="model_id" ref="account.model_account_journal"/>
    <field name="groups" eval="[]"/>
    <field name="domain_force">
        ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
    </field>
</record>
```

> Nota: `account.journal.company_id` es obligatorio (siempre tiene compañía), así que la rama `('company_id','=',False)` aquí no llega a matchear ningún diario real; la dejamos por homogeneidad del patrón y por seguridad ante datos anómalos. No hace daño.

### 8.4 Ejemplo: modelo de distribución analítica consciente de compañía (datos, no automatización)

Si defines los modelos de distribución por XML/datos en vez de por Studio (recomendado, porque **viaja con código**):

```xml
<!-- AUNNA (id 1) -> cuenta 90 -->
<record id="dist_horas_internas_aunna" model="account.analytic.distribution.model">
    <field name="company_id" ref="base.main_company"/>  <!-- id 1 = AUNNA (verificar en PRE) -->
    <field name="account_prefix">...</field>            <!-- prefijo/criterio real (verificar en PRE) -->
    <field name="analytic_distribution">{"CUENTA_90_ID": 100}</field>
</record>

<!-- CITRIC (id 2) -> cuenta 271 -->
<record id="dist_horas_internas_citric" model="account.analytic.distribution.model">
    <field name="company_id" ref="COMPANIA_CITRIC_ID"/> <!-- id 2 = CITRIC (verificar en PRE) -->
    <field name="account_prefix">...</field>
    <field name="analytic_distribution">{"CUENTA_271_ID": 100}</field>
</record>
```

> Sustituye `CUENTA_90_ID` / `CUENTA_271_ID` por los **ids de la cuenta analítica** reales en PRE (la clave del JSON es el id de `account.analytic.account`, no el código). `base.main_company` es el xmlid estándar de la primera compañía (id 1); confirma en PRE que corresponde a AUNNA. **Nunca** dejes un modelo de distribución sin `company_id` si apunta a una cuenta de P&L de compañía.

---

## 9. Aislamiento por usuario: `company_ids` (el control más eficaz)

Principio de **mínimo privilegio también para compañías**. Perfil por perfil, dar en `company_ids` **solo** las compañías donde la persona realmente opera.

| Perfil | `company_ids` recomendado | `base.group_multi_company` |
|---|---|---|
| Fichador/consultor que solo trabaja en una compañía | solo esa compañía | **No** |
| Contabilidad de AUNNA | solo AUNNA (o AUNNA+CITRIC si lleva ambas contabilidades) | Sí solo si lleva varias |
| Dirección / Gerencia | todas las que supervisa | Sí |
| Custodio / Superadmin | todas | Sí |

- El selector multiempresa solo aparece con **`base.group_multi_company`**. **No lo des** a perfiles monocompañía.
- Query de auditoría de sobre-exposición (solo lectura):

```sql
SELECT u.login, array_agg(c.name ORDER BY c.id) AS companias
FROM res_company_users_rel r
JOIN res_users u ON u.id = r.user_id
JOIN res_company c ON c.id = r.cid
GROUP BY u.login
ORDER BY u.login;
```

> ⚠️ Verifica en PRE los nombres reales de la tabla/columnas del m2m `res.users.company_ids` (`res_company_users_rel`, `user_id`, `cid`): son los habituales en Odoo, pero confírmalos con `\d res_company_users_rel` antes de fiarte del resultado. Revisa quién tiene más de una compañía y si lo justifica su función.

---

## 10. Configuración que NO viaja con código (recrear consciente de compañía)

Aviso operativo permanente: lo siguiente **no está en los módulos** y hay que **recrearlo en cada entorno** (y consciente de compañía):

| Elemento | Dónde vive | Riesgo | Acción |
|---|---|---|---|
| Modelos de distribución analítica | `account.analytic.distribution.model` (datos en BD) | `company_id=False` reintroduce la fuga 90 | Definir por XML/datos si es posible; si no, documentar y auditar cada uno |
| Automatizaciones Studio / `base_automation` | BD, por entorno | Reglas escritas contra la 90 fija | Rehacer conscientes de `env.company`; auditar con `auditlog` |
| Server actions (`ir.actions.server`) | BD | Idem | Idem |
| Lock dates por compañía | `res.company` | No se migran solas entre PRE/PRO | Fijar por compañía tras cada restauración |
| Secuencias `ir.sequence` por compañía | BD | Numeración cruzada | Verificar `company_id` de cada secuencia |
| Reglas/permisos creados a mano por UI | `ir.rule` / `ir.model.access` sin `ir.model.data` | No tienen xmlid; se pierden o no se replican | Preferir siempre definirlos en módulo; auditar los que no tengan xmlid |

> Tras **cualquier restauración de backup** o refresco de PRE desde PRO, re-verificar: (1) las 12 reglas nativas de §3, (2) que ningún modelo de distribución tenga `company_id IS NULL` apuntando a cuenta de compañía (§7), (3) `company_ids` de usuarios (§9), (4) lock dates por compañía. Ver checklist en [[07-auditoria-trazabilidad-hardening]].

---

## 11. Checklist accionable (para PRE y luego PRO)

1. [ ] Ejecutar query §3 en PRE **y** PRO: confirmar que existen todas las reglas de compañía nativas y **capturar sus xmlids reales** (query de xmlid de §3) antes de referenciarlos.
2. [ ] Confirmar ids de compañía (AUNNA=1, CITRIC=2, MONTOYA=?, ii=?).
3. [ ] Ejecutar query "peligrosos" §7 y **cruzar el id real de la cuenta 90**: cero modelos de distribución con `company_id IS NULL` apuntando a cuenta de compañía.
   - [ ] **Go-live — las 4 compañías (AUNNA / CITRIC / MONTOYA / ii):** verificar explícitamente en PRE **y** PRO que **NINGUNA** de las cuatro tiene un `account.analytic.distribution.model` con `company_id` **NULL** que apunte a una cuenta de **P&L de OTRA compañía**. No basta con revisar la 90/271: repetir el control para las cuentas de horas de MONTOYA e ii.
4. [ ] Crear/verificar el par de distribución 90→AUNNA(1) y 271→CITRIC(2), y equivalentes para MONTOYA/ii.
5. [ ] Auditar `company_ids` de usuarios (query §9): quitar compañías de más a perfiles monocompañía.
6. [ ] Confirmar `base.group_multi_company` solo en perfiles que operan en varias compañías.
7. [ ] Verificar `check_company=True` (y `_check_company_auto`) en todos los campos relacionales de los módulos custom que atan cuenta/diario/analítica a documentos.
8. [ ] Documentar/recrear las automatizaciones de Studio conscientes de compañía y auditarlas.
9. [ ] Blindaje de UdM/producto "Horas" (globales, no aíslables por compañía): ver [[04-blindaje-datos-maestros]].
10. [ ] Repetir 1–8 tras cada restauración de backup.

> **Recordatorio producción:** las queries de este documento son de **solo lectura** y seguras en PRO. Cualquier `UPDATE` sobre `account_analytic_distribution_model`, sobre `company_id`/`company_ids` de cuentas/analíticas, o sobre `company_ids` de usuarios se prueba **primero en PRE** (`grupo_zambudio_prod_pruebas`). Los xmlids marcados **(verificar en PRE)** se confirman con las queries de §3 antes de referenciarlos en código.

---

## Documentos relacionados

- [[04-blindaje-datos-maestros]] — blindaje de UdM, producto "Horas" y demás maestros globales (permisos, `ir.rule` global, custodio).
- [[02-catalogo-de-roles]] — roles, mínimo privilegio, SoD, los dos "admin", y modelo v19 `res.groups.privilege` / `privilege_id`.
- [[05-record-rules-multiempresa]] — incidente CITRIC / cuenta 90 con datos reales (uid 52, cuentas 90/271/155, `x_plan3_id`).
- [[07-auditoria-trazabilidad-hardening]] — auditlog, doble control, PRE antes que PRO.