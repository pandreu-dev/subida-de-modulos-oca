# Anexo · Verificacion de xmlids y checklist pre-PRO

> **Que es este documento.** El GATE de cierre del entregable `new/permisos`. Consolida en un solo sitio TODOS los xmlids, ids, campos y nombres de tabla que los documentos 00-08 marcan `(verificar en PRE)`, la checklist imprimible que hay que pasar ANTES de aplicar nada en PRO, y las consultas SQL de verificacion (solo lectura).
>
> **Regla absoluta.** Ningun XML de los documentos 00-08 se pega en PRO hasta que su fila de la seccion 1 este en estado **confirmado**. Un xmlid inventado o un `ref()` a un external id inexistente hace **fallar la instalacion del modulo**. Este anexo es la barrera que lo impide.
>
> **Entornos.** PRE = `erp-pre.zambudio.es` / BD `grupo_zambudio_prod_pruebas`. PRO = `erp.zambudio.es` / BD `grupo_zambudio_prod`. Todas las verificaciones se hacen **primero en PRE**; los ids de registros de datos (producto "Horas", cuentas analiticas) hay que **re-resolverlos ademas en PRO** porque difieren entre entornos.
>
> **Como confirmar un xmlid** (dos vias):
> - **UI:** Ajustes -> Tecnico -> Estructura de la base de datos -> *External Identifiers* (Identificadores externos), buscar por `Complete ID`.
> - **SQL (solo lectura):** `SELECT module, name FROM ir_model_data WHERE module='...' AND name='...';`

---

## 1. Anexo de xmlids / ids / campos a verificar en PRE

Tabla unica. Cada fila es un identificador o campo que aparece marcado `(verificar en PRE)` en algun documento del corpus, mas los conocidos que hay que resolver por dato. **Estado**: `pendiente` (hay que confirmarlo) · `confirmado` (verificado en PRE, listo para PRO) · `NO EXISTE` (inventado, eliminar del corpus).

Leyenda de documentos: **00** principios-y-gobernanza · **01** modelo-seguridad-odoo19 · **02** catalogo-de-roles · **03** matriz-permisos-por-app · **04** blindaje-datos-maestros · **05** record-rules-multiempresa · **06** restricciones-tecnicas-xml · **07** auditoria-trazabilidad-hardening · **08** plan-implementacion-y-runbook · **RM** README.

### 1.1 Conocidos criticos (resolver si o si)

| xmlid / campo | Documento(s) | Query o menu para comprobarlo | Estado |
|---|---|---|---|
| `zambudio_permisos.group_master_data_custodian` (grupo custodio canonico; si se crea por UI su xmlid real cambia) | RM, 00, 01, 02, 03, 04, 06, 07, 08 | `SELECT module,name FROM ir_model_data WHERE model='res.groups' AND name='group_master_data_custodian';` · UI: Ajustes>Tecnico>External Identifiers. **Si se crea por UI, apuntar aqui el xmlid efectivo.** | pendiente |
| `uom.group_uom` (funcion "Manage Multiple Units of Measure"; NO protege el dato, solo la funcion) | RM, 01, 03, 04, 06 | `SELECT module,name FROM ir_model_data WHERE module='uom' AND name='group_uom';` · UI: Ajustes>Usuarios>Grupos, buscar "Unidades de medida" | pendiente |
| `uom.product_uom_hour` (UdM "Horas", modelo `uom.uom`, `noupdate=1`) | RM, 00, 01, 03, 04, 07, 08 | `SELECT res_id FROM ir_model_data WHERE module='uom' AND name='product_uom_hour';` · confirmar tambien `uom_type`/`factor` | pendiente |
| `uom.uom_categ_wtime` (categoria "Working Time"; su ratio 8h=1dia rompe conversiones si se toca) | RM, 04 | `SELECT res_id FROM ir_model_data WHERE module='uom' AND name='uom_categ_wtime';` · confirmar ratio/`uom_type` de cada unidad | pendiente |
| `sales_team.group_sale_manager` (CANONICO para "Administrador de Ventas"; `sale.group_sale_manager` es alias -> NO usar en `ref=`) | 01, 02, 03, 08 | `SELECT module,name FROM ir_model_data WHERE model='res.groups' AND name='group_sale_manager';` (comprobar que el modulo es `sales_team`) | pendiente |
| **`base.res_groups_privilege_administration`** (privilege del custodio en borradores previos) | 04 | **INVENTADO. NO existe en Odoo 19.** `base` solo trae `res_groups_privilege_export`, `res_groups_privilege_contact`, etc.; `base.group_system` no tiene `privilege_id`. Dejar el grupo custodio SIN `privilege_id`, o crear un `res.groups.privilege` propio. | **NO EXISTE** |
| id(es) del **producto "Horas"** `product.template` — uno por compania (AUNNA, CITRIC, MONTOYA, ii), DISTINTO en PRE y PRO | RM, 03, 04, 06, 08 | `SELECT id, company_id, default_code, service_policy FROM product_template WHERE type='service' AND service_policy='delivered_timesheet';` (seccion 3, query S5) | pendiente (PRE y PRO) |
| id(es) del **producto "Horas"** `product.product` (variante, la que usa el parte) — por compania, por entorno | RM, 04, 06, 08 | `SELECT pp.id, pp.product_tmpl_id, pt.company_id FROM product_product pp JOIN product_template pt ON pt.id=pp.product_tmpl_id WHERE pt.service_policy='delivered_timesheet';` | pendiente (PRE y PRO) |
| id de compania **MONTOYA** | 00, 04, 05, 08 | `SELECT id, name FROM res_company ORDER BY id;` | pendiente |
| id de compania **ii** | 00, 04, 05, 08 | `SELECT id, name FROM res_company ORDER BY id;` | pendiente |
| Cuenta P&L de horas de **MONTOYA** (equivalente a la 90 AUNNA / 271 CITRIC) | 04, 05 | `SELECT id, code, name, company_id FROM account_analytic_account WHERE company_id = <id_MONTOYA>;` (identificar/crear la cuenta de horas) | pendiente |
| Cuenta P&L de horas de **ii** (equivalente a la 90 / 271) | 04, 05 | `SELECT id, code, name, company_id FROM account_analytic_account WHERE company_id = <id_ii>;` | pendiente |

