# Esquema de Permisos, Roles y Blindaje de Datos Maestros — Grupo Zambudio / Aunna IT (Odoo 19 Enterprise)

> **Carpeta:** `new/permisos` · **Autor:** Pablo Andreu (Aunna IT) · **Fecha:** 2026-07-22
> **Estado:** DOCUMENTACIÓN / PROPUESTA. No es un módulo instalable. Los ejemplos XML/CSV son de referencia, copiables, pero **todo despliegue se prueba primero en PRE** (`erp-pre.zambudio.es`, BD `grupo_zambudio_prod_pruebas`) antes de tocar PRO (`erp.zambudio.es`, BD `grupo_zambudio_prod`).

> ⚠️ **Cómo leer los xmlids de este documento.** Los xmlids de núcleo se aportan de conocimiento verificado contra el código de Odoo, pero **cualquiera marcado `(verificar en PRE)` debe confirmarse en la BD real** (Ajustes → Técnico → *External Identifiers*, o `SELECT module,name FROM ir_model_data WHERE ...`) antes de referenciarse en un módulo o en un `ref=`. No referenciar en PRO ningún xmlid sin haberlo resuelto antes en PRE.

> 🟢 **NOMBRE CANÓNICO — FUENTE DE VERDAD (este README manda sobre todo el corpus).**
> - **Módulo de refuerzo (referencia):** `zambudio_permisos` (autor/prefijo Zambudio). Puede materializarse a futuro como módulo, o crearse el grupo directamente por UI.
> - **Grupo custodio (rol "Custodio de Datos Maestros"):** xmlid CANÓNICO = **`zambudio_permisos.group_master_data_custodian`**.
> - Este grupo **NO implica `base.group_system`** y **NO es el uid 1**: es un grupo **FUNCIONAL**. Las reglas de blindaje lo **re-permiten explícitamente** dentro del propio `domain_force` (vía `user.has_group(...)`).
> - Quedan **OBSOLETAS** y deben sustituirse por el canónico todas estas variantes históricas: `zambudio_custom`, `zambudio_master_data`, `zambudio_master_data_custody`, `zambudio_master_data_lock`, `zambudio_security_hardening`, `group_master_data_custody` y cualquier otra. **Cualquier otro nombre en versiones previas es histórico; usar siempre el canónico.**
> - Si el grupo se crea por **UI** en lugar de por módulo, su xmlid real se resolverá en PRE — marcarlo entonces como **`(verificar en PRE)`**.

---

## 1. Resumen ejecutivo — por qué existe este documento

### El incidente que lo motiva

Un usuario con perfil **"Administrador"** (grupo `base.group_system`) **renombró el producto de servicio "Horas"** (el que usan los partes de horas vía `sale_timesheet`) convirtiéndolo en un producto de venta, y además **alteró/borró la unidad de medida "Horas"** (`uom.uom`, xmlid **`uom.product_uom_hour` (verificar en PRE)**).

Consecuencia: se rompieron **todos los partes de horas** (`hr_timesheet` depende de esa UdM y de ese producto de servicio para registrar y convertir tiempo). Hubo que **restaurar el backup del día anterior**, perdiéndose el trabajo de toda la jornada.

### El diagnóstico

No fue un accidente puntual: fue un **fallo de gobernanza de permisos**. El vector técnico exacto:

- El daño fue un **`write` (renombrar + cambiar tipo/UdM)**, no un `unlink`. Ni las claves foráneas (FK) ni el `noupdate="1"` del núcleo lo impidieron: esos mecanismos frenan **borrados** (o reimportaciones), no renombrados en caliente.
- Un usuario con `base.group_system` **NO es** el superusuario (`base.user_root`, uid 1). Las *record rules* **sí le aplican**. Por tanto, una **regla restrictiva bien diseñada** habría bloqueado al admin del incidente, dejando la edición solo al custodio.
- Demasiadas personas tenían acceso a **datos maestros** (UdM, productos, plan de cuentas, diarios, analíticas, secuencias) y a **menús técnicos/Ajustes**.

### El objetivo del entregable

