# 02 · Catálogo de roles / perfiles

> Entregable de gobernanza de permisos — Grupo Zambudio / Aunna IT · Odoo 19 Enterprise · una sola BD multiempresa (AUNNA IT id 1, CITRIC id 2, MONTOYA, ii).
> Este documento define QUIÉN es cada rol y QUÉ grupos Odoo lo componen. El "cómo se blinda" (record rules, `ir.model.access`, campos con `groups=`) va en [[04-blindaje-datos-maestros]] y el aislamiento multiempresa en [[05-record-rules-multiempresa]]. La gobernanza y procedimientos en [[00-principios-y-gobernanza]].

---

## 0. Cómo leer este catálogo (modelo mental de 3 capas)

Un "rol" en Odoo NO es una entidad única: es una **combinación de grupos** (`res.groups`) que, sumados, dan a la persona su menú, sus verbos CRUD y su alcance de registros. La seguridad se compone en tres capas y el catálogo de roles solo controla la primera:

1. **Grupos / nivel de app** (`res.groups`, agrupados por `res.groups.privilege` en v19) → dan el **MENÚ** y el nivel (Ninguno / User / Manager / Administrator).
2. **`ir.model.access`** → dan el **VERBO** (read/write/create/unlink) por modelo. Aquí se decide quién puede *renombrar* o *borrar* `uom.uom` o `product.template`.
3. **`ir.rule`** (record rules) → dan el **ALCANCE** (solo mis documentos, solo mi compañía, solo proyectos donde soy jefe).

**Consecuencia crítica para este catálogo:** los grupos son **aditivos** (vía `implied_ids`) y **no existe "quitar" un permiso metiendo a alguien en otro grupo**. Por eso:
- Asignar el rol correcto (mínimo privilegio) evita *dar de más*.
- Pero **el diseño de roles por sí solo NO habría evitado el incidente** de la UdM/producto *Horas*: un usuario de Inventario o Ventas normalmente ya puede escribir `product.template`, y `uom.uom` la edita `base.group_system`. El blindaje real está en las capas 2 y 3 → [[04-blindaje-datos-maestros]].

> ⚠️ **Cuidado con `implied_ids` heredados (efecto colateral real en v19).** Verificado contra el código fuente de Odoo 19:
> - `project.group_project_manager` **implica** `hr_timesheet.group_hr_timesheet_approver` ("User: all timesheets"). Todo Jefe de Proyecto/Manager de Proyecto aprueba partes por herencia (luego lo acota la record rule de `zambudio_timesheet_approval_by_project`).
> - `hr_timesheet.group_timesheet_manager` ("Administrator" de Partes de horas) **implica `hr.group_hr_user`** → arrastra acceso de gestor a **todos los empleados** (RRHH). No lo asignes a perfiles que en la tabla figuran con RRHH = "–".
> Regla práctica: al elegir un grupo, comprueba su cadena `implied_ids` en PRE (menú *Ajustes › Usuarios › Grupos*, con developer mode) antes de darlo por bueno.

### Regla de oro del catálogo
> **Nivel de app = menú · `ir.model.access` = verbo · `ir.rule` = alcance.**
> Ningún rol funcional lleva `base.group_system`. Ningún rol funcional escribe datos maestros (UdM, productos, plan contable, diarios, cuentas/planes analíticos, secuencias, monedas). Todos arrancan en `base.group_user` + el nivel **User** más bajo de las apps que realmente usan.

### Convenciones
- ⚠ **(verificar en PRE)** = xmlid o comportamiento que NO he podido confirmar contra fuente v19; confírmalo en `grupo_zambudio_prod_pruebas` antes de usarlo en PRO.
- Los xmlids sin ⚠ están verificados contra el código fuente de Odoo 19 o ya en uso en el repo Zambudio.
- **Nombres visibles v19** (verificados contra `base/security/base_groups.xml` de 19.0): `base.group_user` = "Role / User", `base.group_system` = "Role / Administrator", `base.group_portal` = "Role / Portal", `base.group_erp_manager` = "Access Rights", `base.group_no_one` = "Technical Features". El "Administrador" del incidente = `base.group_system`.
- **Cambios de API en v19 (verificados):** en `res.users` el campo de grupos es `group_ids` (y el computado `all_group_ids`), **ya no `groups_id`**. En `res.groups`, `category_id` se sustituye por `privilege_id` → `res.groups.privilege` (y es `res.groups.privilege` quien lleva el `category_id` hacia `ir.module.category`). Para cualquier dominio/automatización sobre grupos, usa **`user.has_group('modulo.xmlid')`**, nunca comparaciones directas sobre `group_ids`.

---

## 0-bis · Jerarquía real de Aunna / Grupo Zambudio

> Los roles **R01–R15** de más abajo son los **bloques funcionales** ("sombreros"): definen qué grupos Odoo da cada función. Esta sección dice **quién de la organización lleva cada sombrero**, según la jerarquía real: **Pablo (Admin/Dev) › CEO › Responsables › Empleados › Becarios**. Es lo que de verdad marcas en la ficha de cada usuario.