### 1.2 Grupos de nucleo / Enterprise a confirmar

| xmlid / campo | Documento(s) | Query o menu para comprobarlo | Estado |
|---|---|---|---|
| `account.group_account_secured` ("Show Inalterability Features") | RM, 01, 02, 03 | `SELECT module,name FROM ir_model_data WHERE module='account' AND name='group_account_secured';` | pendiente |
| `account.group_account_basic` | 01, 03 | idem `name='group_account_basic'` | pendiente |
| `account.group_validate_bank_account` | 01, 03 | idem `name='group_validate_bank_account'` | pendiente |
| `account.group_account_readonly` (Direccion solo-lectura; existe, confirmar que se expone en el selector de la ficha de usuario) | 00, 01, 02, 03, 08 | Ajustes>Usuarios: privilegio Contabilidad, ver opcion "Solo lectura" | pendiente |
| `analytic.group_analytic_accounting` (existe; NO es solo lectura -> el read-only se logra bloqueando write/create/unlink) | 01, 02, 03, 04, 06 | `SELECT module,name FROM ir_model_data WHERE module='analytic' AND name='group_analytic_accounting';` | pendiente |
| `base.group_partner_manager` (gobierna edicion de contacto/IBAN; SoD) | 00, 01, 03 | idem module='base' name='group_partner_manager' | pendiente |
| `base.group_allow_export` (boton Exportar) | RM, 01, 03, 06 | idem name='group_allow_export' | pendiente |
| `base.group_sanitize_override` (confirmar si `base.group_system` lo implica en v19) | 01, 06 | Ajustes>Usuarios>Grupos: abrir `base.group_system`, pestana Heredados/Implied | pendiente |
| `sale.group_discount_per_so_line` | 03 | idem module='sale' | pendiente |
| `purchase.group_send_reminder` | 02, 03 | idem module='purchase' | pendiente |
| `stock.group_adv_location`, `stock.group_tracking_lot` | 02, 03 | idem module='stock' | pendiente |
| `mrp.group_mrp_workorder_dependencies`, `mrp.group_mrp_byproducts` | 02, 03 | idem module='mrp' | pendiente |
| `project.group_project_stages`, `project.group_project_milestone`, `project.group_project_task_dependencies`, `project.group_project_recurring_tasks` | 01, 03 | idem module='project' | pendiente |
| `planning.group_planning_user`, `planning.group_planning_manager` | 02, 03 | idem module='planning' | pendiente |
| `hr_holidays.group_hr_holidays_responsible` (nombre `_responsible` en v19) | 02, 03 | idem module='hr_holidays' | pendiente |
| `hr_expense.group_hr_expense_team_approver` / `_user` / `_manager` | 00, 02, 03 | idem module='hr_expense' | pendiente |
| `hr_appraisal.group_hr_appraisal_user` / `_manager` | 02, 03 | idem module='hr_appraisal' | pendiente |
| `hr_attendance.group_hr_attendance_manager` (y posible `_officer`) | 02, 03 | idem module='hr_attendance' | pendiente |
| `helpdesk.group_helpdesk_user` / `_manager` (Enterprise) | 02, 03 | idem module='helpdesk' | pendiente |
| `im_livechat.group_im_livechat_user` / `_manager` | 02, 03 | idem module='im_livechat' | pendiente |
| `repair.group_repair_user` / `_manager` (Repair rehecho en versiones recientes) | 02, 03, 08 | idem module='repair' | pendiente |
| `documents.group_documents_user` / `_manager` | 01, 03 | idem module='documents' | pendiente |
| `mass_mailing.group_mass_mailing_user` / `_manager` y grupo de SMS (`mass_mailing_sms.*`) | 02, 03 | idem module='mass_mailing' / 'mass_mailing_sms' | pendiente |
| `sale_subscription.group_sale_subscription_*` | 01, 03 | idem module='sale_subscription' | pendiente |
| `approvals.group_approval_user` / `_manager` (y grupos por tipo de aprobacion) | 00, 03 | idem module='approvals' | pendiente |
| `spreadsheet_dashboard.group_dashboard_user` / `_manager` | 03 | idem module='spreadsheet_dashboard' | pendiente |
| `stock_barcode.group_barcode_user` | 03 | idem module='stock_barcode' | pendiente |
| Grupo del instalador OCA (`instalador_modulos_github_v19.group_oca_installer_user` — vector de riesgo, tratar como custodia) | 03 | Leer `security/*.xml` del modulo; `SELECT module,name FROM ir_model_data WHERE model='res.groups' AND module='instalador_modulos_github_v19';` | pendiente |