Un esquema **óptimo y exhaustivo** de permisos, roles, *record rules* y restricciones para:

- **(a)** Blindar datos maestros (UdM, productos, plan de cuentas, diarios, cuentas y planes analíticos, secuencias, monedas, periodos fiscales) para que **nadie salvo un custodio** pueda renombrar/borrar.
- **(b)** Mínimo privilegio por rol y por app.
- **(c)** Aislar la multiempresa (AUNNA IT id 1 / CITRIC NETWORKS id 2 / MONTOYA / ii) en una sola BD.
- **(d)** Auditoría y trazabilidad (quién tocó qué y cuándo).
- **(e)** Gobernanza: custodia del superadmin, doble control, cambios en PRE primero.

---

## 2. Principios rectores

1. **Mínimo privilegio.** Cada persona arranca con `base.group_user` + el nivel **más bajo (User)** de las apps que realmente usa. Manager/Administrator solo si la función lo exige. Nadie tiene un grupo "por si acaso".
2. **Blindaje de datos maestros.** El `write`/`unlink` sobre UdM, productos, plan de cuentas, diarios, cuentas/planes analíticos, secuencias y monedas se reserva a **un único rol Custodio**. El resto: solo lectura. Se implementa con **`ir.rule` (regla que sí resta)** reforzada con `ir.model.access`.
3. **Nunca restringir `perm_read` en datos maestros.** UdM, productos y cuentas aparecen en desplegables de toda la operativa. Si una regla quita lectura, se rompen ventas, partes, facturas y compras. Todas las reglas de blindaje llevan **`perm_read` = False** (no aplican a lectura) o dominio que siempre permite leer.
4. **Separación admin-técnico ↔ funcional.** `base.group_system` es **custodia, no un rol de trabajo**. Administración, Contabilidad, Ventas, Almacén… **jamás** lo necesitan para su día a día. Se separan el "admin técnico" (`base.group_system`) y el "admin de accesos" (`base.group_erp_manager`).
5. **Doble control.** Los cambios de datos maestros y de permisos se piden por ticket, se aplican **primero en PRE**, se validan con los flujos reales (partes de horas, facturación WIP) y luego pasan a PRO.
6. **Cambios en PRE primero, siempre.** Ningún xmlid de núcleo se referencia en producción sin verificarlo en PRE. Ningún `UPDATE` SQL toca PRO sin ensayarse en `grupo_zambudio_prod_pruebas`.
7. **Auditoría y trazabilidad.** `auditlog` (OCA) sobre datos maestros y sobre los modelos de seguridad/automatización (`ir.rule`, `ir.model.access`, `base.automation`, `ir.actions.server`). Sin esto, los cambios de Studio no dejan rastro.
8. **Custodia del superadmin = Pablo (Admin/Dev), custodio único.** Hoy solo Pablo tiene `base.group_system` + modo desarrollador + el grupo custodio de datos maestros. **Designar 1 suplente** (bus-factor); credenciales bajo control, actividad auditada, 2FA obligatorio. El superusuario real (uid 1) se reserva a emergencias. La jerarquía real **Pablo › CEO › Responsables › Empleados › Becarios** se detalla en [[02-catalogo-de-roles]] (§0-bis).
9. **Revisión periódica.** Auditoría trimestral de `res.users` con `base.group_system`/`base.group_erp_manager`, de `company_ids` sobrantes, y de las *record rules* nativas (que una reinstalación de app puede dejar huérfanas).

---

## 3. Índice de la carpeta `new/permisos`