```
        ┌─────────────────────────────────────────────┐
        │  Pablo · Administrador + Desarrollador Odoo  │  ← Custodio ÚNICO (fuera de la pirámide):
        │  base.group_system + dev mode + custodio     │     el único que toca datos maestros y Ajustes
        └───────────────────────┬─────────────────────┘
                    ┌───────────┴───────────┐
                    │      CEO / Dirección   │   Nivel 1 · visión global, contabilidad en lectura
                    └───────────┬───────────┘
                    ┌───────────┴───────────┐
                    │      Responsables      │   Nivel 2 · Manager de su área, validan/aprueban
                    └───────────┬───────────┘
                    ┌───────────┴───────────┐
                    │        Empleados       │   Nivel 3 · User, operan su app (imputan horas)
                    └───────────┬───────────┘
                    ┌───────────┴───────────┐
                    │        Becarios        │   Nivel 4 · acceso mínimo, supervisado
                    └───────────────────────┘
        (externos: Clientes / Proveedores = Portal, R15)
```

### Nivel 0 · Pablo — Administrador y Desarrollador Odoo (Custodio ÚNICO)
- **Eres tú.** El **único** con TODOS los permisos. En Aunna, los roles **R13 (Custodio de Datos Maestros) + R14 (Custodio Técnico) recaen en la misma persona: Pablo**.
- **Grupos:** `base.group_system` (Ajustes) · `base.group_erp_manager` (usuarios/accesos) · `base.group_no_one` + **modo desarrollador** · **`zambudio_permisos.group_master_data_custodian`** (único que escribe/borra maestros) · `base.group_multi_company` · `base.group_multi_currency`.
- **Clave:** eres el **único** que puede renombrar/archivar/borrar la UdM, el producto *Horas*, cuentas, diarios, secuencias y monedas. **Todos los demás — CEO incluido — son SOLO LECTURA sobre datos maestros** por el blindaje ([[04-blindaje-datos-maestros]]). Esto es **exactamente** lo que habría frenado el incidente: aquel "administrador" hoy **no estaría en tu grupo custodio** y la regla global le bloquearía el `write`.
- ⚠️ **Bus-factor (importante).** Hoy el custodio eres **solo tú**. **Designa un suplente** con estos mismos grupos (2FA + auditlog) para no depender de una sola persona. Mientras no lo haya, el "doble control" de los cambios críticos lo ejerce el **CEO como testigo** (valida, no ejecuta). El superusuario real (`base.user_root`, uid 1) queda **solo para emergencias**.

### Nivel 1 · CEO / Dirección  → rol funcional **R01**
- Visión global de negocio; contabilidad en **solo lectura**. No toca nada técnico ni datos maestros.
- Grupos: `base.group_user`, `base.group_multi_company`, `sales_team.group_sale_manager`, `purchase.group_purchase_manager`, `stock.group_stock_manager`, `project.group_project_manager`, `account.group_account_readonly`, `analytic.group_analytic_accounting`.
- **NO:** `base.group_system`, modo desarrollador, escribir maestros, editar asientos contables, Ajustes.

### Nivel 2 · Responsables (jefes de departamento)  → **Manager** de su área
Cada responsable lleva el **sombrero funcional de su departamento**, a nivel **Manager** (aprueba/valida), pero **sin** Ajustes ni datos maestros:

| Responsable de… | Rol funcional | Grupo clave (Manager) |
|---|---|---|
| Proyectos | R04 | `project.group_project_manager` (aprueba partes de **sus** proyectos) |
| Compras | R06 (Manager) | `purchase.group_purchase_manager` |
| Almacén / Logística | R07 (Manager) | `stock.group_stock_manager` |
| Administración / Contabilidad | R02 | `account.group_account_user` / `account.group_account_manager` |
| RRHH | R09 | `hr.group_hr_manager` |
| Comercial | R10 (Manager) | `sales_team.group_sale_manager` |
| Soporte / Helpdesk | R12 (Manager) | `helpdesk.group_helpdesk_manager` ⚠ |

- **NO (todos los responsables):** `base.group_system`, modo desarrollador, escribir datos maestros, Ajustes. *Ser Manager de una app **no** te hace dueño de sus maestros* — el catálogo de productos, las UdM y el plan de cuentas siguen siendo **solo de Pablo**.

### Nivel 3 · Empleados  → **User** de su app
- El grupo **más numeroso**. Operan su aplicación a nivel usuario. Sombreros típicos: **R05 Consultor/Técnico** (imputa horas — el flujo del incidente), R03 Facturación, R06/R07/R08 (usuario), R10 comercial (solo sus documentos), R11 Marketing, R12 soporte (usuario).
- Siempre `base.group_user` + nivel **User** de lo que usan (grupos concretos en cada R0x).
- **NO:** Manager de nada por defecto, escribir maestros, Ajustes, borrar registros ajenos, validar/aprobar (salvo lo que su rol concreto permita).

### Nivel 4 · Becarios  → **User restringido** (mínimo y supervisado)
- El perfil **más bloqueado**. Solo lo justo para trabajar supervisados:
  - Proyecto: `project.group_project_user` (solo tareas asignadas).
  - Partes de horas: `hr_timesheet.group_hr_timesheet_user` (solo los suyos).
  - Lo demás: lectura o sin acceso.
- **NO (duro):** Contabilidad, RRHH, Compras/pagos, Ajustes, **modo desarrollador**, `base.group_system`, `base.group_allow_export` (export), `base.group_multi_company`, **Manager de nada**, validar/aprobar, borrar.
- **Refuerzo:** sus partes y tareas los **valida su responsable** (nunca ellos). Recomendado: record rule que les impida `unlink` incluso en sus propios documentos, y no darles CRM/Ventas si no lo necesitan.

### Externos · Clientes y Proveedores  → **Portal (R15)**
- `base.group_portal`, **nunca** `base.group_user`. Solo sus propios pedidos/facturas/proyectos vía web.