### 1.3 Modelos (`model_id ref=`) y privilegios v19 a confirmar

| xmlid / campo | Documento(s) | Query o menu para comprobarlo | Estado |
|---|---|---|---|
| `uom.model_uom_category` | 04, 06, 08 | Query S-modelo (seccion 3): `...WHERE m.model='uom.category'` | pendiente |
| `analytic.model_account_analytic_account` | 04, 06 | `...WHERE m.model='account.analytic.account'` | pendiente |
| `analytic.model_account_analytic_plan` | 04, 06 | `...WHERE m.model='account.analytic.plan'` | pendiente |
| `account.model_account_analytic_distribution_model` (puede colgar de `account` o de `analytic`) | 04, 06 | `...WHERE m.model='account.analytic.distribution.model'` | pendiente |
| `res.groups.privilege` propio del custodio (`privilege_id`) — OPCIONAL; si se crea, confirmar su `category_id` (candidato `base.module_category_administration` / `base.module_category_hidden`) | 01, 04, 06, 08 | `SELECT module,name FROM ir_model_data WHERE module='base' AND name LIKE 'module_category_%';` | pendiente |
| Privilegios de app v19 (`res_groups_privilege_sales/_purchase/_inventory/_accounting/_timesheets/_product/_contact/_export`) | 01, 03 | `SELECT module,name FROM ir_model_data WHERE model='res.groups.privilege';` | pendiente |

### 1.4 Campos y nombres de tabla (renombrados v19 / lock dates)

