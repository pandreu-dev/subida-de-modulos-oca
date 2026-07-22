# 00 · Principios y gobernanza de accesos

> **Ámbito:** Grupo Zambudio / Aunna IT · Odoo 19 Enterprise · BD multiempresa única (AUNNA IT id 1, CITRIC id 2, MONTOYA, ii).
> **Qué es este documento:** la capa de GOBERNANZA (personas, procedimientos y reglas de decisión). Aquí NO se detalla el XML de cada blindaje: eso vive en [[04-blindaje-datos-maestros]], [[02-catalogo-de-roles]], [[05-record-rules-multiempresa]], [[07-auditoria-trazabilidad-hardening]]. Este documento manda sobre TODOS ellos: si hay conflicto, gana lo escrito aquí.
> **Origen (por qué existe):** un usuario con perfil "Administrador" (`base.group_system`) renombró el producto de servicio *Horas* y alteró la UdM *Horas* (`uom.uom`), rompiendo TODOS los partes de horas y obligando a restaurar un backup del día anterior (se perdió un día de trabajo). No fue un error técnico: fue un fallo de **gobernanza de permisos**. Demasiada gente con `base.group_system` y con escritura sobre datos maestros. Todo lo que sigue existe para que eso no pueda repetirse.

> ⚠️ **Nota v19 (leer antes de tocar nada de grupos).** Odoo 19 cambió el modelo de seguridad respecto a v17/18. Dos cambios que afectan a TODO este esquema y que están **verificados**:
> - `res.groups` ya **no** cuelga de `ir.module.category` por `category_id`. Ahora usa el modelo nuevo **`res.groups.privilege`** a través del campo **`privilege_id`**; es `res.groups.privilege` quien tiene el `category_id` hacia `ir.module.category`. Tenlo presente al crear el grupo custom *Custodio de Datos Maestros* (mecánica en [[02-catalogo-de-roles]]).
> - En `res.users` el campo `groups_id` de v17/18 se renombró a **`group_ids`** (grupos asignados directamente) y existe además **`all_group_ids`** (computado: incluye los grupos heredados vía `implied_ids`). El inverso en `res.groups` pasó de `users` a **`user_ids`**. En dominios, server actions y automatizaciones usa **`user.has_group('xmlid')`**, no leas el campo directamente.
> - Los xmlids de GRUPO estándar (`base.*`, `account.*`, `sale.*`, `stock.*`, etc.) **no** cambiaron de nombre; lo que cambió es cómo se organizan (privilege) y cómo se asignan al usuario (`group_ids`).

---

## 1. Los 8 principios rectores

Estos principios son de obligado cumplimiento. Cualquier excepción se documenta por ticket y la firma un custodio.

1. **Mínimo privilegio.** Cada usuario arranca con `base.group_user` (Internal User) + el nivel **más bajo** (User) de las apps que realmente usa. Manager/Administrator solo cuando la función lo exige y por escrito.
2. **Need-to-know.** El acceso a un dato se concede por necesidad demostrada de la tarea, no por conveniencia, jerarquía ni "por si acaso". Ver documentos, no editarlos, es el default; editar es la excepción.
3. **Separación de funciones (SoD).** Ninguna persona concentra las tres fases de un proceso sensible (iniciar → autorizar → registrar). Detalle y matriz de incompatibilidades en §4.
4. **Separación de los dos "admin".** El **super-admin técnico** (`base.group_system`, custodia) NUNCA es un rol de trabajo diario ni coincide con un administrador funcional de app. Ver §3.
5. **Datos maestros = solo custodio.** UdM, productos de servicio, plan de cuentas, diarios, cuentas y planes analíticos, secuencias, monedas y lock dates: **escritura/borrado exclusivo del Custodio de Datos Maestros** (rol funcional; grupo canónico `zambudio_permisos.group_master_data_custodian`). El resto: solo lectura. Mecánica en [[04-blindaje-datos-maestros]].
6. **PRE antes que PRO, siempre.** Todo cambio de permisos, datos maestros, módulos o automatizaciones se prueba primero en PRE (`erp-pre.zambudio.es`, BD `grupo_zambudio_prod_pruebas`). A PRO solo pasa lo validado, con backup previo y ventana. Ver §6.
7. **Doble control para lo destructivo.** Crear/renombrar/borrar un dato maestro, crear un diario, instalar un módulo, restaurar un backup o conceder `base.group_system`: requieren solicitante + aprobador distintos. Ver §5 y matriz RACI §9.
8. **Todo cambio sensible deja rastro.** Cuentas nominales (nunca compartidas), auditoría activa sobre datos maestros y modelos de seguridad, y revisión periódica. Sin trazabilidad no hay gobernanza. Ver [[07-auditoria-trazabilidad-hardening]].

