# 03 — Matriz de permisos por aplicación

> **Qué es este documento.** Recorre **todas** las apps instaladas en la BD del Grupo Zambudio y, para cada una, lista los **grupos reales** (con su `xmlid`) y una tabla **rol → nivel asignado**. Es la traducción operativa del catálogo de roles a "qué marco en la ficha de cada usuario, app por app".
>
> **Cómo se usa.** En Odoo 19 la ficha de usuario muestra un desplegable por *privilegio* (Ninguno / User / Manager / Administrator). Esta matriz te dice qué elegir en cada desplegable para cada rol. Para el blindaje de datos maestros (UdM, productos, cuentas) el desplegable **NO basta**: ver [[04-blindaje-datos-maestros]] y [[05-record-rules-multiempresa]].
>
> **Avisos.**
> - Todo cambio se prueba **primero en PRE** (`grupo_zambudio_prod_pruebas`) y luego a PRO (`grupo_zambudio_prod`).
> - Los `xmlid` marcados **(verificar en PRE)** no los he podido confirmar contra fuente; confírmalos leyendo el `security/*.xml` del módulo antes de referenciarlos en código.
> - En v19 el campo de la ficha de usuario es **`group_ids`** (antes `groups_id`) — **confirmado en fuente v19**. En dominios preferir siempre `user.has_group('xmlid')`.
> - **Modelo de privilegios v19 (confirmado):** `res.groups.category_id` desaparece; ahora cada `res.groups` referencia una `res.groups.privilege` vía **`privilege_id`**, y es la `res.groups.privilege.category_id` la que apunta a `ir.module.category`. Los `res_groups_privilege_*` que se citan abajo son esos registros de privilegio (el "desplegable" de la ficha).
> - **`domain_force` de `ir.rule` se evalúa en RUNTIME**, no al cargar el XML: en él **NO existe `ref()`**. Para referenciar un registro por xmlid dentro de un dominio usa **`user.env.ref('modulo.xmlid').id`**; para comprobar grupo, `user.has_group('modulo.xmlid')`. `ref()` solo es válido en `eval=` de campos como `groups`/`model_id` (tiempo de carga).
> - Nombres visibles cambiados en v19: `base.group_user` = "Role / User"; `base.group_system` = "Role / Administrator" (verificar etiqueta exacta en PRE). No confundir a los usuarios.

Documentos relacionados: [[01-modelo-seguridad-odoo19]] · [[02-catalogo-de-roles]] · [[04-blindaje-datos-maestros]] · [[05-record-rules-multiempresa]] · [[07-auditoria-trazabilidad-hardening]] · [[00-principios-y-gobernanza]]

---

## 0. Leyenda de roles (columnas de las tablas)

Abreviaturas usadas en todas las matrices. El catálogo completo está en [[02-catalogo-de-roles]].

| Abrev. | Rol | Resumen |
|---|---|---|
| **DIR** | Dirección / Gerencia | Visión global, contabilidad en solo-lectura. NO `base.group_system`. |
| **ADM** | Administración / Contabilidad | Contable completo. Sin datos maestros contables en escritura. |
| **JP** | Jefe de Proyecto | Gestiona sus proyectos, aprueba partes de sus proyectos. |
| **CONS** | Consultor / Técnico | Imputa horas. Perfil más numeroso. Mínimo privilegio. |
| **COM** | Comercial | Ventas/CRM. |
| **CMP** | Compras | Pedidos de compra. No paga ni concilia. |
| **ALM** | Almacén / Inventario | Movimientos de stock. |
| **PRO** | Producción / Taller | MRP + Repair. |
| **RRHH** | Recursos Humanos | Empleados, ausencias, gastos, evaluación. |
| **CDM** | Custodio de Datos Maestros | Único con write/unlink sobre maestros. Rol nuevo, grupo funcional custom. xmlid **canónico** = `zambudio_permisos.group_master_data_custodian`. |
| **SYS** | Superadmin / Custodio de Sistema | `base.group_system`. 1 titular + 1 suplente. |

Convenio de celdas:
- `User`, `Manager`, `Admin`, `Officer`, `Approver`, `RO` (read-only) = nivel del desplegable / grupo concreto.
- `—` = Ninguno (no se le da la app).
- `RO` = solo lectura (por grupo específico o por record rule).
- `(cfg)` = requiere además ajuste de configuración; ver notas de la app.

> **Nota de nomenclatura (fuente de verdad).** El grupo custodio (CDM) tiene un único xmlid **canónico**: `zambudio_permisos.group_master_data_custodian` (grupo **funcional**; NO implica `base.group_system` ni es el UID 1; las reglas de blindaje lo re-permiten explícitamente). Cualquier otro nombre en versiones previas de esta documentación (`zambudio_custom`, `zambudio_master_data`, `zambudio_master_data_custody`, `zambudio_master_data_lock`, `zambudio_security_hardening`, `group_master_data_custody`, u otras variantes) es **histórico**: usar siempre el canónico. Si el grupo se crea por UI en lugar de por módulo, su xmlid real se resolverá en PRE **(verificar en PRE)**.

---

## 1. Apps transversales (todos los internos las llevan)

### 1.1 Conversaciones / Discuss (`mail`)
No tiene grupos funcionales propios de nivel; el acceso lo da `base.group_user`. Todos los internos (DIR, ADM, JP, CONS, COM, CMP, ALM, PRO, RRHH, CDM, SYS) lo tienen implícitamente.

- **Nota:** los canales privados y el moderador de canal se gestionan dentro de Discuss, no por grupo de sistema. No requiere matriz.

### 1.2 Calendario (`calendar`)
Sin niveles: lo usa cualquier `base.group_user`. Grupo técnico de interés: `base.group_erp_manager` puede gestionar tipos de cita globales **(verificar en PRE)**. No requiere restricción.

### 1.3 Actividades pendientes (`mail.activity`)
Motor transversal, sin app propia ni grupos de nivel. Cualquier interno crea/cierra actividades sobre los registros que ve. Sin matriz.

### 1.4 Contactos (`contacts`)

| Grupo | xmlid |
|---|---|
| Alta/edición de contactos | `base.group_partner_manager` ("Contact Creation") |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Contactos | User | **Mgr** | User | User (RO reforzado) | **Mgr** | User | User | User | User | Mgr | Mgr |