### Tabla resumen · Nivel de organización → nivel Odoo
| Nivel org | Nivel Odoo | Ajustes | Dev mode | Datos maestros | Aprueba/valida |
|---|---|---|---|---|---|
| **Pablo** (Admin/Dev) | `base.group_system` + custodio | **SÍ** | **SÍ** | **SÍ (único)** | SÍ |
| CEO / Dirección | Manager (varias apps) + Contab. lectura | NO | NO | NO (lectura) | Según app |
| Responsables | Manager de su área | NO | NO | NO (lectura) | SÍ (su área) |
| Empleados | User de su app | NO | NO | NO (lectura) | Limitado |
| Becarios | User restringido | NO | NO | NO (lectura) | NO |
| Portal (externos) | `base.group_portal` | NO | NO | NO | NO |

> **Regla que resume todo:** solo **Pablo** toca datos maestros y Ajustes. De **CEO para abajo, NADIE** puede renombrar/borrar UdM, productos, cuentas ni diarios — aunque el grupo de su app se lo permitiera de serie, el blindaje de [[04-blindaje-datos-maestros]] lo pone a `write=0`. **Eso** es lo que evita que el incidente se repita.

---

## 1. Los dos "admin" que hay que separar (raíz del incidente)

Antes de los roles funcionales, hay que fijar la separación que causó el incidente:

| Concepto | xmlid | Qué concede | Quién debe tenerlo |
|---|---|---|---|
| **Admin TÉCNICO** (Ajustes) | `base.group_system` | Acceso a *Ajustes*, instalar/activar funciones, menús técnicos, editar datos maestros de sistema (UdM, secuencias, monedas), Studio/`base_automation` | **SOLO Pablo** (Admin/Dev = custodio único; designar 1 suplente). **Ningún otro perfil**, ni CEO. |
| **Admin de accesos** | `base.group_erp_manager` | Crear/editar usuarios y asignarles grupos (sin el resto de Ajustes). Implica `base.group_user` | Custodio técnico; opcionalmente un "gestor de usuarios" delegado |
| **Técnico oculto / developer** | `base.group_no_one` | "Technical Features": desvela campos/menús técnicos (UdM, secuencias, `ir.rule`...) **solo en modo desarrollador**. No da permisos de datos por sí mismo, pero destapa los menús peligrosos | Solo Custodio técnico |
| **Multiempresa** | `base.group_multi_company` | Activa el selector de compañía | Solo perfiles que operan en 2+ compañías |
| **Multi-moneda** | `base.group_multi_currency` | Muestra campos de moneda | Contabilidad / Dirección si aplica |

> **Norma 1.** `base.group_system` es **custodia, no un rol de trabajo**. Administración y Contabilidad NO lo necesitan para su día a día. El incidente = dar `group_system` (o CRUD amplio sobre `product.template`/`uom.uom`) a un perfil funcional.

> **Norma 2.** El modo desarrollador se activa manualmente; los menús técnicos que destapa `base.group_no_one` solo se ven con developer mode encendido. **Prohibido activar developer mode a perfiles funcionales** (procedimiento en [[00-principios-y-gobernanza]]).

> ⚠️ **Matiz importante sobre `base.group_no_one`.** En Odoo `group_no_one` NO es "solo del admin": el framework lo concede de forma efectiva a muchos usuarios en función del developer mode. No lo uses como si fuera una barrera de seguridad — es solo visibilidad de UI. La barrera real de los datos maestros son `ir.model.access` + `ir.rule` (capas 2 y 3). No confíes en "ocultar el menú" para blindar.

---

## 2. Catálogo de roles (15 perfiles)

Para cada rol: descripción · a quién aplica · apps y nivel · grupos (xmlids) · qué NO puede · Ajustes/datos maestros.

> **Por defecto, TODOS los roles funcionales: Ajustes = NO · Datos maestros (escritura) = NO.** Solo se indica lo contrario cuando cambia.

> ⚠️ **Nota sobre "Analítica = lectura".** En v19 existe **un único** grupo analítico, `analytic.group_analytic_accounting` ("Analytic Accounting"): **NO es de solo lectura**, habilita las funciones de analítica (líneas, aplicabilidad, modelos de distribución). El "solo lectura" que pedimos para Dirección/Jefe de Proyecto **no se consigue con este grupo**, sino bloqueando `write/create/unlink` sobre `account.analytic.account` y `account.analytic.plan` en capa 2/3 → [[04-blindaje-datos-maestros]]. Donde el catálogo dice "Analítica *lectura*", entiéndase "ve analítica, pero no puede definir cuentas/planes por blindaje".

---

### R01 · Dirección / Gerencia
- **Descripción:** visión global de negocio (ventas, compras, proyectos, inventario, márgenes) con contabilidad en **solo lectura**.
- **Aplica a:** gerencia, socios, dirección de operaciones.
- **Apps y nivel:** Ventas *Manager*, Compras *Manager*, Inventario *Manager*, Proyecto *Manager*, Partes de horas *all timesheets*, Contabilidad *solo lectura*, Analítica *ve, no define*.
- **Grupos (xmlids):**
  - `base.group_user`, `base.group_multi_company`
  - `sales_team.group_sale_manager` — "Administrator" *(el manager de ventas vive en el módulo `sales_team`, no en `sale`)*
  - `purchase.group_purchase_manager`
  - `stock.group_stock_manager`
  - `project.group_project_manager` *(ya implica `hr_timesheet.group_hr_timesheet_approver` → all timesheets)*
  - `account.group_account_readonly` — "Show Accounting Features - Readonly"
  - `analytic.group_analytic_accounting` — "Analytic Accounting" *(ver nota: no es read-only; se acota en capa 2/3)*