| # | Fichero | Contenido |
|---|---------|-----------|
| 0 | **README.md** (este) | Resumen ejecutivo, principios, índice, Quick Wins TOP 10, alcance. |
| 1 | [[00-principios-y-gobernanza]] | Gobernanza operativa: custodia superadmin (titular+suplente), doble control, procedimiento PRE→PRO, tickets, revisión periódica, matriz de responsabilidades. |
| 2 | [[01-modelo-seguridad-odoo19]] | Cómo funciona la seguridad en v19: `res.groups` + nuevo `res.groups.privilege` (`privilege_id`), `implied_ids`, capas ACL vs record rules vs `groups=`, cambio `groups_id`→`group_ids`, superusuario que ignora reglas. |
| 3 | [[02-catalogo-de-roles]] | Catálogo completo Rol→grupos (xmlids reales): Dirección, Administración/Contabilidad, Jefe de Proyecto, Consultor, Compras, Almacén, Producción, RRHH, Comercial, Custodio de Datos Maestros, Superadmin, Portal. Matriz de incompatibilidades (SoD). |
| 4 | [[03-matriz-permisos-por-app]] | Tabla app-por-app: qué grupo da User/Manager/Admin, qué menú abre, qué CRUD concede sobre los modelos clave. |
| 5 | [[04-blindaje-datos-maestros]] | El núcleo del entregable: `ir.rule` + `ir.model.access` + `groups=` para blindar `uom.uom`, `uom.category`, producto "Horas", `account.account`, `account.journal`, analíticas, `ir.sequence`, `res.currency`. XML/CSV copiables. |
| 6 | [[05-record-rules-multiempresa]] | Aislamiento AUNNA/CITRIC: patrón `['|',('company_id','=',False),('company_id','in',company_ids)]`, `check_company=True`, distribución analítica (cuenta 90/271), inventario de reglas nativas y query de verificación. |
| 7 | [[06-restricciones-tecnicas-xml]] | Colección exhaustiva de restricciones XML copiables: ocultar menús técnicos, bloquear export/import, campos sensibles con `groups=`, quitar Apps/store, lock dates contables. |
| 8 | [[07-auditoria-trazabilidad-hardening]] | `auditlog`, `auth_session_timeout`, 2FA nativo forzado, catálogo OCA de hardening con disponibilidad en 19, avisos de soporte Enterprise. |
| 9 | [[08-plan-implementacion-y-runbook]] | Runbook paso a paso PRE→PRO: orden de aplicación, checklist de validación de flujos reales, plan de rollback, cronograma. |
| 10 | [[09-anexo-verificacion-y-checklist]] | Anexo de verificación: resolución de xmlids/ids en PRE y PRO (grupo custodio, UdM "Horas", producto "Horas", cuentas de P&L de horas por compañía AUNNA/CITRIC/MONTOYA/ii), checklist go-live, norma de backup etiquetado, riesgo residual y revisión de automatizaciones Studio. |

> 📌 **La tabla de decisión de patrón (P1/P2/P3 por modelo maestro) vive en [[04-blindaje-datos-maestros]]** — es la referencia oficial de qué patrón de `ir.rule` aplica a cada modelo (`uom.uom`, `res.currency`, `account.*`, producto "Horas", etc.).

---

## 4. Quick Wins — TOP 10 a aplicar primero

Ordenados por impacto/esfuerzo. Cada uno se prueba en PRE antes de PRO.