- **Nota SoD crítica.** `base.group_partner_manager` permite crear/editar el contacto **y su IBAN bancario** (`res.partner.bank`). Quien da de alta proveedores/cambia IBAN **no** debe autorizar pagos (ver Contabilidad). Dáselo a COM (clientes) y a un responsable de CMP, no a todo el mundo.
- **Nota.** Sin `base.group_partner_manager` un interno **igual ve y puede editar** contactos por defecto (el ACL base de `res.partner` es amplio). Si quieres que CONS no toque contactos maestros, refuerza con record rule / ACL — ver [[04-blindaje-datos-maestros]].

---

## 2. Comercial

### 2.1 CRM (`crm`)

| Grupo | xmlid | Da |
|---|---|---|
| Usuario CRM | va incluido con el vendedor (`sales_team.group_sale_salesman`) | Sus leads/oportunidades |
| Manager | `sales_team.group_sale_manager` | Todos los equipos, config |

CRM reutiliza los grupos de `sales_team` (ver Ventas). No tiene desplegable propio separado en la práctica.

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CRM | Mgr | — | — | — | User/All | — | — | — | — | — | — |

### 2.2 Ventas (`sale` / `sales_team`)

Privilegio (v19): `res_groups_privilege_sales` **(verificar el xmlid exacto del privilegio en PRE)**. Grupos (verificados en fuente v19):

| Nivel | xmlid | Alcance |
|---|---|---|
| User: solo sus documentos | `sales_team.group_sale_salesman` | Sus pedidos/leads |
| User: todos los documentos | `sales_team.group_sale_salesman_all_leads` (implica el anterior) | Todos los pedidos |
| Administrador | `sales_team.group_sale_manager` (implica los anteriores) | Config, descuentos, todos |

Toggles de funcionalidad (se activan en Ajustes de Ventas, aplican a todos):
- `product.group_product_variant` — variantes de producto.
- `product.group_product_pricelist` — tarifas.
- `uom.group_uom` — **Unidades de medida** (ver nota abajo). *En v19 el grupo vive en el módulo `uom`; en versiones antiguas era `product.group_uom`. **Verificar en PRE** cuál está presente tras la reestructuración de UoM de v19.*
- `sale.group_discount_per_so_line` **(verificar en PRE)** — descuento por línea.

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ventas | **Mgr** | All (RO) | User | — | User o **All** | — | — | — | — | — | — |

- **⚠ Nota de configuración obligatoria (raíz del incidente).** En **Ajustes → Ventas** hay un check **"Unidades de medida"** que activa `uom.group_uom` para todos. Este toggle **solo cambia la visibilidad de la UI, NO protege el dato**. La UdM "Horas" (`uom.product_uom_hour` — **verificar xmlid en PRE**, ha cambiado de módulo entre versiones) sigue existiendo y `hr_timesheet` la sigue necesitando. **Recomendación:** deja el sub-check de UdM **desactivado** salvo que Compras/Inventario necesiten varias unidades; y **en todo caso** blinda `uom.uom` por permisos (ver [[04-blindaje-datos-maestros]] y §12). Desactivar el check ≠ blindaje.
- **Nota.** DIR como `sales_team.group_sale_manager` para visión global; contabilidad ventas en RO. COM arranca en `sales_team.group_sale_salesman` (solo sus docs) y sube a `_all_leads` solo por necesidad.

### 2.3 Suscripciones (`sale_subscription`)

| Nivel | xmlid | Nota |
|---|---|---|
| Usuario / Manager de suscripciones | `sale_subscription.group_sale_subscription_*` **(verificar en PRE)** | Reutiliza grupos de ventas en gran parte |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Suscripciones | Mgr | RO | — | — | User | — | — | — | — | — | — |

- **Nota.** Verifica en PRE el `xmlid` exacto del grupo (varía entre versiones Enterprise). Las suscripciones tocan facturación recurrente: el que **crea** la suscripción no debe ser el que **concilia** el cobro.

### 2.4 Tableros / Spreadsheet Dashboard (`spreadsheet_dashboard`)

| Nivel | xmlid |
|---|---|
| Usuario dashboards | `spreadsheet_dashboard.group_dashboard_user` **(verificar en PRE)** |
| Gestión de dashboards | `spreadsheet_dashboard.group_dashboard_manager` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Tableros | Mgr | User | User | RO | User | User | User | User | User | — | Mgr |

- **Nota.** Un dashboard puede **exponer datos de todas las compañías** si quien lo diseña tiene varias en el selector. Cuida que los tableros de AUNNA no filtren cifras de CITRIC. La edición del dashboard (fórmulas) solo a perfiles de confianza.

---

## 3. Operaciones (Compra, Inventario, Fabricación, Taller, Barcode)

### 3.1 Compra (`purchase`)

Privilegio: `res_groups_privilege_purchase` **(verificar xmlid del privilegio en PRE)**.

| Nivel | xmlid |
|---|---|
| Usuario | `purchase.group_purchase_user` |
| Administrador | `purchase.group_purchase_manager` |
| Avisos de compra | `purchase.group_warning_purchase` |
| Recordatorio a proveedor | `purchase.group_send_reminder` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Compra | **Mgr** (RO deseable) | User (RO) | — | — | — | User o **Mgr** | User (RO recepción) | User | — | — | — |

- **Nota SoD.** CMP **no** debe llevar `account.group_account_manager` (quien compra no paga/concilia). La factura de proveedor la registra ADM. Alta de IBAN de proveedor: separada (ver Contactos).

### 3.2 Inventario (`stock`) — **APP SENSIBLE**

Privilegio: `res_groups_privilege_inventory` **(verificar xmlid del privilegio en PRE)**.

| Nivel | xmlid |
|---|---|
| Usuario | `stock.group_stock_user` |
| Administrador | `stock.group_stock_manager` |
| Multi-ubicaciones | `stock.group_stock_multi_locations` |
| Multi-almacenes | `stock.group_stock_multi_warehouses` |
| Lotes/nº de serie | `stock.group_production_lot` |
| Seguimiento de paquetes | `stock.group_tracking_lot` |
| Ubicaciones avanzadas | `stock.group_adv_location` |
| Propietario del stock | `stock.group_tracking_owner` |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Inventario | RO | RO | — | — | RO | User (RO) | User o **Mgr** | User | — | — | — |