- **NO puede:** editar asientos ni configuración contable (solo lectura); crear/renombrar productos, UdM, diarios, cuentas; entrar en Ajustes.
- **Ajustes / maestros:** NO / NO.

> ⚠️ **Colateral verificado:** NO añadas `hr_timesheet.group_timesheet_manager` a Dirección: implica `hr.group_hr_user` y le daría acceso de gestor a **todos los empleados** (RRHH), lo que contradice la fila R01 (RRHH = "–"). Con `project.group_project_manager` ya obtiene el nivel *approver* de partes; es suficiente para la visión de Dirección.

---

### R02 · Administración / Contabilidad (asesor-contable)
- **Descripción:** lleva la contabilidad completa: asientos, conciliación, impuestos, cierre. Es el perfil contable "de verdad".
- **Aplica a:** responsable de administración, contable interno o asesoría.
- **Apps y nivel:** Contabilidad *completa* (o *Administrator/adviser* para quien lleva el cierre), Facturación, Analítica, Compras *lectura*, Ventas *lectura*.
- **Grupos (xmlids):**
  - `base.group_user`
  - `account.group_account_user` — "Show Full Accounting Features" (contable completo) · **el que hace el cierre**. Si además administra facturación/adviser: `account.group_account_manager` — "Administrator" *(en v19 el nivel contable se elige por privilege: se marca **uno**, el superior implica los inferiores)*
  - `account.group_account_invoice` — "Invoicing" *(implícito por los anteriores)*
  - `analytic.group_analytic_accounting`
  - `purchase.group_purchase_user` (lectura/gestión de facturas proveedor) — *ver SoD §4*
  - `sales_team.group_sale_salesman_all_leads` — "User: All Documents" (lectura de ventas) ⚠ *(o dejar sin ventas si no lo necesita)*
  - Cierres blindados: `account.group_account_secured` — "Show Inalterability Features"
- **NO puede:** dar de alta/renombrar cuentas, diarios, secuencias ni productos (eso es del Custodio de datos maestros); entrar en Ajustes generales; pagar Y comprar a la vez (SoD §4).
- **Ajustes / maestros:** NO / NO — **importante:** el contable NO es el dueño del plan de cuentas ni de los diarios. Puede *usarlos* (crear asientos), no *definirlos*. Ver [[04-blindaje-datos-maestros]].

---

### R03 · Facturación
- **Descripción:** emite y controla facturas de cliente/proveedor sin llevar la contabilidad general.
- **Aplica a:** personal administrativo de facturación.
- **Apps y nivel:** Contabilidad *nivel Invoicing*, Ventas *lectura*.
- **Grupos (xmlids):**
  - `base.group_user`
  - `account.group_account_invoice` — "Invoicing"
  - `sales_team.group_sale_salesman` — "User: Own Documents Only" ⚠ *(o `sales_team.group_sale_salesman_all_leads` si necesita ver todo)*
- **NO puede:** ver funciones contables completas (asientos generales, conciliación), tocar plan de cuentas/diarios, entrar en Ajustes.
- **Ajustes / maestros:** NO / NO.

---

### R04 · Jefe de Proyecto
- **Descripción:** gestiona sus proyectos, planifica y **aprueba los partes de horas de sus proyectos** (encaja con el módulo `zambudio_timesheet_approval_by_project`).
- **Aplica a:** jefes/responsables de proyecto.
- **Apps y nivel:** Proyecto *Manager*, Partes de horas *all timesheets*, Planificación *Manager*, Ventas *usuario*, Analítica *ve, no define*.
- **Grupos (xmlids):**
  - `base.group_user`
  - `project.group_project_manager` *(ya implica `hr_timesheet.group_hr_timesheet_approver`)*
  - `hr_timesheet.group_hr_timesheet_approver` — "User: all timesheets" *(explícito por claridad; es redundante con el anterior, no molesta)*
  - `planning.group_planning_manager` ⚠ *(verificar nombre exacto v19)*
  - `sales_team.group_sale_salesman` — "User: Own Documents Only"
  - `analytic.group_analytic_accounting` *(ver nota: no es read-only)*
- **NO puede:** aprobar partes de proyectos que NO son suyos (lo restringe la record rule de `zambudio_timesheet_approval_by_project`, **no el grupo**: el grupo `approver` da acceso a todos los partes; el filtrado por "soy jefe del proyecto" lo hace la `ir.rule`); crear/renombrar productos ni UdM; contabilizar; Ajustes.
- **Ajustes / maestros:** NO / NO.

> ⚠️ Como el grupo `approver` da por sí mismo *todos* los partes, **confirma en PRE que la record rule de `zambudio_timesheet_approval_by_project` está activa y restringe correctamente** antes de dar este rol en PRO; si la regla no cargara, el jefe podría aprobar partes de proyectos ajenos.

---

### R05 · Consultor / Técnico (imputa horas)
- **Descripción:** el perfil **más numeroso**. Trabaja tareas de proyecto e **imputa partes de horas** (el flujo que rompió el incidente). Es precisamente quien más sufre si se toca la UdM/producto *Horas*.
- **Aplica a:** consultores, técnicos, desarrolladores, cualquiera que fiche horas a proyecto.
- **Apps y nivel:** Proyecto *usuario*, Partes de horas *usuario (solo los suyos)*, Planificación *usuario*.
- **Grupos (xmlids):**
  - `base.group_user`
  - `project.group_project_user`
  - `hr_timesheet.group_hr_timesheet_user` — "User: own timesheets only" *(xmlid verificado y ya en uso en el repo)*
  - `planning.group_planning_user` ⚠ *(verificar nombre exacto v19)*