| # | Acción | Cómo | Impacto |
|---|--------|------|---------|
| 1 | **Quitar `base.group_system` a todo perfil funcional** | Ajustes → Usuarios: dejar el grupo **solo a Pablo** (Admin/Dev, custodio único; +1 suplente). CEO, responsables, empleados y becarios **NO** lo llevan. Sin él no se ve Ajustes, Apps ni menús técnicos, pero el trabajo diario sigue si se mantienen los grupos funcionales. | Corta de raíz el vector del incidente y el acceso a Apps/store. |
| 2 | **Regla que blinda la UdM "Horas" y su categoría** | `ir.rule` sobre `uom.uom` y `uom.category` que solo permite `write`/`unlink` al custodio (patrón `user.has_group`, ver XML abajo). | Impide renombrar/alterar la UdM que rompió los partes. |
| 3 | **Regla que blinda el producto de servicio "Horas"** | `ir.rule` sobre `product.template`/`product.product` que bloquea `write`/`unlink` **solo del/los producto(s) de partes** (por id), no de todo el catálogo. | Impide convertir "Horas" en producto de venta **sin romper la edición del resto de productos**. |
| 4 | **Crear el rol custodio `zambudio_permisos.group_master_data_custodian`** | Grupo **funcional** nuevo (futuro módulo `zambudio_permisos`, o creado por UI → xmlid `(verificar en PRE)`). **No implica `base.group_system` ni es el uid 1.** Único con `write`/`unlink` sobre UdM, productos, cuentas, diarios, analíticas, secuencias, monedas. Resto: read=1. Variantes previas del nombre son históricas → usar el canónico. | Centraliza y hace trazable quién toca maestros. |
| 5 | **Forzar 2FA a custodios y a todo `base.group_system`** | Nativo `auth_totp`: Ajustes → Permisos → *Two-factor authentication* **(verificar ruta/opción de forzado en PRE)**. | Protege las cuentas más peligrosas. |
| 6 | **Instalar `auditlog` (OCA server-tools, verificar rama 19 en PRE)** | Reglas de auditoría en `product.template`, `product.product`, `uom.uom`, `uom.category`, `account.account`, `account.journal`, `account.analytic.account`/`account.analytic.plan`, `ir.sequence`, `res.currency`, más `ir.rule`, `ir.model.access`, `base.automation`, `ir.actions.server`. | Rastro nominal de todo cambio, incluido lo hecho por Studio. |
| 7 | **Auditar y no dar `company_ids` de más** | Revisar que cada usuario solo tenga en `company_ids` las compañías donde opera. Un fichador de CITRIC sin AUNNA no puede inyectar la cuenta 90. | Control más eficaz contra fugas cross-company. |
| 8 | **Verificar que existen las record rules multiempresa nativas** | Query SQL de [[05-record-rules-multiempresa]] sobre `ir_rule` (contar y listar las de `company`). Una reinstalación de app puede dejarlas huérfanas. | Garantiza el aislamiento AUNNA/CITRIC. |
| 9 | **`auth_session_timeout` (OCA, verificar rama 19 en PRE) con excepción para APIs** | Logout por inactividad. Excluir usuarios técnicos/integración (campo de exclusión del propio módulo). | Reduce sesiones abiertas olvidadas. |
| 10 | **Restringir el botón Exportar a un grupo** | Nativo `base.group_allow_export` **(verificar en PRE)** solo a perfiles autorizados; alternativas OCA `web_disable_export_group` / `base_export_manager` **(verificar port a 19 en PRE)**. | Evita fuga masiva de datos maestros/contactos. |

### XML de referencia — blindaje de la UdM "Horas" (Quick Win 2)

> ⚠️ **Global vs. por grupo — el detalle que importa.** Las reglas **globales** (sin grupos) se combinan en **AND** y **no se pueden reabrir** con otro grupo; las reglas **de grupo** se combinan en **OR** entre sí. Por eso **no puedes "re-permitir" al custodio con una segunda regla de grupo frente a una regla global**: la global sigue aplicando. La forma limpia de tener una regla global **irrompible** que a la vez deje pasar al custodio es meter la excepción **dentro del propio dominio** con `user.has_group(...)`. Es el patrón recomendado (el superusuario uid 1 se salta las reglas de todos modos).

Regla **global** cuyo dominio devuelve "todo permitido" para el custodio y "nada modificable" para el resto. **No toca lectura** (`perm_read` = False).

```xml
<record id="uom_lock_write_rule" model="ir.rule">
    <field name="name">UdM: solo custodio modifica/borra</field>
    <field name="model_id" ref="uom.model_uom_uom"/>
    <!-- Global: sin grupos => se combina en AND, irrompible.
         has_group está disponible en el eval de domain_force (probar en PRE). -->
    <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [(0, '=', 1)]</field>
    <field name="groups" eval="[]"/>            <!-- sin grupos = regla global -->
    <field name="perm_read"   eval="False"/>    <!-- NO restringe lectura -->
    <field name="perm_write"  eval="True"/>
    <field name="perm_create" eval="True"/>     <!-- crear UdM = solo custodio -->
    <field name="perm_unlink" eval="True"/>
</record>
```