| xmlid / campo | Documento(s) | Query o menu para comprobarlo | Estado |
|---|---|---|---|
| Campo de grupos en `ir.ui.menu` (`group_ids` en v19, era `groups_id`) | 01, 03 | Modo dev: abrir un menu en Ajustes>Tecnico>Interfaz>Menus; o `\d ir_ui_menu` | pendiente |
| Campo m2m de grupos en `ir.rule` (`groups`; confirmar que no cambio) | 01 | `\d ir_rule` / modo dev sobre una `ir.rule` | pendiente |
| Tabla puente usuario-grupo directa (`res_groups_users_rel`, cols `gid`,`uid`) — puede cambiar por rename v19 | 04, 06, 07, 08 | `\d res_groups_users_rel` en psql | pendiente |
| Relacion de membresia **efectiva** (`all_group_ids`, cierre transitivo) — nombre de tabla | 08 | inspeccionar esquema; preferir ORM `search([('all_group_ids','in',...)])` | pendiente |
| Tabla puente usuario-compania (`res_company_users_rel`, cols `user_id`,`cid`) | 05, 08 | `\d res_company_users_rel` | pendiente |
| Tabla puente regla-grupo (`rule_group_rel`) | 06, 08 | `\d rule_group_rel` | pendiente |
| Lock dates en `res.company`: `fiscalyear_lock_date`, `tax_lock_date`, `hard_lock_date`, `sale_lock_date`, `purchase_lock_date` (refactor v18/19) | RM, 00, 03, 04, 06, 08 | Modo dev: `res.company` -> Ver metadatos; o UI Contabilidad>Cierre/Fechas de bloqueo | pendiente |
| Modelo de excepciones de bloqueo `account.lock_exception` (v18+) | 04, 06 | `SELECT model FROM ir_model WHERE model='account.lock.exception';` | pendiente |
| `res.company.timesheet_encode_uom_id` y `res.company.project_time_mode_id` (recodifican el tiempo de TODOS los partes) | 04 | Modo dev sobre `res.company`; Ajustes>Partes de horas | pendiente |
| `account.analytic.line.x_plan3_id` (campo Studio del plan "Horas internas/externas") | 03, 04, 05 | Modo dev: `ir.model.fields` de `account.analytic.line`, buscar `x_plan3_id` | pendiente |

### 1.5 Menus, rutas y credenciales a confirmar

| xmlid / campo | Documento(s) | Query o menu para comprobarlo | Estado |
|---|---|---|---|
| Menus/acciones de UdM: `uom.product_uom_categ_form_action`, `uom.product_uom_form_action` (y menuitems para ocultarlos) | 04, 06 | Query S-menu (seccion 3) filtrando por "unit"/"medida" | pendiente |
| Ruta exacta para **forzar 2FA** (Ajustes>Permisos>"Enforce two-factor authentication"; literal segun traduccion) | RM, 00, 06, 07, 08 | Ajustes>Permisos (con 2FA activo) | pendiente |
| xmlid nativo de las **ACL de `uom.uom`/`product.template`** que conceden `write`/`unlink` (para sobrescribir en capa 2) | 01, 04, 06 | Query S6 (seccion 3) | pendiente |
| `sale_timesheet.time_product` (producto de servicio de partes por defecto; confirmar cual usa cada compania) | RM | `SELECT res_id FROM ir_model_data WHERE module='sale_timesheet' AND name='time_product';` | pendiente |
| **API key de PRE**: caduca **2026-10-12** -> rotar antes | 07 | Query S-apikeys (seccion 3) | pendiente (rotacion) |
| Disponibilidad OCA rama 19.0: `auditlog`, `tracking_manager`, `auth_session_timeout` (CONFIRMADOS 19), `password_security`, `web_disable_export_group`/`base_export_manager`, `base_user_role`, `base_import_security_group` (port a 19 SIN confirmar) | RM, 02, 07, 08 | Revisar repos OCA server-tools/server-auth/web/server-ux rama 19.0 y probar instalacion en PRE | pendiente |

> **Nota de gobernanza (C7).** Ademas de estos identificadores, antes de cerrar el blindaje hay que **inventariar y revisar TODAS las automatizaciones Studio / server actions existentes que escriban datos maestros** (corren en `sudo` y se saltan las `ir.rule`). Ver seccion 2 (fila C7) y query S8 (seccion 3).

---

## 2. GATE pre-produccion (checklist imprimible)

> Se pasa **integramente en PRE** y se deja acta. Ninguna casilla marcada "de palabra": cada una con evidencia (captura, salida de query, ticket). **Si una sola casilla obligatoria queda sin marcar, NO se aplica en PRO.**

### G0 · Requisitos de arranque
- [ ] Todos los identificadores de la **seccion 1** en estado `confirmado` (o `NO EXISTE` y ya eliminados del XML). En particular: grupo custodio, `uom.group_uom`, `uom.product_uom_hour`, `sales_team.group_sale_manager`.
- [ ] Confirmado que **`base.res_groups_privilege_administration` NO se referencia en ningun XML** (esta eliminado; el grupo custodio va sin `privilege_id` o con uno propio).
- [ ] Confirmado que **ningun `domain_force` usa `ref()` suelto** (solo `user.env.ref('modulo.xmlid').id` o listas de ids resueltos). Query S-ref opcional: grep del XML del modulo.
- [ ] ids del **producto "Horas"** resueltos en PRE **y** en PRO, uno por compania (AUNNA, CITRIC, MONTOYA, ii), para `product.template` **y** `product.product`. External ids creados (o `post_init_hook`) antes de que carguen las reglas.