- **⚠ Nota de configuración crítica (vector del incidente).** Bajo Inventario cuelgan los menús de **Productos, Categorías de producto y Unidades de medida**. Por defecto un `stock.group_stock_user` puede **escribir `product.template`** y a menudo ver el menú de UdM/categorías. Esto es sobreexposición.
  - **Quién ve el menú de Productos/Categorías/UdM:** debe reducirse. La visibilidad de menú se controla en Ajustes → Técnico → Interfaz → Menús (campo `group_ids` del `ir.ui.menu` en v19), pero **ocultar el menú NO impide el acceso por RPC/import**: el blindaje real es ACL + record rule (ver [[04-blindaje-datos-maestros]] y §12).
  - **Escritura sobre `product.template` / `product.product`:** reservar la **modificación/borrado de los productos maestros críticos** a **CDM**. Ojo: bloquear TODA escritura sobre `product.template` rompe la creación rápida de productos desde ventas/compras — usa el patrón **quirúrgico** de §12.2-bis (proteger solo los productos críticos), no un read-only global sobre todo el modelo.
  - **`uom.uom` / `uom.category`:** write/create/unlink **solo CDM** (o superusuario en procedimiento controlado). Las UdM se crean rara vez, así que aquí sí es seguro un bloqueo total del modelo. Ver bloque XML en §12.2.
- **Nota.** Ajustes de inventario y validación de recuentos: solo `stock.group_stock_manager`.
- **Módulos custom que tocan stock** (ver §11): `aunna_stock_negative_control`, `aunna_stock_picking_departments`, `aunna_stock_move_product_category_column`, `aunna_product_labels`, `aunna_stock_picking_analytic_plan`.

### 3.3 Fabricación (`mrp`)

| Nivel | xmlid |
|---|---|
| Usuario | `mrp.group_mrp_user` (implica `stock.group_stock_user`) |
| Administrador | `mrp.group_mrp_manager` |
| Rutas/operaciones | `mrp.group_mrp_routings` |
| Subproductos | `mrp.group_mrp_byproducts` |
| Dependencias de OT | `mrp.group_mrp_workorder_dependencies` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fabricación | RO | — | — | — | — | — | User (RO) | User o **Mgr** | — | — | — |

- **Nota.** Las **listas de materiales (BoM)** son casi datos maestros: su edición debería limitarse a `mrp.group_mrp_manager` o a un responsable de PRO, no a cualquier operario.

### 3.4 Taller / Repair (`repair`)

| Nivel | xmlid |
|---|---|
| Usuario | `repair.group_repair_user` **(verificar en PRE)** |
| Administrador | `repair.group_repair_manager` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Taller/Repair | RO | — | — | — | — | — | User | User o **Mgr** | — | — | — |

- **Nota.** Confirmar `xmlid` en PRE (el módulo repair cambió de estructura de grupos entre versiones; en algunas versiones reutilizaba grupos de stock).

### 3.5 Código de barras (`stock_barcode`)

| Nivel | xmlid |
|---|---|
| Usuario barcode | `stock_barcode.group_barcode_user` **(verificar en PRE)** — normalmente incluido con `stock.group_stock_user` |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Barcode | — | — | — | — | — | User | User | User | — | — | — |

- **Nota.** No maneja datos maestros; hereda del acceso a stock. No requiere blindaje especial.

---

## 4. Contabilidad y analítica — **APP MÁS SENSIBLE**

### 4.1 Contabilidad (`account`)

Privilegio: `res_groups_privilege_accounting` **(verificar xmlid del privilegio en PRE)**. Cadena de implicación (grosso modo; **verificar el encadenamiento exacto en PRE**, cambia entre versiones):

`account.group_account_manager` ⊃ `account.group_account_user` ⊃ `account.group_account_readonly`, y en paralelo los grupos de `account.group_account_basic` / `account.group_account_invoice`.

| Nivel | xmlid | Qué es |
|---|---|---|
| Facturación | `account.group_account_invoice` | Solo facturar |
| Básico | `account.group_account_basic` | Contabilidad básica |
| Solo lectura contable | `account.group_account_readonly` | "Show Accounting Features - Readonly" (auditor/dirección) |
| Contable completo | `account.group_account_user` | "Show Full Accounting Features" |
| Administrador / Adviser | `account.group_account_manager` | Config, plan de cuentas, diarios |
| Inalterabilidad | `account.group_account_secured` **(verificar en PRE)** | Funciones de sellado |
| Validar cuenta bancaria | `account.group_validate_bank_account` **(verificar en PRE)** | — |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Contabilidad | **RO** (`group_account_readonly`) | **User** o **Mgr** | RO analítica | — | — | Invoice (facturas prov., RO deseable) | — | — | — | RO | — |

- **⚠ Nota de gobernanza clave.** `account.group_account_manager` permite **crear/renombrar cuentas contables, diarios, impuestos y posiciones fiscales**. Eso son datos maestros. Decisión de diseño:
  - **Opción A (recomendada):** ADM lleva `account.group_account_user` (contable completo, opera el día a día y cierres), y el **alta/renombrado de plan de cuentas, diarios y secuencias** se reserva a **CDM** (blindaje ACL/record rule sobre `account.account`, `account.journal`, `ir.sequence`). Ver [[04-blindaje-datos-maestros]].
  - **Opción B:** ADM lleva `account.group_account_manager` y se **audita** con `auditlog` sobre `account.account`/`account.journal` (ver [[07-auditoria-trazabilidad-hardening]]).
- **Nota SoD.** Quien **compra** (CMP) no debe conciliar banco. Quien da de alta el IBAN del proveedor no autoriza el pago.
- **Fechas de bloqueo.** Protegen los asientos por fecha (`fiscalyear_lock_date`, `tax_lock_date`, `hard_lock_date`). No protegen el renombrado del plan. Configúralas por compañía; ver [[04-blindaje-datos-maestros]] §5.
- **DIR = solo lectura contable.** Confirmar en PRE que el privilegio de contabilidad expone `group_account_readonly` como opción del desplegable en v19.