> 📌 **Nombre canónico del custodio (fuente de verdad).** El rol "Custodio de Datos Maestros" se materializa en el grupo funcional cuyo xmlid CANÓNICO es **`zambudio_permisos.group_master_data_custodian`** *(si el grupo se crea por UI en lugar de por el módulo de refuerzo `zambudio_permisos`, su xmlid real se resuelve en PRE — **verificar en PRE**)*. Este grupo **NO** implica `base.group_system` ni es el superusuario uid 1: es un grupo FUNCIONAL, y las reglas de blindaje lo RE-PERMITEN explícitamente. Cualquier otro nombre en versiones previas de la documentación (`zambudio_custom`, `zambudio_master_data`, `zambudio_master_data_custody`, `zambudio_master_data_lock`, `zambudio_security_hardening`, `group_master_data_custody`, etc.) es **histórico y OBSOLETO**: usar siempre el canónico.

---

## 2. Mínimo privilegio y need-to-know (cómo se aplica en la práctica)

- **Default de alta:** `base.group_user` + nivel User de sus apps. Nada más. Subir de nivel es un cambio de rol (§7), no un ajuste silencioso.
- **"User" significa "solo mis documentos"** en muchas apps de Odoo (regla de registro nativa: p.ej. ventas, CRM, proyecto). No es universal: en Inventario o Compras el nivel User ya ve/opera sobre datos compartidos. Pasar a "todos los documentos" o a Manager se justifica por escrito.
- **La contabilidad de Dirección es de solo lectura** (`account.group_account_readonly` — en Enterprise se expone como "Contabilidad / Solo lectura"; **verificar en PRE** que aparece seleccionable en la UI de Ajustes > Usuarios). Ver el negocio no es operarlo.
- **`base.group_system` no se reparte.** No es "el permiso para poder hacer de todo cuando haga falta": es la custodia del sistema. Un administrador funcional NO lo necesita para su día a día (ver §3 y [[02-catalogo-de-roles]]).
- **Recordatorio técnico clave (raíz del incidente):** el nivel de app NO basta. Un usuario de Inventario o Ventas normalmente puede escribir `product.template`, y `uom.uom` suele ser editable por perfiles amplios (o queda visible al activar el modo desarrollador). El mínimo privilegio real se consigue combinando las 3 capas de Odoo: **grupo** (menú/privilege) + **`ir.model.access`** (verbo CRUD por modelo) + **`ir.rule`** (alcance de filas). Diseño de roles solo NO habría evitado el incidente.

---

## 3. Los dos "admin": super-admin técnico vs administradores funcionales

**El fallo del incidente fue confundir estos dos conceptos.** Deben estar físicamente en personas distintas.