- **NO puede:** **NADA de datos maestros** — ni escribir productos, UdM, cuentas; no aprueba partes (ni los suyos, si el flujo exige aprobación de un tercero); no ve más proyectos que los asignados; no toca Ajustes. **Sin Manager en nada.**
- **Ajustes / maestros:** NO / NO.

---

### R06 · Responsable de Compras
- **Descripción:** gestiona pedidos de compra y proveedores; recibe mercancía (lectura). SoD: **quien compra no paga ni concilia**.
- **Aplica a:** compras / aprovisionamiento.
- **Apps y nivel:** Compras *usuario* (o *Manager* el responsable), Inventario *lectura de recepciones*, facturas proveedor *lectura*.
- **Grupos (xmlids):**
  - `base.group_user`
  - `purchase.group_purchase_user` (o `purchase.group_purchase_manager` para el responsable)
  - `stock.group_stock_user` (recepción)
  - `purchase.group_warning_purchase` (avisos) · `purchase.group_send_reminder` ⚠ (opcionales)
- **NO puede (SoD crítico):** pagar/conciliar (`account.group_account_manager` prohibido), dar de alta el IBAN del proveedor (separar de tesorería), crear/renombrar productos ni categorías; Ajustes.
- **Ajustes / maestros:** NO / NO.

---

### R07 · Almacén / Inventario
- **Descripción:** operativa de stock: recepciones, entregas, transferencias internas, códigos de barras.
- **Aplica a:** mozos de almacén, responsable de logística.
- **Apps y nivel:** Inventario *usuario* (o *Manager* el responsable), Código de barras.
- **Grupos (xmlids):**
  - `base.group_user`
  - `stock.group_stock_user` (o `stock.group_stock_manager`)
  - Toggles según operativa: `stock.group_production_lot` (lotes/series), `stock.group_stock_multi_locations` (ubicaciones), `stock.group_adv_location` ⚠, `stock.group_tracking_lot` ⚠ *(paquetes)*
- **NO puede:** validar ajustes de inventario / recuentos definitivos si es solo *usuario* (eso es `stock.group_stock_manager`); crear/renombrar productos ni categorías ni UdM; Ajustes.
- **Ajustes / maestros:** NO / NO. **Nota:** editar producto y UdM son datos maestros → Custodio, no almacén. **Ojo:** `stock.group_stock_user` **por defecto sí puede escribir `product.template`**; ese hueco es exactamente el que se cierra en [[04-blindaje-datos-maestros]] (capa 2).

---

### R08 · Producción / Taller
- **Descripción:** órdenes de fabricación y reparaciones (Repair/Taller).
- **Aplica a:** operarios de producción y taller.
- **Apps y nivel:** Fabricación *usuario* (o *Manager*), Taller/Repair *usuario*, Inventario *usuario* (consumos).
- **Grupos (xmlids):**
  - `base.group_user`
  - `mrp.group_mrp_user` (o `mrp.group_mrp_manager`) — *implica `stock.group_stock_user`*
  - `repair.group_repair_user` ⚠ (verificar nombre exacto en v19)
  - Toggles: `mrp.group_mrp_routings` ⚠, `mrp.group_mrp_byproducts` ⚠, `mrp.group_mrp_workorder_dependencies` ⚠
- **NO puede:** definir listas de materiales/rutas si es solo *usuario* (Manager); crear/renombrar productos ni UdM; Ajustes.
- **Ajustes / maestros:** NO / NO.

---

### R09 · RRHH
- **Descripción:** gestión de empleados, ausencias, gastos, evaluaciones, asistencias. Datos personales sensibles → **mínimo número de personas**.
- **Aplica a:** responsable de RRHH y su equipo.
- **Apps y nivel:** Empleados *officer/Manager*, Ausencias *Manager*, Gastos *Manager*, Evaluación *Manager*, Asistencias *Manager*.
- **Grupos (xmlids):**
  - `base.group_user`
  - `hr.group_hr_user` (officer: gestiona todos los empleados) o `hr.group_hr_manager` (Administrator)
  - `hr_holidays.group_hr_holidays_manager` (o `hr_holidays.group_hr_holidays_responsible`) ⚠ *(verificar `_responsible` en v19)*
  - `hr_expense.group_hr_expense_manager`
  - `hr_appraisal.group_hr_appraisal_manager` ⚠
  - `hr_attendance.group_hr_attendance_manager` ⚠ (los nombres officer/manager cambiaron entre versiones)
- **NO puede:** contabilizar (RRHH no lleva contabilidad general); tocar productos/UdM/plan contable; Ajustes generales. Nóminas (si aplica) = rol aparte.
- **Ajustes / maestros:** NO / NO.

---

### R10 · Comercial / CRM / Ventas
- **Descripción:** gestiona oportunidades (CRM) y pedidos de venta.
- **Aplica a:** equipo comercial.
- **Apps y nivel:** Ventas/CRM *usuario* (solo sus documentos por defecto). El responsable comercial, *Manager*.
- **Grupos (xmlids):**
  - `base.group_user`
  - `sales_team.group_sale_salesman` — "User: Own Documents Only" o `sales_team.group_sale_salesman_all_leads` — "User: All Documents"
  - Solo el responsable: `sales_team.group_sale_manager` — "Administrator"