### 4.2 Analítica (`analytic`)

| Nivel | xmlid |
|---|---|
| Contabilidad analítica | `analytic.group_analytic_accounting` |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Analítica | User | User | RO | — | — | — | — | — | — | User (write maestro) | — |

- **⚠ Nota multiempresa (fuga cuenta 90).** Las **cuentas analíticas** (`account.analytic.account`) y los **modelos de distribución** (`account.analytic.distribution.model`) deben ser **conscientes de compañía**. La cuenta 90 es de AUNNA (id 1) y la 271 de CITRIC (id 2). Prohibir modelos de distribución con `company_id=False` que referencien cuentas de P&L de compañía. Recuerda que el plan analítico P&L "Horas internas/externas" se ancla en el campo **`x_plan3_id`** de `account.analytic.line`. Detalle y queries en [[05-record-rules-multiempresa]] §7.
- El alta/renombrado de `account.analytic.account` y `account.analytic.plan` → **CDM**. El resto, lectura.

---

## 5. Proyecto, Partes de horas, Planificación

### 5.1 Proyecto (`project`)

| Nivel | xmlid |
|---|---|
| Usuario | `project.group_project_user` |
| Administrador | `project.group_project_manager` |
| Etapas | `project.group_project_stages` **(verificar en PRE)** |
| Hitos | `project.group_project_milestone` **(verificar en PRE)** |
| Dependencias de tareas | `project.group_project_task_dependencies` **(verificar en PRE)** |
| Tareas recurrentes | `project.group_project_recurring_tasks` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Proyecto | **Mgr** | RO | **Mgr** | User | User (RO) | — | — | — | — | — | — |

- **Módulos custom que aplican** (ver §11): `zambudio_project_type`, `zambudio_project_unique_name`, `zambudio_project_sale_naming`, `zambudio_project_billable`. Afectan al alta/nombre de proyectos; el nombre único y el tipo restringen qué puede tocar el JP.

### 5.2 Partes de horas (`hr_timesheet` / `sale_timesheet`) — **crítico para el incidente**

Privilegio: `res_groups_privilege_timesheets` **(verificar xmlid del privilegio en PRE)**. Grupos **verificados en fuente v19**:

| Nivel | xmlid |
|---|---|
| Usuario: solo mis partes | `hr_timesheet.group_hr_timesheet_user` (implica `base.group_user`) |
| Usuario: todos los partes | `hr_timesheet.group_hr_timesheet_approver` (implica `group_hr_timesheet_user`) |
| Administrador | `hr_timesheet.group_timesheet_manager` (implica `group_hr_timesheet_approver` + `hr.group_hr_user`) |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Partes de horas | Mgr | RO | **Approver** | **User** | User | User | User | User | RO | — | — |

- **Nota.** El perfil CONS (el más numeroso) va en `group_hr_timesheet_user` = solo sus partes. La aprobación por JP la gobierna el módulo custom `zambudio_timesheet_approval_by_project` (ver §11): valida partes **solo el jefe del proyecto**, no cualquier approver.
- **Recordatorio del incidente.** Los partes dependen de: (a) la UdM `uom.product_uom_hour` **(verificar xmlid en PRE)**, (b) el **producto de servicio "Horas"** (`type='service'`, `service_policy='delivered_timesheet'`), (c) `res.company.timesheet_encode_uom_id` y `project_time_mode_id`. Renombrar/alterar cualquiera rompe TODOS los partes. Blindaje en §12 y [[04-blindaje-datos-maestros]].
- **Módulo custom:** `zambudio_wip_hide_timesheets` oculta partes en ciertos flujos WIP.

### 5.3 Planificación (`planning`)

| Nivel | xmlid |
|---|---|
| Usuario | `planning.group_planning_user` |
| Administrador | `planning.group_planning_manager` |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Planificación | Mgr | — | **Mgr** | User | — | — | — | PRO:User | RRHH:User | — | — |

---

## 6. Servicio de asistencia (Helpdesk)

### 6.1 Helpdesk (`helpdesk`, Enterprise)

| Nivel | xmlid |
|---|---|
| Usuario | `helpdesk.group_helpdesk_user` **(verificar en PRE)** |
| Administrador | `helpdesk.group_helpdesk_manager` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Helpdesk | Mgr | — | User | User | User | — | — | — | — | — | — |

- **Nota.** Los tickets se asignan por equipo; la visibilidad "solo mis tickets / todos" se controla por equipo + record rule, no solo por grupo. Confirmar `xmlid` y estructura de equipos en PRE.

### 6.2 Chat en vivo (`im_livechat`)

| Nivel | xmlid |
|---|---|
| Operador de chat | `im_livechat.group_im_livechat_user` **(verificar en PRE)** |
| Manager | `im_livechat.group_im_livechat_manager` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Chat en vivo | — | — | — | — | User | — | — | — | — | — | Mgr |

---

## 7. Marketing y Web

### 7.1 Sitio web (`website`)

| Nivel | xmlid |
|---|---|
| Editor restringido | `website.group_website_restricted_editor` |
| Diseñador | `website.group_website_designer` |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sitio web | — | — | — | — | Editor | — | — | — | — | — | Designer |

- **Nota.** `group_website_designer` puede tocar plantillas/vistas QWeb = casi técnico. Restríngelo (COM lleva `restricted_editor` para editar contenido, no plantillas).

### 7.2 Email Marketing (`mass_mailing`)

| Nivel | xmlid |
|---|---|
| Usuario | `mass_mailing.group_mass_mailing_user` **(verificar en PRE)** |
| Manager | `mass_mailing.group_mass_mailing_manager` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Email Marketing | — | — | — | — | User/Mgr | — | — | — | — | — | — |

### 7.3 SMS Marketing (`mass_mailing_sms`)

Reutiliza los grupos de Email Marketing + `sms` nativo. Mismo criterio: solo COM.

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SMS Marketing | — | — | — | — | User | — | — | — | — | — | — |

- **Nota RGPD.** Email/SMS Marketing accede a listas de contactos y consentimientos. Combínalo con restricción de **export** (ver [[07-auditoria-trazabilidad-hardening]] §4, `web_disable_export_group`).