| | Super-admin técnico (Custodio de sistema) | Administrador funcional (por app) |
|---|---|---|
| **Qué es** | `base.group_system` (+ `base.group_erp_manager`, `base.group_no_one`). Da Ajustes, instalar/activar funciones, menús técnicos, editar datos maestros de sistema, Studio/base_automation. | El "Administrator/Manager" de UNA app (p.ej. `sale.group_sale_manager`, `stock.group_stock_manager`, `account.group_account_manager`). |
| **Alcance** | Todo el sistema, transversal. | Solo su app y su operativa. |
| **Cuántas personas** | **Pablo** (Admin + Desarrollador Odoo), custodio **único**. **Designar 1 suplente** (bus-factor). **Nadie más.** | Los que la operativa exija, por app. |
| **Uso diario** | **NO.** Cuenta que NO se usa para trabajar. Solo para tareas de custodia/config, planificadas. | Sí, es su rol de trabajo. |
| **Datos maestros** | Puede tocarlos (pero por procedimiento de doble control, no a discreción). | **NO** puede tocarlos: solo lectura vía `ir.model.access` / `ir.rule`. |

> ℹ️ Nota: `base.group_system` (Ajustes) ya **implica** `base.group_erp_manager` (Derechos de acceso) en el estándar. Listarlos juntos es descriptivo; en la práctica basta con conceder `base.group_system` para el custodio de sistema. `base.group_no_one` se explica en §8.

Reglas duras:
- **`base.group_system` = custodia, no rol de trabajo.** Administración/Contabilidad, Dirección, Jefes de Proyecto, etc. NO lo llevan.
- Un administrador funcional de app **no** obtiene por ello acceso a datos maestros técnicos (UdM, secuencias, monedas): esos son del Custodio de Datos Maestros, aunque sea la misma persona que el custodio de sistema en una organización pequeña. Aun así, se separan como roles (grupos distintos) para poder auditar y delegar.
- **Developer mode (menús técnicos, `base.group_no_one`):** solo custodios. Ver §8.

Tabla completa rol→grupos en [[02-catalogo-de-roles]].

---

## 4. Separación de funciones (SoD)

SoD = ninguna persona controla las tres fases de un proceso: **iniciar → autorizar → registrar/contabilizar**.

### Ejemplo canónico: ciclo de compra
| Fase | Acción | Rol responsable | Grupo Odoo |
|---|---|---|---|
| Iniciar | Crear pedido de compra | Compras | `purchase.group_purchase_user` |
| Autorizar | Aprobar el pedido | Responsable de compras / Aprobaciones | `purchase.group_purchase_manager` / grupos de `approvals` (verificar xmlid exacto en PRE) |
| Recibir | Validar la recepción | Almacén | `stock.group_stock_user` |
| Registrar/pagar | Contabilizar factura y conciliar banco | Contabilidad/Tesorería | `account.group_account_user` / `account.group_account_manager` |

**Quien pide no aprueba, quien recibe no paga, quien da de alta el IBAN del proveedor no autoriza el pago.**

### Ejemplo: ciclo de venta y facturación
Comercial crea el pedido (`sales_team.group_sale_salesman`) → responsable comercial lo valida (`sale.group_sale_manager`) → Contabilidad factura/contabiliza (`account.group_account_user`). El comercial no contabiliza; el contable no modifica el pedido comercial.

### Ejemplo: partes de horas (ya cubierto por custom)
Quien imputa horas (`hr_timesheet.group_hr_timesheet_user`) **no** aprueba sus propios partes. La aprobación la hace el jefe del proyecto vía `zambudio_timesheet_approval_by_project`. Ver [[02-catalogo-de-roles]].

### Matriz de incompatibilidades — qué NO puede acumular una misma persona
| No combinar | Con | Motivo |
|---|---|---|
| Compras (`purchase.group_purchase_user`) | Pago/conciliación (`account.group_account_manager`) | Quien pide no paga |
| Alta de proveedor / cambio de IBAN (`base.group_partner_manager` — verificar en PRE que es el grupo que gobierna la edición del contacto/banco) | Autorización de pago (tesorería) | Fraude de desvío de pagos |
| Solicitante de gasto | Aprobador de gasto (`hr_expense.group_hr_expense_team_approver`) | Auto-aprobación |
| Imputar horas en un proyecto | Aprobar partes de ese proyecto | Cubierto por `zambudio_timesheet_approval_by_project` |
| **Cualquier rol funcional** | **`base.group_system`** | **Raíz del incidente** |
| Custodio de Datos Maestros | Rol "de paso" (contable, inventario, etc.) | El custodio es dedicado, no acumulado |