### G1 · Backup DURO (C6) — bloqueante
- [ ] **Backup manual, verificado (restaurable) y ETIQUETADO** hecho **inmediatamente antes** del cambio en PRO. Etiqueta con ticket + fecha/hora + motivo (p.ej. `grupo_zambudio_prod_pre-cambio-permisos-AAAAMMDD_HHMM.sql`).
- [ ] Verificacion de restaurabilidad realizada (restaurar el dump en PRE/entorno aislado, no solo comprobar que el fichero existe). Ref: `new/doc/04-backups-y-restauracion.md`, script `/root/backup_odoo19_prod.sh`.
- [ ] RPO objetivo `grupo_zambudio_prod` <= 4 h configurado (backups automaticos al menos cada 4 h, ademas del manual pre-cambio).
- [ ] Prueba de restauracion **trimestral** con **RTO documentado** (<= 4 h extremo a extremo) al dia; acta archivada.

### G2 · Pruebas de rol manager (el gap real del incidente) — bloqueante
> Con un usuario de prueba de CADA rol manager, iniciar sesion (NO con admin: el superusuario ignora las reglas y da falsos verdes). Confirmar el par "NO puede tocar el maestro / SI puede operar":
- [ ] **Ventas manager (`sales_team.group_sale_manager`):** NO puede renombrar/archivar (`active=False`) el producto "Horas", ni cambiarle `type`/`uom_id`/`sale_ok` -> **debe fallar**; SI puede crear presupuesto y editar/archivar un producto **normal** -> debe funcionar.
- [ ] **Almacen manager (`stock.group_stock_manager`):** NO puede renombrar/archivar el producto "Horas" ni tocar la UdM "Horas"/su categoria -> **debe fallar**; SI puede ajuste de inventario, validar albaran, editar categorias/productos normales -> debe funcionar.
- [ ] **Contabilidad manager (`account.group_account_manager`):** NO puede renombrar/archivar el producto "Horas" ni la UdM "Horas" -> **debe fallar**; SI puede crear factura/asiento y editar plan de cuentas/diarios segun su rol (P2) -> debe funcionar.
- [ ] Intentos repetidos sobre `product.template` **y** sobre la variante `product.product`.
- [ ] El **custodio** (`zambudio_permisos.group_master_data_custodian`) SI puede editar el producto "Horas" y la UdM (via de edicion legitima verificada y documentada).
- [ ] Un usuario con `base.group_system` (simulando al del incidente) **NO** puede renombrar la UdM "Horas" ni convertir el producto en producto de venta.

### G3 · Flujos operativos que NO se deben romper — bloqueante
- [ ] Crear e imputar un **parte de horas** (funciona: la lectura de UdM/producto sigue disponible, `perm_read=False`).
- [ ] **Facturar un proyecto WIP** por partes (`sale_timesheet`) y calculo WIP.
- [ ] Alta y edicion de un **producto normal** por un comercial (sigue funcionando).
- [ ] **Postear una factura** y validar su numeracion (secuencias intactas).
- [ ] Crons / automatizaciones internas (`sudo`) y actualizacion de tasas de moneda siguen operando.

### G4 · Multiempresa — las 4 companias (C8) — bloqueante
- [ ] ids de AUNNA (1), CITRIC (2), **MONTOYA** e **ii** confirmados (query S3).
- [ ] Par de distribucion analitica consciente de compania creado: 90->AUNNA(1), 271->CITRIC(2), y **equivalentes de horas para MONTOYA e ii**.
- [ ] **NINGUNA** de las 4 companias tiene un `account.analytic.distribution.model` con `company_id` **NULL** apuntando a una cuenta de P&L de **otra** compania (query S4, comprobado por id real de cuenta, no por `LIKE '%90%'`). Verificado en PRE **y** PRO.
- [ ] Las ~12 record rules nativas de compania presentes y no huerfanas (query S-multicompany).
- [ ] `check_company=True` en los campos relacionales custom (cuenta/diario/analitica) de los modelos con `company_id`.
- [ ] `company_ids` reducido al minimo por usuario; `base.group_multi_company` solo a quien opera 2+ companias.