### 7.4 Rastreador de enlaces (`link_tracker`)
Motor transversal usado por marketing/web. Sin grupos de nivel propios relevantes. Acceso ligado a `mass_mailing`/`website`. Sin matriz.

---

## 8. RRHH y personas

### 8.1 Empleados (`hr`)

| Nivel | xmlid |
|---|---|
| Officer: gestiona todos | `hr.group_hr_user` |
| Administrador | `hr.group_hr_manager` |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Empleados | RO | RO | RO | — (solo su ficha) | — | — | — | — | **Mgr** | — | — |

- **Nota privacidad.** Datos personales sensibles → mínimo nº de personas con `hr.group_hr_user`/`_manager`. El resto solo ve su propia ficha (record rule nativa). DIR/ADM en RO si necesitan organigrama.

### 8.2 Evaluación / Appraisal (`hr_appraisal`)

| Nivel | xmlid |
|---|---|
| Usuario | `hr_appraisal.group_hr_appraisal_user` **(verificar en PRE)** |
| Manager | `hr_appraisal.group_hr_appraisal_manager` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Evaluación | RO | — | JP:User (su equipo) | — | — | — | — | — | **Mgr** | — | — |

### 8.3 Asistencias (`hr_attendance`)

| Nivel | xmlid |
|---|---|
| Usuario | (todo empleado fichaje propio, vía `base.group_user`) |
| Officer/Manager | `hr_attendance.group_hr_attendance_manager` **(verificar en PRE — en algunas versiones existe también `group_hr_attendance_officer`)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Asistencias | RO | — | — | (propio) | (propio) | (propio) | (propio) | (propio) | **Mgr** | — | — |

- **Nota.** El grupo de "officer/manager" de asistencias cambió de nombre entre versiones. Verificar en PRE.

### 8.4 Ausencias (`hr_holidays`)

| Nivel | xmlid |
|---|---|
| Usuario | `hr_holidays.group_hr_holidays_user` |
| Responsable | `hr_holidays.group_hr_holidays_responsible` |
| Administrador | `hr_holidays.group_hr_holidays_manager` |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ausencias | RO | — | Responsible (su equipo) | User (propio) | User | User | User | User | **Mgr** | — | — |

- **Nota.** `group_hr_holidays_responsible` = aprueba las de su equipo. Los JP aprueban las de su gente; RRHH administra tipos de ausencia y saldos.
- **Módulo custom:** `aunna_public_holiday_timesheet_bridge` conecta festivos con partes. Sin grupo propio.

### 8.5 Gastos (`hr_expense`)

| Nivel | xmlid |
|---|---|
| Aprobador de equipo | `hr_expense.group_hr_expense_team_approver` |
| Todo aprobador | `hr_expense.group_hr_expense_user` |
| Administrador | `hr_expense.group_hr_expense_manager` |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Gastos | Team approver | **Mgr** (contabiliza) | Team approver | (solo presenta) | (presenta) | (presenta) | (presenta) | (presenta) | User | — | — |

- **Nota SoD.** Separar **quien aprueba** el gasto (JP/DIR sobre su equipo) de **quien lo contabiliza** (ADM). Ningún jefe debe autoaprobarse: revisar en PRE que la jerarquía de aprobación no permita self-approval.

---

## 9. Aprobaciones y utilidades

### 9.1 Aprobaciones (`approvals`)

| Nivel | xmlid |
|---|---|
| Usuario | `approvals.group_approval_user` **(verificar en PRE)** |
| Administrador | `approvals.group_approval_manager` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Aprobaciones | User | User | User | User | User | User | User | User | User | — | Mgr |

- **Nota.** El **administrador de Aprobaciones** define los **tipos de aprobación** (categorías) = configuración. Resérvalo a SYS/CDM o a un responsable, no a todos. Los usuarios solo crean/aprueban solicitudes según su rol en cada tipo.

### 9.2 Documentos (`documents`)

| Nivel | xmlid |
|---|---|
| Usuario | `documents.group_documents_user` **(verificar en PRE)** |
| Administrador | `documents.group_documents_manager` **(verificar en PRE)** |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Documentos | Mgr | User | User | User | User | User | User | User | User | — | Mgr |

- **Nota.** El acceso real a cada carpeta lo dan los **espacios de trabajo** (workspaces) y sus grupos, no solo el grupo de app. La contabilidad y RRHH suelen tener carpetas con acceso restringido: configúralo por workspace. Restringe **borrado de adjuntos** si es preciso (`attachment_delete_restrict` OCA, ver [[07-auditoria-trazabilidad-hardening]]).

---

## 10. Ajustes / Sistema — **MÁXIMA RESTRICCIÓN**

### 10.1 Ajustes (`base` / settings)

| Concepto | xmlid | Qué da |
|---|---|---|
| Admin técnico (Ajustes) | `base.group_system` | Ajustes, instalar/activar apps, menús técnicos, editar maestros de sistema, Studio |
| Admin de accesos | `base.group_erp_manager` | Crear/editar usuarios y asignar grupos |
| Técnico oculto | `base.group_no_one` | Campos/menús developer (solo en modo desarrollador) |
| Multiempresa | `base.group_multi_company` | Selector de compañía |
| Multi-moneda | `base.group_multi_currency` | Activa multi-moneda |
| Permitir exportar | `base.group_allow_export` | Botón Exportar |

| Rol | DIR | ADM | JP | CONS | COM | CMP | ALM | PRO | RRHH | CDM | SYS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `base.group_system` | — | — | — | — | — | — | — | — | — | — | **✔ (1+1)** |
| `base.group_erp_manager` | — | — | — | — | — | — | — | — | — | — | ✔ (opcional a un gestor de usuarios delegado) |
| `base.group_no_one` | — | — | — | — | — | — | — | — | — | — | ✔ |
| `base.group_multi_company` | ✔ | ✔ (si opera 2 cías) | — | — | — | — | — | — | — | — | ✔ |
| `base.group_multi_currency` | según necesidad contable (ADM) | | | | | | | | | | ✔ |
| `base.group_allow_export` | ✔ selectivo | ✔ selectivo | — | — | ✔ selectivo | — | — | — | — | — | ✔ |