---

## 5. Doble control para acciones destructivas sobre datos maestros

Toda acción que pueda romper el sistema o corromper datos maestros requiere **dos personas**: un **solicitante** (abre ticket, describe el cambio y el rollback) y un **aprobador/ejecutor** distinto (valida en PRE, ejecuta en PRO con backup).

Aplica obligatoriamente a:
- Crear, renombrar, desactivar o **borrar** una UdM (`uom.uom`) o categoría de UdM (`uom.category`) — **especialmente la UdM *Horas* (`uom.product_uom_hour`)**.
- Crear/renombrar/borrar el **producto de servicio *Horas*** o cambiarle el tipo/UdM/política de facturación.
- Crear o modificar un **diario** (`account.journal`), una **cuenta** (`account.account`), una **cuenta/plan analítico** (`account.analytic.account` / `account.analytic.plan`), una **secuencia** (`ir.sequence`) o una **moneda** (`res.currency`).
- Modificar/crear **modelos de distribución analítica** (`account.analytic.distribution.model`) — vector de la fuga de la cuenta 90 a CITRIC. Ver [[05-record-rules-multiempresa]].
- Modificar **lock dates** contables. **Verificar nombres exactos de campo en PRE** (en v18/19 el bloque se amplió: además de `fiscalyear_lock_date` y `tax_lock_date` existen `sale_lock_date`, `purchase_lock_date` y `hard_lock_date`; comprueba cuáles expone la BD).
- Conceder `base.group_system`, `base.group_erp_manager` o el grupo custodio a cualquier usuario.
- **Restaurar un backup** o cualquier operación a nivel de BD.

Por qué el doble control y no solo permisos: el blindaje técnico (regla `ir.rule` global sobre `uom.uom`, etc., ver [[04-blindaje-datos-maestros]]) deja al custodio como único que puede tocar. El doble control garantiza que ni siquiera el custodio actúe en solitario sobre lo crítico.

> ⚠️ **Aviso multiempresa.** Al blindar datos maestros con `ir.rule` globales, cuida que el dominio no sea "compañía-ciego" cuando el dato SÍ es por compañía (diarios, cuentas, distribución analítica, secuencias). Una regla global mal escrita puede o bien dejar ver datos de otra compañía, o bien bloquear a un usuario legítimo de su propia compañía. Diseño company-aware en [[05-record-rules-multiempresa]].

---

## 6. Gestión del cambio: PRE → PRO

**Regla absoluta: nada toca PRO sin haber pasado por PRE.** Aplica a permisos, datos maestros, módulos, automatizaciones Studio, record rules y lock dates.

Flujo obligatorio:

1. **Ticket.** Solicitante describe: qué cambia, por qué, xmlids/registros afectados, cómo se revierte (rollback).
2. **PRE.** Se aplica en `grupo_zambudio_prod_pruebas`. Se **verifican los xmlids reales** (los marcados "(verificar en PRE)" en los docs se confirman aquí con la query de inventario de reglas — ver [[05-record-rules-multiempresa]] §3).
3. **Prueba funcional real en PRE.** No basta con que "cargue": se ejecutan los flujos reales afectados — como mínimo: crear un parte de horas, facturar un proyecto (WIP), crear pedido→factura, y comprobar que ningún perfil pierde acceso que necesita ni gana acceso indebido. **Probar con un usuario de cada rol impactado**, no solo con el admin (el superusuario ignora las reglas y da falsos verdes — ver §8).
4. **Aprobación.** El aprobador (distinto del solicitante, §5) valida el resultado en PRE.
5. **Backup de PRO OBLIGATORIO, manual, verificado y ETIQUETADO** inmediatamente antes de aplicar (ver norma dura al final de §6). No basta con "que se generó": se verifica que es **restaurable** y se etiqueta con ticket/fecha/hora. Referencia operativa: `new/doc/04-backups-y-restauracion.md`, script `/root/backup_odoo19_prod.sh`. Ver también [[doc-operativa-folder]] / `new/doc`.
6. **Ventana de cambio.** Fuera de horario de trabajo intensivo cuando sea posible; avisar a usuarios si hay impacto.
7. **Aplicar en PRO** y verificación post-cambio (repetir el flujo mínimo del paso 3 en PRO, de nuevo con usuarios de rol, no con admin).
8. **Cierre del ticket** con evidencia y, si aplica, actualización de este esquema de permisos.