> ⚠️ **Efecto colateral asumido:** esta regla bloquea `create`/`write`/`unlink` de **todas** las UdM (no solo "Horas") para cualquiera que no sea custodio. Es lo deseado (nadie crea UdM en la operativa diaria), pero valídalo en PRE: si algún módulo/flujo crea UdM automáticamente, ajústalo o pon `perm_create` = False. Repite la misma regla para **`uom.category`** (`ref="uom.model_uom_category"`), porque alterar la categoría *Working Time* también rompe los partes.

**Fallback más simple** (si no quieres depender de `user.has_group` en el dominio): dominio **siempre falso** `[(0, '=', 1)]`, regla global, y el custodio edita **como superusuario (uid 1)** en procedimiento controlado. Bloquea a todo `base.group_system` incluido el del incidente. Menos elegante (obliga a usar uid 1 para editar), pero 100% predecible.

### XML de referencia — blindaje del producto "Horas" (Quick Win 3)

> ⚠️ **No bloquear todo `product.template`.** Ventas, Inventario, Compras, MRP editan productos a diario. Una regla con dominio falso sobre todo el modelo **paraliza la operativa**. Hay que blindar **solo el/los producto(s) concretos** que usan los partes, por su **id numérico** (resuelto en PRE) — `domain_force` no dispone de `ref()`.

```xml
<record id="product_horas_lock_rule" model="ir.rule">
    <field name="name">Producto de partes "Horas": solo custodio modifica/borra</field>
    <field name="model_id" ref="product.model_product_template"/>
    <!-- LOCKED_TMPL_IDS = ids de las product.template de partes, resueltos en PRE.
         Custodio: todo permitido. Resto: todo MENOS esos ids. -->
    <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id', 'not in', [LOCKED_TMPL_IDS])]</field>
    <field name="groups" eval="[]"/>
    <field name="perm_read"   eval="False"/>    <!-- lectura libre: el producto sigue en desplegables -->
    <field name="perm_write"  eval="True"/>
    <field name="perm_create" eval="False"/>    <!-- crear productos nuevos NO se toca -->
    <field name="perm_unlink" eval="True"/>
</record>
```

> ⚠️ Replica la misma regla en **`product.product`** (`ref="product.model_product_product"`) con los `product.product` ids equivalentes: los `groups=`/reglas de `product.template` **no** cubren automáticamente `product.product`. El producto de servicio por defecto de los partes suele ser **`sale_timesheet.time_product` (verificar en PRE)**; confirma cuál usa realmente cada compañía antes de fijar los ids.

### CSV de referencia — ACL de refuerzo (read para todos, sin write/unlink)