- **⚠ Regla nº 1 de gobernanza (raíz del incidente).** `base.group_system` **es custodia, NO un rol de trabajo**. NADIE funcional (ADM, DIR, JP, COM…) debe tenerlo. El "Administrador" que rompió la UdM/producto Horas tenía exactamente este grupo de más. Solo **SYS** (1 titular + 1 suplente).
- **⚠ Aviso importante sobre el alcance real de `base.group_system`.** Retirar este grupo NO basta por sí solo para blindar los maestros: un usuario con `sale.group_sale_manager`, `stock.group_stock_manager` o `account.group_account_manager` **también** puede renombrar producto/UdM/cuentas según los ACL nativos. El grupo de Ajustes es el vector más grave, pero el cierre definitivo es el blindaje de §12 (ACL + record rule global). No des por resuelto el incidente solo quitando `base.group_system`.
- **Nota.** Quitar `base.group_system` a un usuario le retira Ajustes y el store de Apps **pero conserva su trabajo diario** si mantiene sus grupos funcionales. Probar en PRE qué menús concretos desaparecen antes de aplicar en PRO (algunos cuelgan de `group_erp_manager`).
- **Nota exportación.** `base.group_allow_export` no es "todo o nada" trivial: valóralo con `web_disable_export_group`/`base_export_manager` (OCA) para limitar fuga de datos. Ver [[07-auditoria-trazabilidad-hardening]].
- **2FA.** Forzar 2FA nativo al menos para SYS y CDM (Ajustes → Permisos → "Enforce two-factor authentication").

### 10.2 Aplicaciones (Apps store)
Visible solo con `base.group_system`. Sin ese grupo, el usuario final **no ve Apps ni Updates**. Es el mecanismo nativo para "deshabilitar el store" sin módulo. Ver [[07-auditoria-trazabilidad-hardening]] §6.

---

## 11. Módulos CUSTOM — grupos y restricciones propias

| Módulo | Grupo / xmlid | Qué controla | Quién lo recibe |
|---|---|---|---|
| `instalador_modulos_github_v19` (OCA Installer) | **`OCA Installer User`** (xmlid a confirmar, p.ej. `instalador_modulos_github_v19.group_oca_installer_user` — **verificar en PRE**) | Clonar/instalar módulos OCA desde GitHub. **Superpoder**: instala código en la BD. | **SOLO SYS** (1-2 personas). NUNCA funcional. |
| `zambudio_timesheet_approval_by_project` | Sin grupo nuevo: usa `hr_timesheet.group_hr_timesheet_user` + record rule que ata la validación al **jefe de proyecto** | Solo el JP valida los partes de SUS proyectos | JP (vía ser jefe del proyecto) |
| `zambudio_project_type` / `_unique_name` / `_sale_naming` / `_billable` | Sin grupos nuevos; restringen campos/nombres de proyecto | Nombre único, tipo, nombre=pedido-línea, facturable↔productividad | Aplica a JP / Proyecto |
| `zambudio_wip_hide_timesheets` | Sin grupo; oculta partes en flujos WIP | Visibilidad de partes en WIP | Transversal |
| `zambudio_informe_operativo_financiero`, `aunna_wip_accounting`, `aunna_wip_budget_calc`, `aunna_wip_project_link_fix`, `project_delivery_analytic_valuation` | Grupos de acceso al informe/asientos WIP (**verificar xmlid en PRE**) | Informes financieros / asientos WIP | DIR (RO), ADM |
| `aunna_project_cost_account_moves` | **NO instalado** (decisión) | Coste TH | — |
| `aunna_stock_negative_control` | Sin grupo; bloquea stock negativo | Control de stock | ALM |
| `aunna_stock_picking_departments`, `aunna_stock_move_product_category_column`, `aunna_stock_picking_analytic_plan`, `aunna_pyg_hide_total_analytic` | Sin grupos nuevos; columnas/plan analítico en pickings, ocultar total P&L | Ajustes de UI/analítica stock | ALM, ADM |
| `aunna_purchase_order_type` | Sin grupo; tipo de pedido de compra | Clasifica compras | CMP |
| `aunna_product_labels` | Sin grupo; etiquetas de producto | Impresión etiquetas | ALM |
| `aunna_public_holiday_timesheet_bridge` | Sin grupo; festivos↔partes | Puente festivos | Transversal |
| `zambudio_product_company_from_user` | Sin grupo; asigna producto a las `company_ids` del usuario | Coherencia multiempresa de producto | Transversal |

- **⚠ Nota.** El grupo **OCA Installer User** es un vector de riesgo tan grave como `base.group_system`: instala código arbitrario. Trátalo como custodia pura y audítalo (`auditlog` sobre `ir.module.module` / acciones del instalador). Ver [[07-auditoria-trazabilidad-hardening]].
- Los `xmlid` de grupos de los módulos WIP y del instalador **deben verificarse en PRE** leyendo su `security/*.xml`; no los invento aquí.

---

## 12. Bloques de referencia copiables

> Estos ejemplos son **de referencia** para el blindaje que acompaña a la matriz. El entregable es documentación; el detalle completo (con el grupo custodio y todas las reglas) está en [[04-blindaje-datos-maestros]]. Los `xmlid` de modelos del núcleo (`uom.model_uom_uom`, etc.) confirmar en PRE.
>
> **⚠ Principio de partida.** El blindaje de "solo el custodio escribe" se resuelve en DOS capas complementarias, y conviene entender el orden:
> 1. **ACL (`ir.model.access`)** — decide el *verbo* por grupo (read/write/create/unlink). **Las ACL se SUMAN (OR)**: basta que UN grupo del usuario conceda write para que pueda escribir. Es la capa que de verdad quita el write a los funcionales, pero obliga a **sobrescribir por xmlid** las líneas nativas que lo conceden.
> 2. **Record rules (`ir.rule`)** — filtran *qué filas* dentro de lo que la ACL ya permite. Un `ir.rule` **nunca concede** acceso por encima de la ACL; solo lo estrecha. Reglas **globales** (sin `groups`) van en **AND** y se aplican a TODOS; reglas de **grupo** van en **OR** y pueden ampliar acceso entre grupos.