Avisos de producción:
- **Studio/base_automation/server actions NO viajan con código.** Un despliegue de módulos no reproduce las automatizaciones; hay que rehacerlas/auditarlas en cada entorno. Es la vía más probable de reintroducir el bug de la cuenta 90 tras un despliegue.
- **Cambios de seguridad por datos, no solo por módulo.** Las modificaciones de `ir.model.access` y `ir.rule` hechas por la UI viven como registros en la BD y **tampoco viajan** con el código si no están en un módulo. Decide para cada blindaje si va en módulo custom (versionado) o como dato de configuración (y entonces se replica manualmente en cada entorno y se documenta).
- **Módulos OCA en BD Enterprise:** pueden afectar la cobertura de soporte oficial y requieren re-port en cada upgrade anual. Instalar solo lo confirmado en 19 y siempre por PRE. Detalle en [[07-auditoria-trazabilidad-hardening]].

### 6.1 Norma de backup (DURA — no negociable)

Esta norma es **dura**: su incumplimiento bloquea el cambio. No es una recomendación.

- **Backup previo OBLIGATORIO.** Antes de **cualquier** cambio de **datos maestros** o de **permisos/seguridad** (`ir.rule`, `ir.model.access`, `res.groups`, concesión de `base.group_system`/`base.group_erp_manager`/grupo custodio) en **PRO**, se ejecuta un backup **manual**, se **verifica que es restaurable** y se **etiqueta** con ticket + fecha/hora + descripción del cambio. Sin ese backup etiquetado y verificado, el cambio **no se aplica**.
- **Referencia operativa:** `new/doc/04-backups-y-restauracion.md`, script `/root/backup_odoo19_prod.sh`. La verificación de restaurabilidad se hace restaurando el dump en PRE/entorno aislado, no solo comprobando que el fichero existe.
- **RPO objetivo para `grupo_zambudio_prod` ≤ 4 horas.** El incidente costó ~24 h de trabajo; el objetivo de punto de recuperación se fija en **como máximo 4 horas** de datos en riesgo (backups automáticos al menos cada 4 h, además del backup manual pre-cambio). Ajustar a la baja si el volumen de imputación diaria lo exige.
- **Prueba de restauración TRIMESTRAL con RTO documentado.** Cada trimestre se realiza una restauración real de prueba y se registra el **RTO** medido (tiempo objetivo de recuperación **≤ 4 horas** de extremo a extremo: desde la decisión de restaurar hasta BD operativa verificada). Se deja acta con el RTO real obtenido y las desviaciones.
- **Responsable:** Custodio de Sistema (ejecuta/aprueba el backup previo y la prueba trimestral); ver matriz RACI §9 (fila "Backup previo verificado y etiquetado" y fila "Restaurar backup").

---

## 7. Ciclo de vida de usuarios