### G5 · Automatizaciones Studio (C7) — bloqueante
- [ ] **Inventariadas TODAS las automatizaciones (`base.automation`) y server actions (`ir.actions.server`) que escriben datos maestros** (query S8), documentadas (que escribe, por que, quien la creo) y decididas: conservar / restringir / eliminar.
- [ ] Automatizaciones de distribucion analitica rehechas conscientes de compania (`env.company` -> 90/271/MONTOYA/ii), no contra la 90 fija.
- [ ] El blindaje **NO se declara cerrado** mientras haya una automatizacion Studio sin revisar que escriba maestros.

### G6 · Auditoria y hardening (refuerzo del riesgo residual)
- [ ] `auditlog` (rama 19.0 confirmada) activo sobre maestros + seguridad (`res.groups`, `ir.rule`, `ir.model.access`, `base.automation`, `ir.actions.server`) con cron de purga.
- [ ] Alerta `base.automation` ante `write` en `uom.uom` y en el producto "Horas" (via de notificacion verificada en PRE).
- [ ] 2FA forzado a `base.group_system`, `base.group_erp_manager` y al custodio (enrolados).
- [ ] `auth_session_timeout` con excepcion para usuarios API/integracion.
- [ ] API key de PRE rotada / planificada antes del **2026-10-12**.

### G7 · Gobernanza y cierre
- [ ] Todo probado en PRE con **usuarios de rol** (no admin).
- [ ] **Doble control**: solicitante != aprobador/ejecutor (ticket -> PRE -> validar -> PRO), incluida la desactivacion temporal de cualquier regla global.
- [ ] Blindajes decididos como **codigo versionado** (modulo `zambudio_permisos`) o dato replicado documentado; no quedan solo en la UI de PRO.
- [ ] Runbook de emergencia (doc 08) impreso y accesible; scripts de restore localizados en `new/doc`.
- [ ] Ventana de cambio acordada (fuera de horario intensivo) y usuarios avisados si hay impacto.

---

## 3. Consultas SQL de verificacion (SOLO LECTURA — seguras en PRO)

> **Todas son de solo lectura** (`SELECT`). Ninguna hace `UPDATE`/`DELETE`. Cualquier correccion (setear `company_id`, revertir un renombrado) se ensaya **primero en PRE**. Confirmar en PRE los nombres de tabla puente marcados (`res_groups_users_rel`, `res_company_users_rel`, `rule_group_rel`), que pudieron cambiar con el rename v19; para membresia **efectiva** (con implicados) preferir el ORM `search([('all_group_ids','in', grp.ids)])`.

### S1 · Usuarios con `base.group_system`
```sql
-- Grupo del incidente: acceso a Ajustes + datos maestros de sistema.
-- Solo lista membresia DIRECTA; para la efectiva usar el ORM (all_group_ids).
SELECT u.login, p.name, u.active
FROM res_users u
JOIN res_partner p ON p.id = u.partner_id
JOIN res_groups_users_rel rel ON rel.uid = u.id
JOIN ir_model_data d ON d.res_id = rel.gid AND d.model = 'res.groups'
WHERE d.module = 'base' AND d.name = 'group_system'
ORDER BY u.active DESC, u.login;
```

### S2 · Usuarios con `base.group_erp_manager`
```sql
SELECT u.login, p.name, u.active
FROM res_users u
JOIN res_partner p ON p.id = u.partner_id
JOIN res_groups_users_rel rel ON rel.uid = u.id
JOIN ir_model_data d ON d.res_id = rel.gid AND d.model = 'res.groups'
WHERE d.module = 'base' AND d.name = 'group_erp_manager'
ORDER BY u.active DESC, u.login;
```
> Query combinada (system + erp_manager en una sola pasada):
```sql
SELECT d.module||'.'||d.name AS grupo, u.login, p.name, u.active
FROM res_users u
JOIN res_partner p ON p.id = u.partner_id
JOIN res_groups_users_rel rel ON rel.uid = u.id
JOIN ir_model_data d ON d.res_id = rel.gid AND d.model = 'res.groups'
WHERE (d.module,d.name) IN (('base','group_system'),('base','group_erp_manager'))
ORDER BY grupo, u.login;
```