### 12.1 ACL restrictiva: UdM solo lectura para funcionales, custodio full
`ir.model.access.csv` (cabecera exacta v19). Recuerda: como las ACL se suman, para que un funcional NO escriba **ningún** grupo suyo debe conceder write; esto obliga a **sobrescribir las ACL nativas por su `id`/xmlid**, no solo añadir líneas nuevas.

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_uom_uom_readonly_user,uom.uom solo lectura internos,uom.model_uom_uom,base.group_user,1,0,0,0
access_uom_uom_custodian,uom.uom custodio full,uom.model_uom_uom,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_uom_category_readonly_user,uom.category solo lectura,uom.model_uom_category,base.group_user,1,0,0,0
access_uom_category_custodian,uom.category custodio,uom.model_uom_category,zambudio_permisos.group_master_data_custodian,1,1,1,1
```

- **⚠ UdM sí, producto NO por este método.** Bloquear `uom.uom` a read-only para `base.group_user` es seguro (las UdM apenas se crean en el día a día). **Pero no hagas lo mismo con `product.template`/`product.product`**: dejar a `base.group_user` en read-only rompe la **creación rápida de productos** desde ventas/compras y muchos flujos. Para producto, usa el patrón quirúrgico de §12.2-bis.
- **⚠ Override nativo obligatorio.** Añadir estas líneas no elimina las nativas: si `stock`, `sale` o `uom` conceden write a `uom.uom` a otro grupo que el funcional también tenga, la ACL **suma** y podrá escribir. Localiza esas líneas (Ajustes → Técnico → Reglas de acceso, filtrando por modelo `uom.uom`) y ponles write/create/unlink a 0, o redefínelas por su xmlid. Verificar en PRE los xmlids nativos concretos.

### 12.2 Record rule GLOBAL correcta: solo el custodio escribe/crea/borra UdM
> **⚠ Corrección de patrón.** El patrón de "una regla que bloquea a `base.group_user` con dominio falso + otra que re-permite al custodio", ambas atadas a `groups`, **NO es global y NO es infalible**: al llevar `groups` son reglas de **grupo (OR)**, y cualquier otro grupo del usuario con una regla permisiva sobre el mismo modelo las sortearía. Además una regla verdaderamente global con dominio siempre-falso bloquearía **también al custodio**. El patrón correcto para "solo X escribe, sin que ningún grupo lo esquive" es **una única regla GLOBAL** cuyo dominio se decide por usuario con `user.has_group(...)`:

```xml
<record id="uom_lock_write_global" model="ir.rule">
    <field name="name">UdM: solo el custodio escribe/crea/borra</field>
    <field name="model_id" ref="uom.model_uom_uom"/>
    <field name="groups" eval="[]"/> <!-- lista de groups VACÍA => GLOBAL, se aplica a TODOS y va en AND.
         OJO: NO escribir `<field name="global" eval="True"/>`: el campo `global` es CALCULADO
         (global = not groups_id) y de SOLO LECTURA; su eval se ignora y la regla acabaría
         como regla de grupo esquivable vía OR. La forma canónica de "global" es groups eval [] . -->
    <!-- Custodio: dominio siempre verdadero. Resto: siempre falso.
         OJO: en domain_force NO existe ref(); sí user.has_group(). -->
    <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [(0, '=', 1)]</field>
    <field name="perm_read"   eval="False"/> <!-- la regla NO aplica a lectura: TODOS siguen leyendo la UdM -->
    <field name="perm_write"  eval="True"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_unlink" eval="True"/>
</record>
```

- **Por qué es infalible.** Al ser **global** entra en **AND** con cualquier otra regla; ningún grupo la "esquiva" vía OR. Un global falso ⇒ falso pase lo que pase. Ni siquiera `base.group_system` la ignora (solo el superusuario real `__system__`/UID 1 salta las record rules).
- **Por qué no rompe nada.** `perm_read=False` deja la lectura intacta: partes de horas, ventas y compras siguen **leyendo** `uom.uom` sin problema. Solo se cierran write/create/unlink a los no-custodios.
- **Combínala con la ACL (§12.1).** Si la ACL ya niega write a los funcionales, esta regla es defensa en profundidad; si algún grupo conserva write por ACL, esta regla global lo cierra igualmente.
- **⚠ A validar en PRE.** También bloquea `create`/`unlink` de UdM a los no-custodios. Comprueba que ningún flujo automático (importaciones, asistentes) necesite crear UdM en caliente con un usuario funcional.

### 12.2-bis Record rule GLOBAL quirúrgica: proteger solo los PRODUCTOS críticos
Para no romper la alta de productos, no bloquees todo `product.template`: protege únicamente el/los producto(s) maestro(s) críticos (el servicio "Horas", etc.) frente a renombrado/borrado.

```xml
<record id="product_protect_critical_global" model="ir.rule">
    <field name="name">Producto: proteger maestros críticos (write/unlink) salvo custodio</field>
    <field name="model_id" ref="product.model_product_template"/>
    <field name="groups" eval="[]"/> <!-- groups vacío => GLOBAL (AND). NO usar `global eval=True`: es campo calculado de solo lectura. -->
    <!-- Custodio: puede todo. Resto: puede write/unlink de CUALQUIER producto MENOS los protegidos.
         Referenciar por xmlid dentro del dominio con user.env.ref(...).id (ref() NO existe en runtime).
         Si el producto "Horas" nativo no tiene xmlid estable, sustituir por su id numérico real. -->
    <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id', 'not in', [user.env.ref('zambudio_permisos.product_horas_protegido').id])]</field>
    <field name="perm_read"   eval="False"/> <!-- no afecta a lectura -->
    <field name="perm_write"  eval="True"/>
    <field name="perm_create" eval="False"/> <!-- la regla NO aplica a create: se siguen creando productos nuevos con normalidad -->
    <field name="perm_unlink" eval="True"/>