- **NO puede:** ver pedidos ajenos si es "own documents"; crear/renombrar productos, listas de precios ni UdM; contabilizar; Ajustes.
- **Ajustes / maestros:** NO / NO. **Nota:** las listas de precios y el catálogo son maestros → Custodio, no comercial.

---

### R11 · Marketing
- **Descripción:** Email Marketing, SMS Marketing, campañas, sitio web (edición restringida).
- **Aplica a:** equipo de marketing/comunicación.
- **Apps y nivel:** Email/SMS Marketing *usuario*, Sitio web *editor restringido*, CRM *lectura*.
- **Grupos (xmlids):**
  - `base.group_user`
  - `mass_mailing.group_mass_mailing_user` ⚠ (Email Marketing — verificar en v19)
  - Grupo de SMS Marketing (`mass_mailing_sms.*`) ⚠ *(verificar: el módulo SMS puede reutilizar el grupo de `mass_mailing` en lugar de definir uno propio)*
  - `website.group_website_restricted_editor` (edición de contenido, no diseño)
  - `sales_team.group_sale_salesman` — "User: Own Documents Only" (lectura CRM) ⚠
- **NO puede:** publicar cambios estructurales del sitio (eso es `website.group_website_designer`); exportar bases de contactos sin permiso de export (ver [[04-blindaje-datos-maestros]], `base.group_allow_export`); crear productos; Ajustes.
- **Ajustes / maestros:** NO / NO.

---

### R12 · Soporte / Helpdesk
- **Descripción:** atención de tickets (Helpdesk Enterprise), chat en vivo.
- **Aplica a:** equipo de soporte / asistencia.
- **Apps y nivel:** Helpdesk *usuario* (o *Manager* el responsable), Chat en vivo, Proyecto *lectura* si aplica.
- **Grupos (xmlids):**
  - `base.group_user`
  - `helpdesk.group_helpdesk_user` ⚠ (o `helpdesk.group_helpdesk_manager` ⚠) — verificar nombres Enterprise en v19
  - `im_livechat.group_im_livechat_user` ⚠ (o `im_livechat.group_im_livechat_manager` ⚠)
- **NO puede:** configurar equipos/SLA de helpdesk si es solo usuario; crear productos; contabilizar; Ajustes.
- **Ajustes / maestros:** NO / NO.

---

### R13 · Custodio de Datos Maestros *(rol NUEVO a crear)*
- **Descripción:** rol **dedicado** (1-2 personas) que es el **ÚNICO** con write/unlink sobre los datos maestros críticos. Es quien PUEDE renombrar la UdM/producto *Horas*, dar de alta cuentas, diarios, secuencias, monedas — de forma controlada y por procedimiento (ticket + PRE primero). **NO es el superadmin técnico** (no lleva `base.group_system`).
- **Aplica a:** en Aunna, **Pablo** (el Admin/Dev asume también este rol; ver §0-bis). En organizaciones mayores sería un responsable funcional dedicado + suplente. Nunca "de paso" al contable ni al de inventario.
- **Grupos (xmlids):**
  - `base.group_user`
  - **Grupo custom canónico: `zambudio_permisos.group_master_data_custodian`** *(módulo de refuerzo de referencia `zambudio_permisos`; puede crearse por módulo o por UI. Si se crea por UI, su xmlid real se resuelve en PRE → ⚠ **(verificar en PRE)**)*
- **Qué le da el grupo custom** (definido en [[04-blindaje-datos-maestros]]): write/unlink sobre `uom.uom`, `uom.category`, `product.template`, `product.product`, `product.category`, `account.account`, `account.journal`, `account.tax`, `account.analytic.account`, `account.analytic.plan`, `ir.sequence`, `res.currency`. El resto de roles: `read=1, write=create=unlink=0`.
- **NO puede:** entrar en Ajustes generales del sistema, instalar módulos, editar `ir.rule`/`ir.model.access`, tocar Studio (eso es Custodio técnico). Su poder está **acotado a datos maestros de negocio**, no a la infraestructura de seguridad.
- **Ajustes / maestros:** NO (Ajustes) / **SÍ** (maestros de negocio, único rol con este privilegio).

> ⚠️ **Nombre canónico (fuente de verdad).** El xmlid del grupo custodio es **`zambudio_permisos.group_master_data_custodian`**. Cualquier otro nombre visto en versiones previas del corpus (`zambudio_master_data`, `zambudio_custom`, `zambudio_master_data_custody`, `zambudio_master_data_lock`, `zambudio_security_hardening`, `group_master_data_custody`, `group_master_data_custodian` sin prefijo, y cualquier otra variante) es **histórico**: usar siempre el canónico. Este grupo es **funcional**, **NO** implica `base.group_system` y **NO** es el uid 1; las record rules de blindaje lo **re-permiten explícitamente** para que el custodio **SÍ** pueda `write/create/unlink` sobre los maestros mientras el resto solo lee (patrones P1/P2/P3 → [[04-blindaje-datos-maestros]]).

> ⚠️ **Este grupo custom + `ir.model.access` restrictivo son lo que de verdad habría evitado el incidente.** Aviso operativo: el efecto solo es real si **NINGÚN otro grupo** deja `write` sobre esos modelos. Recuerda que `stock.group_stock_user`, `sale.*` y varios más traen `write` sobre `product.template` de serie; hay que **sobreescribir** esos `ir.model.access` a `write=0` (Odoo concede el permiso si CUALQUIER línea `ir.model.access` de los grupos del usuario lo da). Detalle y CSV copiables en [[04-blindaje-datos-maestros]].

---