### S3 · Quien puede hacer `unlink` (y `write`) en `uom.uom` — via ACL
```sql
-- Grupos con perm_unlink/perm_write sobre uom.uom y que usuarios los tienen.
-- Los ACL SUMAN (OR): basta un grupo con el permiso para poder borrar/escribir.
-- group_id NULL = ACL global (lo tiene todo el mundo).
SELECT m.model, a.name AS acl,
       COALESCE(g_d.module||'.'||g_d.name,'(ACL GLOBAL - sin grupo)') AS grupo,
       a.perm_read, a.perm_write, a.perm_create, a.perm_unlink,
       string_agg(u.login, ', ' ORDER BY u.login) AS usuarios
FROM ir_model_access a
JOIN ir_model m ON m.id = a.model_id
LEFT JOIN res_groups g ON g.id = a.group_id
LEFT JOIN ir_model_data g_d ON g_d.res_id = g.id AND g_d.model = 'res.groups'
LEFT JOIN res_groups_users_rel rel ON rel.gid = g.id
LEFT JOIN res_users u ON u.id = rel.uid AND u.active
WHERE m.model = 'uom.uom' AND a.perm_unlink   -- cambiar a "a.perm_write" para escritura
GROUP BY m.model, a.name, grupo, a.perm_read, a.perm_write, a.perm_create, a.perm_unlink
ORDER BY grupo;
```

### S4 · `account.analytic.distribution.model` con `company_id` NULL (fuga cross-company)
```sql
-- Paso 1: id real de las cuentas de horas por compania (90 AUNNA, 271 CITRIC, y MONTOYA/ii).
SELECT id, code, name, company_id
FROM account_analytic_account
WHERE code IN ('90','271')      -- anadir codigos de horas de MONTOYA e ii
ORDER BY company_id;

-- Paso 2: modelos de distribucion SIN compania que referencian esas cuentas por su ID
--         (analytic_distribution es JSONB indexado por id de cuenta, NO por codigo).
--         Sustituir <ID90>/<ID271>/... por los ids del paso 1. Deben salir CERO filas.
SELECT id, company_id, account_prefix, partner_id, product_id, analytic_distribution
FROM account_analytic_distribution_model
WHERE company_id IS NULL
  AND (analytic_distribution ? '<ID90>'
    OR analytic_distribution ? '<ID271>');   -- + ids de MONTOYA/ii
```
> Cribado rapido (tosco, puede dar falsos positivos por texto): `... WHERE company_id IS NULL AND analytic_distribution::text LIKE '%90%';`

### S5 · Producto(s) de horas y su id por compania
```sql
-- product.template "Horas" (servicio facturado por partes), uno por compania.
-- Los ids DIFIEREN entre PRE y PRO: ejecutar en cada entorno.
SELECT pt.id AS tmpl_id, pt.name, pt.default_code, pt.type,
       pt.service_policy, pt.company_id
FROM product_template pt
WHERE pt.type = 'service'
  AND pt.service_policy = 'delivered_timesheet'
ORDER BY pt.company_id;

-- Variante(s) product.product asociada(s) (la que usa el parte de horas):
SELECT pp.id AS variant_id, pp.product_tmpl_id, pt.name, pt.company_id
FROM product_product pp
JOIN product_template pt ON pt.id = pp.product_tmpl_id
WHERE pt.type = 'service'
  AND pt.service_policy = 'delivered_timesheet'
ORDER BY pt.company_id;
```

### Consultas de apoyo del GATE

**S-companias** (ids de AUNNA/CITRIC/MONTOYA/ii):
```sql
SELECT id, name FROM res_company ORDER BY id;
```

**S-multicompany** (inventario de record rules por compania; `global` es palabra reservada -> se cita):
```sql
SELECT r.id, m.model, r.name, r.domain_force, r."global" AS es_global,
       r.perm_read, r.perm_write, r.perm_create, r.perm_unlink
FROM ir_rule r
JOIN ir_model m ON m.id = r.model_id
WHERE r.domain_force ILIKE '%company_id%'
ORDER BY m.model;
```

**S-reglas-globales** (usar el campo calculado `global`, mas robusto que reconstruir joins):
```sql
SELECT r.id, m.model, r.name
FROM ir_rule r JOIN ir_model m ON m.id = r.model_id
WHERE r."global" = true
ORDER BY m.model;
```

**S6 · ACL nativas que conceden write/unlink sobre maestros** (para sobrescribir por xmlid en capa 2):
```sql
SELECT d.module||'.'||d.name AS xmlid, m.model, a.name,
       a.perm_read, a.perm_write, a.perm_create, a.perm_unlink,
       g.name AS grupo
FROM ir_model_access a
JOIN ir_model m ON m.id = a.model_id
LEFT JOIN res_groups g ON g.id = a.group_id
LEFT JOIN ir_model_data d ON d.model='ir.model.access' AND d.res_id=a.id
WHERE m.model IN ('uom.uom','uom.category','product.template','product.product',
                  'account.account','account.journal','ir.sequence','res.currency')
  AND (a.perm_write OR a.perm_unlink)
ORDER BY m.model;
```