</record>
```

- **Efecto.** Los funcionales crean productos y editan/borran los normales; **no** pueden tocar (write/unlink) los productos de la lista protegida. El custodio, todo.
- **⚠ xmlid del producto "Horas".** El producto de servicio de `sale_timesheet` puede no tener un xmlid estable. Verifica en PRE: si no existe, crea un `<record>` con id propio que lo referencie, o usa el **id numérico** real en el dominio. Si `user.env.ref(...)` no encuentra el xmlid, la regla peta al evaluarse: asegúralo antes de subir a PRO.
- **⚠ Regla GEMELA obligatoria sobre `product.product`.** La regla de arriba protege `product.template`, pero **la variante `product.product` es la que referencia el parte de horas** y la que muchos flujos escriben directamente. Hay que **duplicar la regla global** sobre `product.model_product_product` (mismo `domain_force`, mismos `perm_*`) para que el blindaje sea efectivo; con solo `product.template` el producto "Horas" sigue siendo alterable por su variante. `perm_write=True` cubre además **archivar** (`active=False`), cambiar `type` y `sale_ok`, porque cualquier `write` queda restringido.
- **⚠ Producto "Horas" e ids por compañía.** Hay un producto de servicio "Horas" **por compañía**, con **ids DISTINTOS en PRE y en PRO** (y una fila por AUNNA/CITRIC/MONTOYA/ii). Resuelve los ids en cada BD y usa una **lista**: `[('id','not in',[id1,id2,...])]` (nunca `!=` con un solo id). Alternativas: `user.env.ref('modulo.xmlid').id` si tienen external id estable, o un `post_init_hook` que los localice (`service_policy='delivered_timesheet'` / `default_code`) y les cree el external id. **Nunca** un `ref()` suelto en el dominio.
- **Extensible.** Mete en la lista también el resto de maestros intocables (producto de gastos, etc.).

### 12.3 Seguridad a nivel de campo (blindaje real, pero peligroso en campos centrales)
`groups=` en la **definición del field** es seguridad real (el ORM lo quita por RPC). En la vista es solo visibilidad.

```python
# Patrón (en un módulo custom que herede product.template):
# NO aplicar groups= a 'name' de product.template: 'name' se lee en TODAS partes
# (líneas de pedido, partes de horas, facturas...). Restringirlo dejaría el campo
# como no legible para los no-custodios y ROMPERÍA vistas y flujos en cascada.
```

- **⚠ Regla práctica.** Para maestros centrales (`name` de producto/UdM/cuenta) **NO uses `groups=` en el campo**: prefiere **ACL + record rule** (§12.1 / §12.2 / §12.2-bis), que protegen sin dejar el campo ilegible. Reserva `groups=` para campos **muy concretos y periféricos** que un rol no deba ver ni editar, y pruébalo en PRE porque cualquier vista que muestre ese campo a un no-autorizado dará error o lo ocultará.

### 12.4 Aislamiento multiempresa (patrón canónico para reglas custom)
```xml
<record id="rule_mimodelo_multicompany" model="ir.rule">
    <field name="name">MiModelo multi-company</field>
    <field name="model_id" ref="model_mi_modelo"/>
    <field name="groups" eval="[]"/> <!-- groups vacío => GLOBAL (AND). NO usar `global eval=True`: es campo calculado de solo lectura. -->
    <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
</record>
```
- `company_ids` está disponible en el contexto de evaluación de `domain_force` (compañías activas del usuario). Es el patrón nativo correcto.
- Añade `check_company=True` en todo campo relacional (cuenta, diario, analítica) de cualquier custom que ate documentos a compañía, para que el ORM valide coherencia de compañía. Detalle en [[05-record-rules-multiempresa]].
- **⚠ Cuentas analíticas y modelos de distribución.** Aplica este mismo aislamiento a `account.analytic.account` y `account.analytic.distribution.model`, y **prohíbe** modelos de distribución con `company_id=False` que apunten a cuentas P&L de una compañía (evita que la 90 de AUNNA se cuele en documentos de CITRIC). Ver [[05-record-rules-multiempresa]] §7.

---

## 13. Checklist de aplicación (orden recomendado, todo en PRE primero)

1. **Crear el grupo custodio** `zambudio_permisos.group_master_data_custodian` y asignarlo a 1-2 personas (CDM). Ver [[02-catalogo-de-roles]].
2. **Retirar `base.group_system`** a todo perfil funcional. Dejar solo SYS (titular + suplente). Verificar en PRE qué menús desaparecen.
3. **Retirar el grupo OCA Installer User** a cualquiera que no sea SYS.
4. **Aplicar la matriz app por app** (secciones 1–10) sobre cada usuario real, revisando también quién tiene `*_manager` (sale/stock/account), que también permite tocar maestros.
5. **Blindar maestros** (12.1 / 12.2 / 12.2-bis) sobre `uom.uom`, `uom.category`, los **productos críticos** de `product.template`, `account.account`, `account.journal`, `account.analytic.account/plan`, `ir.sequence`, `res.currency`. Sobrescribir ACL nativas por xmlid. Ver [[04-blindaje-datos-maestros]].
6. **Configurar toggles:** desactivar sub-check de UdM en Ventas si procede; limitar visibilidad de menús Productos/Categorías/UdM en Inventario (`group_ids` del `ir.ui.menu`), recordando que ocultar el menú no blinda el dato.
7. **Ajustar multiempresa:** `company_ids` mínimos por usuario; auditar reglas nativas y modelos de distribución analítica. Ver [[05-record-rules-multiempresa]].
8. **Fechas de bloqueo** contables por compañía.
9. **Auditoría:** activar `auditlog` sobre maestros + modelos de seguridad/automatización; 2FA forzado a SYS/CDM. Ver [[07-auditoria-trazabilidad-hardening]].
10. **Validar flujos reales en PRE** (login de cada rol, partes de horas, facturación WIP, alta de proyecto, creación de producto desde pedido, recepción de compra, creación de UdM controlada por CDM) antes de replicar en PRO.

> **Recordatorio final.** El diseño de roles de esta matriz **por sí solo no habría evitado el incidente**: hace falta el **custodio + ACL/record rules restrictivas** sobre los datos maestros (secciones 3.2, 4 y 12), y recordar que **quitar `base.group_system` no basta** mientras `sale/stock/account_manager` conserven write nativo sobre los maestros. La matriz reparte el menú y el verbo por rol; el blindaje de fila lo cierra §12 y [[04-blindaje-datos-maestros]].