| Evento | Procedimiento | Responsable |
|---|---|---|
| **Alta** | Ticket con rol solicitado + compañías (`company_ids`) donde opera realmente. Alta con `base.group_user` + nivel User de sus apps. 2FA obligatorio (ver §8). Nunca se copia "tal cual" otro usuario sin revisar. | Admin de accesos (`base.group_erp_manager`) |
| **Cambio de rol** | Ticket. Se **retiran** los grupos del rol anterior y se asignan los del nuevo (no acumular). Revisar que no se crea una incompatibilidad SoD (§4). | Admin de accesos + aprobador |
| **Baja** | **Desactivar inmediatamente** (`res.users.active = False`), no borrar (preserva trazabilidad/auditoría). Revocar 2FA, cerrar sesiones y **eliminar API keys** del usuario. Reasignar sus documentos/proyectos si procede. | Admin de accesos |
| **Compañías (`company_ids`)** | Solo las compañías donde la persona opera; y fijar la **compañía por defecto** (`company_id`) coherente. Mínimo privilegio también aplica a compañías: es el control más eficaz contra fugas cross-company (más que cualquier record rule). Ver [[05-record-rules-multiempresa]]. | Admin de accesos |
| **Revisión trimestral** | Auditar quién tiene `base.group_system`/`base.group_erp_manager`, revisar incompatibilidades SoD, usuarios activos sin uso, `company_ids` de más, API keys vivas y sesiones/2FA. Dejar acta. | Custodio + Admin de accesos |

Nota v19: recuerda el rename de campos (`group_ids` / `all_group_ids` en `res.users`; `user_ids` en `res.groups`) descrito en la nota de cabecera. Para comprobar pertenencia a un grupo usa `user.has_group('xmlid')` en vez de leer el campo directamente (verificar comportamiento exacto en PRE).

---

## 8. Developer mode, 2FA y política de la cuenta admin

### Cuenta admin / superusuario
- **Renombrar y nominalizar:** la cuenta de administración se asigna a una persona identificable, no "admin" genérico compartido.
- **No compartir credenciales.** Nunca. Ni "temporalmente".
- **2FA obligatorio** para custodios y para todo lo que lleve `base.group_system` (2FA nativo Odoo, TOTP; verificar en PRE la ruta exacta en Ajustes para forzarlo). Recomendado forzarlo para todos los internos.
- **No usar la cuenta de custodia para trabajo diario.** Si esa persona también trabaja en el sistema, tiene un usuario nominal funcional aparte para el día a día.
- **Ojo con el superusuario real (`base.user_root`, uid 1):** IGNORA todas las record rules e `ir.model.access`. Por eso: (a) el blindaje de datos maestros se apoya en reglas `ir.rule` **globales** (las globales SÍ frenan a un `base.group_system` normal, pero NO al superusuario uid 1); (b) las pruebas de §6 se hacen con usuarios de rol, no con admin, porque el admin no ve los bloqueos; (c) la custodia del root (contraseña, acceso a shell/`odoo-bin`) es crítica y se documenta aparte, sin credenciales aquí.

### Developer mode (menús técnicos / `base.group_no_one`)
- **Solo custodios.** Activar el modo desarrollador no da permisos de datos por sí mismo, pero DESVELA los menús técnicos (UdM, secuencias, categorías, campos) que fueron la vía del incidente. Un `base.group_system` + developer mode ve y toca todo lo técnico.
- Los usuarios funcionales no necesitan ni deben usar developer mode.

### Instalación de módulos
- **Solo custodios**, y **en PRE primero** (§6). Los usuarios finales no llevan `base.group_system`, así que **no ven Apps ni el store** (control nativo). Custodio evalúa, prueba en PRE con flujos reales, y solo entonces PRO.

---

## 9. Matriz RACI de acciones sensibles

**R** = ejecuta · **A** = aprueba/responsable último (uno solo) · **C** = consultado · **I** = informado.
Roles: **CS** = Custodio de Sistema (`base.group_system`) · **CDM** = Custodio de Datos Maestros (grupo funcional custom; xmlid canónico `zambudio_permisos.group_master_data_custodian` — *verificar en PRE*) · **AA** = Admin de Accesos (`base.group_erp_manager`) · **AF** = Admin Funcional de la app · **DIR** = Dirección.