**S-modelo** (xmlid real de un modelo, para los `model_id ref=` dudosos):
```sql
SELECT d.module||'.'||d.name AS xmlid, m.model
FROM ir_model m
JOIN ir_model_data d ON d.model='ir.model' AND d.res_id=m.id
WHERE m.model IN ('account.analytic.account','account.analytic.plan',
                  'account.analytic.distribution.model','uom.category');
```

**S-privileges** (privilegios v19 disponibles):
```sql
SELECT d.module||'.'||d.name AS xmlid, pr.name
FROM res_groups_privilege pr
JOIN ir_model_data d ON d.model='res.groups.privilege' AND d.res_id=pr.id
ORDER BY xmlid;
```

**S-menu** (xmlid real de un menu, para ocultarlo por grupo):
```sql
SELECT d.module||'.'||d.name AS xmlid, mnu.name
FROM ir_ui_menu mnu
JOIN ir_model_data d ON d.model='ir.ui.menu' AND d.res_id=mnu.id
WHERE mnu.name::text ILIKE '%unit%' OR mnu.name::text ILIKE '%medida%'
   OR mnu.name::text ILIKE '%secuencia%' OR mnu.name::text ILIKE '%sequence%';
```

**S-company_ids** (usuarios con exceso de companias):
```sql
SELECT u.login, count(rel.cid) AS n_companias,
       string_agg(c.name, ', ' ORDER BY c.id) AS companias
FROM res_users u
JOIN res_company_users_rel rel ON rel.user_id = u.id
JOIN res_company c ON c.id = rel.cid
WHERE u.active
GROUP BY u.login
HAVING count(rel.cid) > 1
ORDER BY n_companias DESC;
```

**S-apikeys** (inventario y caducidad; la de PRE caduca 2026-10-12):
```sql
SELECT k.id, k.name, ru.login, k.scope, k.expiration_date, k.create_date
FROM res_users_apikeys k
JOIN res_users ru ON ru.id = k.user_id
ORDER BY k.expiration_date NULLS FIRST;
```

**S7 · Ultima modificacion de la UdM "Horas"** (quien y cuando; `login` vive en `res_users`, no en `res_partner`):
```sql
SELECT u.id, u.name, ru.login AS ultimo_editor, u.write_date
FROM uom_uom u
LEFT JOIN res_users ru ON ru.id = u.write_uid
WHERE u.id = (SELECT res_id FROM ir_model_data
              WHERE module='uom' AND name='product_uom_hour');   -- verificar xmlid en PRE
```

**S8 · Automatizaciones Studio / server actions que escriben maestros (C7)**:
```sql
-- Automatizaciones base.automation sobre modelos maestros (revisar TODAS).
SELECT ba.id, ba.name, m.model, ba.trigger, ba.active
FROM base_automation ba
JOIN ir_actions_server act ON act.id = ba.action_server_id   -- verificar el nombre del enlace en PRE
JOIN ir_model m ON m.id = act.model_id
WHERE m.model IN ('uom.uom','uom.category','product.template','product.product',
                  'account.account','account.journal','res.currency','ir.sequence',
                  'account.analytic.distribution.model')
ORDER BY ba.active DESC, m.model;

-- Server actions de tipo codigo (Studio) que puedan tocar maestros en sudo.
SELECT act.id, act.name, m.model, act.state
FROM ir_actions_server act
JOIN ir_model m ON m.id = act.model_id
WHERE act.state = 'code'
  AND m.model IN ('uom.uom','product.template','product.product','account.account',
                  'account.analytic.distribution.model');
```

**S-reglas-desactivadas** (alguien pudo apagar un blindaje):
```sql
SELECT r.id, m.model, r.name, r.active, r.write_uid, r.write_date
FROM ir_rule r JOIN ir_model m ON m.id = r.model_id
WHERE r.active = false
ORDER BY r.write_date DESC NULLS LAST;
```

---

*Anexo del entregable `new/permisos`. Fuente de verdad para cerrar el GATE previo a PRO. Al confirmar cada fila de la seccion 1, actualizar su columna "estado" a `confirmado` con la evidencia (identificador real o salida de query). Documentos relacionados: [[08-plan-implementacion-y-runbook]] (runbook y fases), [[04-blindaje-datos-maestros]] (patrones P1/P2/P3), [[00-principios-y-gobernanza]] (norma de backup y riesgo residual).*