Cabecera exacta de `ir.model.access.csv` en v19:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_uom_uom_readonly_user,uom.uom read-only,uom.model_uom_uom,base.group_user,1,0,0,0
access_uom_uom_custodian,uom.uom custodian full,uom.model_uom_uom,zambudio_permisos.group_master_data_custodian,1,1,1,1
```

> ⚠️ **El ACL es aditivo (OR entre grupos): añadir una línea con `perm_write=0` NO resta por sí solo.** Si cualquier otro grupo del usuario ya trae un ACL nativo con `perm_write=1` sobre `uom.uom` (existe `uom.group_uom` y ACLs de núcleo — **verificar en PRE**), seguirá pudiendo escribir. El mecanismo que **sí resta** es la `ir.rule` de arriba. El ACL es refuerzo/documentación de intención, **no** la defensa principal. No uses `__export__.*` como referencia de grupo: define el grupo en el módulo `zambudio_permisos` y refiérelo por su xmlid estable. Detalle completo en [[04-blindaje-datos-maestros]].

---

## 5. Alcance y avisos

- **Esto es documentación / propuesta, no un módulo montado.** Los XML y CSV son **plantillas de referencia** para que, cuando se decida materializar, se empaqueten en un módulo `zambudio_permisos` (autor Zambudio) con la debida revisión. No se entrega instalable.
- **Todo toca (o puede tocar) producción.** Cada cambio sigue el ciclo PRE → validación → PRO. Las queries de diagnóstico incluidas son de **solo lectura**; cualquier `UPDATE` se ensaya primero en PRE.
- **xmlids a verificar en PRE.** Se aportan de conocimiento verificado contra el código de Odoo 19, pero deben confirmarse en la BD real antes de referenciarse. En particular:
  - `account.group_account_secured` (asientos asegurados/inalterabilidad), y los grupos Enterprise `hr_appraisal.*`, `hr_attendance.*`, `helpdesk.*`, `repair.*`, `documents.*`, y los de `sale_subscription`.
  - `uom.product_uom_hour` (UdM Horas) y `uom.uom_categ_wtime` (categoría *Working Time*), incluido su `uom_type`.
  - Producto de servicio de partes por defecto: `sale_timesheet.time_product`.
  - Nombres exactos de los campos de *lock dates* en `res.company` v19 (candidatos: `fiscalyear_lock_date`, `tax_lock_date`, `hard_lock_date`, `sale_lock_date`, `purchase_lock_date`; en v18/19 hubo refactor — **confirmar cuáles existen y su ubicación**).
  - `analytic.group_analytic_accounting` (grupo de analítica) y las ACL nativas de `uom.uom`/`product.template`.
- **Modelo de seguridad v19 (breaking changes):**
  - El campo de grupos en `res.users` es **`group_ids`** (+ `all_group_ids` para los heredados vía `implied_ids`); antes era `groups_id`. En dominios y lógica preferir siempre **`user.has_group('modulo.xmlid')`**, que es estable entre versiones.
  - Odoo 19 introduce **`res.groups.privilege`**: `res.groups` ya no cuelga de `category_id` directo, sino de **`privilege_id` → `res.groups.privilege` → `category_id` → `ir.module.category`**. Los grupos custom nuevos deben declarar `privilege_id` (o quedarán sueltos en la UI de Ajustes).
  - El campo m2m de grupos en `ir.rule` **(verificar nombre exacto en PRE: `groups` en versiones previas)** define si la regla es global (vacío) o de grupo.
- **Nada de credenciales** en esta documentación. La gestión de contraseñas del superadmin es procedimiento operativo, fuera del repo.
- **Studio no viaja con código.** Muchas automatizaciones son `base.automation`/`ir.actions.server` creadas en Studio; no se auto-registran ni se despliegan con los módulos. Hay que auditarlas aparte en cada entorno (por eso `auditlog` sobre `base.automation` e `ir.actions.server`, y por eso PRE y PRO pueden divergir en automatizaciones).
- **Backup obligatorio y etiquetado antes de tocar maestros/permisos en PRO.** Antes de **cualquier** cambio de datos maestros o de permisos en PRO es **OBLIGATORIO** un backup manual **verificado y ETIQUETADO** inmediatamente previo al cambio (referencia: [`new/doc/04-backups-y-restauracion.md`](../doc/04-backups-y-restauracion.md), script `/root/backup_odoo19_prod.sh`). RPO objetivo para `grupo_zambudio_prod`: **≤ pocas horas** (el incidente costó ~24 h de trabajo). Prueba de restauración **trimestral** con RTO documentado. Detalle y checklist en [[09-anexo-verificacion-y-checklist]].
- **Riesgo residual — control procedimental, no técnico.** Tras el blindaje, que el **propio custodio** (o una automatización Studio / código en `sudo`) repita el incidente es un control **procedimental**: nada en la BD frena al **uid 1** ni a `sudo`. Refuerzo obligatorio: `auditlog` sobre los maestros y sobre `res.groups`/`ir.rule`/`ir.model.access`/`base.automation`/`ir.actions.server`; alerta `base_automation` ante `write` en `uom.uom` / producto "Horas"; y **revisión OBLIGATORIA de TODAS las automatizaciones Studio** que escriban maestros **antes** de dar el blindaje por cerrado (Studio corre en `sudo` y se salta las record rules). Se declara en [[00-principios-y-gobernanza]] y se refuerza en [[07-auditoria-trazabilidad-hardening]].

---

*Siguiente lectura recomendada: [[00-principios-y-gobernanza]] para el marco operativo, y [[04-blindaje-datos-maestros]] para el corazón técnico del blindaje.*