### R14 · Custodio Técnico / Superadmin
- **Descripción:** administración del sistema: instalar módulos, Ajustes, usuarios y grupos, Studio/`base_automation`, menús técnicos. Es el único que ignora record rules como superusuario en procedimiento controlado.
- **Aplica a:** **Pablo** (Administrador + Desarrollador Odoo) — custodio **único**; **designar 1 suplente** (bus-factor). Credenciales bajo control, actividad auditada (auditlog → [[00-principios-y-gobernanza]]).
- **Grupos (xmlids):**
  - `base.group_system` — "Role / Administrator"
  - `base.group_erp_manager` — "Access Rights" (gestión de usuarios/accesos)
  - `base.group_no_one` — "Technical Features" (menús técnicos con developer mode)
  - `base.group_multi_company`, `base.group_multi_currency`
- **NO puede (por procedimiento, no por permiso):** aplicar cambios directamente en PRO sin pasar por PRE (`grupo_zambudio_prod_pruebas`); trabajar en el día a día con esta cuenta (usar cuenta funcional aparte). El **superusuario real** (`base.user_root`, uid 1) queda reservado a operaciones de emergencia — las record rules NO le aplican, por eso su uso es excepcional y auditado.
- **Ajustes / maestros:** SÍ / SÍ (todo). Es la custodia; ver gobernanza en [[00-principios-y-gobernanza]].

---

### R15 · Portal Cliente / Proveedor *(externo)*
- **Descripción:** acceso externo limitado a sus propios pedidos, proyectos, facturas, tickets vía portal web.
- **Aplica a:** clientes y proveedores externos.
- **Grupos (xmlids):**
  - `base.group_portal` — "Role / Portal"
  - **NUNCA** `base.group_user` (son disjuntos: Odoo impide que un usuario sea portal e interno a la vez).
- **NO puede:** entrar al backend, ver datos de otros clientes (record rules de portal), ver datos maestros, nada interno.
- **Ajustes / maestros:** NO / NO.

---

## 3. Tabla resumen ROL × APPS

Nivel: **U** = Usuario · **M** = Manager/Administrator · **R** = solo lectura · **–** = sin acceso · **C** = custodia (write/unlink maestros).

| Rol \ App | Ventas/CRM | Compras | Inventario | Fabric./Taller | Proyecto | Partes horas | Contab. | Analítica | RRHH | Marketing | Helpdesk | Ajustes | Maestros |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R01 Dirección | M | M | M | – | M | M(apr) | R | ve¹ | – | – | – | – | – |
| R02 Admin/Contab. | R | U | – | – | – | – | M/U | ve¹ | – | – | – | – | – |
| R03 Facturación | R | – | – | – | – | – | U(inv) | – | – | – | – | – | – |
| R04 Jefe Proyecto | U | – | – | – | M | M(apr) | – | ve¹ | – | – | – | – | – |
| R05 Consultor | – | – | – | – | U | U(own) | – | – | – | – | – | – | – |
| R06 Compras | – | U/M | R | – | – | – | – | – | – | – | – | – | – |
| R07 Almacén | – | – | U/M | – | – | – | – | – | – | – | – | – | – |
| R08 Producción | – | – | U | U/M | – | – | – | – | – | – | – | – | – |
| R09 RRHH | – | – | – | – | – | – | – | – | M | – | – | – | – |
| R10 Comercial | U/M | – | – | – | – | – | – | – | – | – | – | – | – |
| R11 Marketing | R | – | – | – | – | – | – | – | – | U | – | – | – |
| R12 Soporte | – | – | – | – | R | – | – | – | – | – | U/M | – | – |
| R13 Custodio Datos | – | – | – | – | – | – | – | – | – | – | – | – | **C** |
| R14 Custodio Técnico | M | M | M | M | M | M | M | M | M | M | M | **SÍ** | SÍ |
| R15 Portal | portal | – | – | – | portal | – | portal | – | – | – | portal | – | – |

¹ "ve" = tiene `analytic.group_analytic_accounting` (ve analítica) pero **no puede definir cuentas/planes** por blindaje de capa 2/3; en v19 no existe un grupo analítico de solo lectura.
> Los niveles M de R14 son inherentes a `base.group_system`; no es un "rol de trabajo", es custodia.

---

## 4. Matriz de incompatibilidades (Segregación de Funciones · SoD)

Combinaciones de grupos que **NO deben acumularse en la misma persona**:

| Nº | Función A | Función B | Por qué |
|---|---|---|---|
| SoD-1 | Compras (`purchase.group_purchase_user`) | Pago/conciliación (`account.group_account_manager`) | Quien pide no paga. |
| SoD-2 | Alta proveedor / cambio IBAN (`base.group_partner_manager`) | Autorización de pago / tesorería | Fraude de desvío de pagos. |
| SoD-3 | Solicitante de gasto | Aprobador de gasto (`hr_expense.group_hr_expense_manager`) | Autoaprobación. |
| SoD-4 | Imputa horas en un proyecto (`hr_timesheet.group_hr_timesheet_user`) | Aprueba partes del mismo proyecto (`hr_timesheet.group_hr_timesheet_approver` sin la record rule por proyecto) | Cubierto por `zambudio_timesheet_approval_by_project` (jefe ≠ imputador). |
| SoD-5 | **Cualquier rol funcional** | `base.group_system` | **Raíz del incidente.** |
| SoD-6 | Custodio de Datos Maestros (R13) | Contable (R02) o Inventario (R07) | El custodio debe ser rol dedicado, no acumulado. |
| SoD-7 | Custodio Técnico (R14) | Cuenta de trabajo diaria | El superadmin no se usa para operar; cuenta funcional aparte. |
| SoD-8 | Comercial que crea pedido | Facturación que lo cobra | Recomendable separar en volúmenes altos ⚠ (según tamaño de equipo). |