| Acción sensible | CS | CDM | AA | AF | DIR |
|---|---|---|---|---|---|
| Crear/renombrar/borrar **UdM** (`uom.uom`, cat.) | A | R | — | I | I |
| Crear/renombrar/borrar **producto de servicio *Horas*** | A | R | — | C | I |
| Crear/modificar **diario** (`account.journal`) | A | R | — | C (contable) | I |
| Crear/modificar **cuenta** (`account.account`) | A | R | — | C (contable) | I |
| Crear/modificar **cuenta/plan analítico** | A | R | — | C | I |
| Modificar **modelo de distribución analítica** | A | R | — | C | I |
| Crear/modificar **secuencia** (`ir.sequence`) | A/R | C | — | — | I |
| Crear/modificar **moneda** (`res.currency`) | A/R | C | — | — | I |
| Modificar **lock dates** contables | C | — | — | A/R (contable resp.) | I |
| **Instalar/actualizar módulo** | A/R | — | — | C | I |
| **Backup previo verificado y etiquetado** (obligatorio pre-cambio, §6.1) | A/R | C | — | — | I |
| **Restaurar backup** | A/R | C | — | I | I |
| **Conceder `base.group_system` / `base.group_erp_manager`** | A | — | R | — | C |
| Conceder grupo **Custodio de Datos Maestros** | A | — | R | — | C |
| **Alta/baja/cambio de rol** de usuario | C | — | A/R | C | I |
| Asignar/ampliar **`company_ids`** de un usuario | C | — | A/R | C | I |
| Crear/editar **automatización Studio / server action** | A/R | C | — | C | I |
| **Aprobar pedido de compra** | — | — | — | A/R (compras mgr) | I |
| **Contabilizar factura / conciliar banco** | — | — | — | A/R (contable) | I |
| Cambio de **record rule / `ir.model.access`** | A/R | C | C | C | I |

Notas:
- Toda fila con **A ≠ R** materializa el **doble control** (§5): quien ejecuta no es quien aprueba.
- Donde CS aparece como **A/R** (secuencias, moneda, backup, módulos), sigue exigiéndose ticket con solicitante distinto salvo que CS y el solicitante coincidan por tamaño de organización; en ese caso, DIR queda como **C** para no dejar la acción sin segundo par de ojos.
- **Coherencia con §5:** conceder `base.group_erp_manager` es acción de doble control igual que `base.group_system` (por eso comparten fila: CS aprueba, AA ejecuta).
- En organización pequeña, CS y CDM pueden ser la misma persona, pero se mantienen como **grupos distintos** para auditar por separado y poder delegar.

---

## 10. Riesgo residual (lo que el blindaje técnico NO cubre)

**Declaración explícita:** incluso tras aplicar el blindaje de datos maestros ([[04-blindaje-datos-maestros]]), **queda un riesgo residual que es PROCEDIMENTAL, no técnico**. Nada en la base de datos frena a quien opera por encima de las `ir.rule`:

- El **superusuario uid 1** (`base.user_root`) ignora todas las record rules e `ir.model.access`.
- El **código en `sudo()`** (server actions, automatizaciones Studio, `base.automation`, `ir.actions.server`, scripts) se ejecuta saltándose las reglas de registro.
- El **propio Custodio de Datos Maestros** está RE-PERMITIDO por diseño: puede repetir el incidente si actúa mal (por eso el doble control de §5 y la auditoría).

Es decir: que el custodio, o una automatización en `sudo`, o el root, repitan el incidente **no lo impide la BD** — lo contienen los **controles procedimentales**. Por tanto son OBLIGATORIOS los siguientes refuerzos (detalle técnico en [[07-auditoria-trazabilidad-hardening]] — este es el punto de gobernanza que lo exige):

1. **Auditlog (obligatorio) sobre los modelos críticos:** `uom.uom`, `uom.category`, el **producto de servicio *Horas*** (`product.template` **y** `product.product`), `account.account`, `account.journal`, `res.currency`, `ir.sequence`, `res.groups`, `ir.rule`, `ir.model.access`, `base.automation`, `ir.actions.server`. Registrar create/write/unlink con usuario, fecha y valores previos/nuevos.
2. **Alerta (`base.automation`) ante `write` en `uom.uom` y en el producto *Horas***: notificación inmediata a los custodios (y a Dirección si procede) cuando cualquier usuario escriba sobre esos registros. Es la red que avisa aunque el bloqueo se haya esquivado por `sudo`/root.
3. **Revisión OBLIGATORIA de TODAS las automatizaciones Studio / server actions existentes** que escriban datos maestros, **ANTES de dar por cerrado el blindaje.** Studio corre en `sudo` y puede saltarse las `ir.rule`: una automatización preexistente que toque `uom.uom` o el producto *Horas* reintroduce el incidente aunque el blindaje esté "puesto". Sin esta revisión, el blindaje NO se considera completo.

> ⚠️ **Regla de gobernanza:** el blindaje técnico reduce la superficie, pero **no elimina** el riesgo del custodio, del `sudo` ni del root. Ese riesgo residual se gestiona con **procedimiento + trazabilidad + alerta**, no con más `ir.rule`. Reforzado en [[07-auditoria-trazabilidad-hardening]].

---

## 11. Checklist de gobernanza (resumen accionable)

- [ ] Solo 1 titular + 1 suplente con `base.group_system`. Ningún rol funcional lo lleva.
- [ ] 2FA forzado para custodios y `base.group_system`.
- [ ] Cuenta admin nominal, renombrada, no compartida, no usada para trabajo diario. Root (uid 1) custodiado.
- [ ] Custodio de Datos Maestros = único con write/unlink sobre UdM, productos, cuentas, diarios, analíticas, secuencias, monedas (ver [[04-blindaje-datos-maestros]]).
- [ ] Doble control activo para todas las acciones de la matriz RACI con A≠R.
- [ ] Todo cambio pasa por PRE con prueba funcional real **usando usuarios de rol (no admin)** + backup de PRO restaurable antes de aplicar.
- [ ] **Backup previo manual, verificado (restaurable) y etiquetado** antes de CUALQUIER cambio de datos maestros o permisos en PRO (norma dura §6.1). RPO `grupo_zambudio_prod` ≤ 4 h.
- [ ] **Prueba de restauración TRIMESTRAL** ejecutada con **RTO documentado** (≤ 4 h) y acta.
- [ ] **Riesgo residual gestionado** (§10): auditlog sobre modelos críticos + alerta `base.automation` en `uom.uom`/producto *Horas*.
- [ ] **TODAS las automatizaciones Studio / server actions que escriben maestros revisadas** ANTES de dar por cerrado el blindaje (Studio corre en `sudo`).
- [ ] `company_ids` mínimos por usuario (aislamiento AUNNA/CITRIC — [[05-record-rules-multiempresa]]).
- [ ] Developer mode e instalación de módulos: solo custodios, PRE primero.
- [ ] Blindajes de `ir.rule`/`ir.model.access` decididos como código versionado o dato replicado (no quedan solo en la UI de PRO).
- [ ] Auditoría activa sobre datos maestros y modelos de seguridad ([[07-auditoria-trazabilidad-hardening]]).
- [ ] Revisión trimestral de accesos con acta (incluye API keys y sesiones).
- [ ] Bajas desactivan (no borran) y revocan 2FA/sesiones/API keys el mismo día.

> **Recordatorio final:** el diseño de roles por sí solo NO habría evitado el incidente. La gobernanza (este documento) + el blindaje técnico de datos maestros ([[04-blindaje-datos-maestros]]) + el aislamiento multiempresa ([[05-record-rules-multiempresa]]) + la auditoría ([[07-auditoria-trazabilidad-hardening]]) son las cuatro patas. Falta una y el sistema vuelve a ser vulnerable.