> ⚠️ **Recordatorio SoD-4/aprobaciones:** el grupo `approver` concede *todos* los partes; la separación jefe≠imputador la impone la **record rule** de `zambudio_timesheet_approval_by_project`, no el grupo. Si esa regla se desactivara o no cargara, SoD-4 deja de cumplirse. Verificar su carga en PRE.

---

## 5. Normas transversales del catálogo (checklist de asignación)

1. **Arranque mínimo:** todo interno = `base.group_user` + nivel **User** de las apps que usa. Manager solo por necesidad justificada.
2. **`base.group_system` = solo Pablo** (Admin/Dev, custodio único; +1 suplente a designar). Ni CEO, ni responsables, ni empleados, ni becarios.
3. **Developer mode = solo Pablo (custodio).** Prohibido a CEO, responsables, empleados y becarios. Recuerda que `base.group_no_one` es visibilidad de UI, no una barrera de seguridad (ver §1).
4. **`base.group_multi_company` solo a quien opera 2+ compañías.** Pero el control **real** de aislamiento no es este grupo, sino el **`company_ids`** de cada usuario (compañías permitidas) + record rules con `company_id`. Quitar AUNNA de `company_ids` a un usuario de CITRIC impide inyectar la cuenta 90 aunque tuviera el selector → [[05-record-rules-multiempresa]].
5. **Ningún rol funcional escribe datos maestros.** Aunque el grupo de app lo permita (p.ej. `stock.group_stock_user` escribe `product.template`), se **sobreescribe** el `ir.model.access` a `write=0` en capa 2 → [[04-blindaje-datos-maestros]]. (Odoo concede el permiso si CUALQUIER grupo del usuario lo da: no basta con "no darlo", hay que "quitarlo" en todos.)
6. **Portal nunca lleva `base.group_user`** (disjunto).
7. **Al elegir un grupo, revisa su cadena `implied_ids` en PRE** (developer mode): p.ej. `project.group_project_manager` → `hr_timesheet.group_hr_timesheet_approver`, y `hr_timesheet.group_timesheet_manager` → `hr.group_hr_user`. Evita arrastres no deseados.
8. **No asignar grupos sueltos "a mano"** fuera de estos roles. Recomendado evaluar `base_user_role` (OCA) para materializar roles como plantilla y evitar drift — pendiente confirmar port a v19 ⚠ (ver [[00-principios-y-gobernanza]] y catálogo OCA).
9. **Export de datos** controlado por `base.group_allow_export`; no darlo por defecto (fuga de contactos/maestros).
10. **Toda alta/cambio de rol = ticket + PRE primero + doble control.** Procedimiento en [[00-principios-y-gobernanza]].
11. **Revisión periódica** de quién tiene `base.group_system`/`base.group_erp_manager` (query en [[00-principios-y-gobernanza]]).
12. **Automatizaciones/dominios sobre grupos:** usar siempre `user.has_group('modulo.xmlid')`; en v19 el campo en `res.users` es `group_ids` (no `groups_id`) y en `res.groups` la categoría es `privilege_id` → `res.groups.privilege`.

---

## 6. Puntos a verificar en PRE antes de aplicar en PRO

1. Nombres exactos v19 de grupos Enterprise ⚠: `hr_appraisal.*`, `hr_attendance.*` (officer/manager), `helpdesk.*`, `repair.*`, `documents.*`, `mass_mailing*.*`, `im_livechat.*`, y grupos de `sale_subscription` y `planning.*`.
2. **`analytic.group_analytic_accounting` NO es solo lectura** (confirmado en fuente): planificar el bloqueo de `write/create/unlink` sobre `account.analytic.account` y `account.analytic.plan` en capa 2/3 para R01/R02/R04.
3. Confirmar que `account.group_account_readonly` ("Show Accounting Features - Readonly") se expone como opción de UI para R01 (Dirección solo-lectura). *(El grupo existe en v19.)*
4. Verificar en ESTA BD qué grupos traen por defecto `write` sobre `uom.uom` y `product.template` (puede haber sido alterado por módulos custom/Studio), y sobreescribir esos `ir.model.access`.
5. Confirmar el xmlid real del grupo custom del Custodio de Datos Maestros. Nombre **canónico**: `zambudio_permisos.group_master_data_custodian` (los nombres previos como `zambudio_master_data.*` son históricos → no usar). Si el grupo se crea por UI en vez de por módulo, resolver el xmlid efectivo en PRE ⚠ **(verificar en PRE)** — se define en [[04-blindaje-datos-maestros]].
6. Revisar **cadenas `implied_ids`** verificadas: `project.group_project_manager` → `hr_timesheet.group_hr_timesheet_approver`; `hr_timesheet.group_timesheet_manager` → `hr.group_hr_user`. Decidir si esos arrastres son deseados por rol.
7. Confirmar que la record rule de `zambudio_timesheet_approval_by_project` carga y restringe la aprobación al jefe del proyecto (soporte de R04 y SoD-4).

---

*Continúa en [[04-blindaje-datos-maestros]] (record rules + `ir.model.access` + `groups=` copiables), [[05-record-rules-multiempresa]] (AUNNA/CITRIC) y [[00-principios-y-gobernanza]] (procedimientos, custodia, auditlog).*