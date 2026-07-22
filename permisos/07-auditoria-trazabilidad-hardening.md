# Auditoría, trazabilidad y hardening de la instancia Odoo 19 (Grupo Zambudio / Aunna IT)

> **Ámbito**: una sola BD multiempresa (AUNNA IT id 1, CITRIC id 2, MONTOYA, ii). Entornos PRO (`erp.zambudio.es` / `grupo_zambudio_prod`) y PRE (`erp-pre.zambudio.es` / `grupo_zambudio_prod_pruebas`).
> **Regla absoluta**: todo lo que toque PRO se prueba **primero en PRE**. Los `xmlid`, nombres de tabla y modelos que no puedo confirmar contra código van marcados **(verificar en PRE)**.
> **Documentos hermanos**: [[02-catalogo-de-roles]] (roles y record rules), [[05-record-rules-multiempresa]] (aislamiento de compañías), y la doc operativa de backups (ver §7).

Este documento es la **quinta línea de defensa**: cuando los permisos ([[02-catalogo-de-roles]]) fallan o alguien con privilegios legítimos hace algo destructivo, la trazabilidad permite **saber quién, qué y cuándo**, y el backup permite **volver atrás**. El incidente que motiva todo esto (un "Administrador" renombró el producto de servicio *Horas* y alteró la UdM *Horas*, rompiendo todos los partes y obligando a restaurar backup del día anterior) es exactamente el caso que aquí se blinda con **detección + trazabilidad + red final**.

> ⚠️ **Nota de versión (Odoo 19) que afecta a TODO este documento**: en v19 el sistema de grupos cambió de forma estructural. El campo `res.groups.category_id` se sustituye por `privilege_id` → `res.groups.privilege` → `category_id` → `ir.module.category`. En `res.users`, el clásico `groups_id` pasa a llamarse **`group_ids`** (grupos asignados directamente) y **`all_group_ids`** (cierre transitivo con los `implied_ids`, que es contra lo que resuelve `has_group`). Este cambio arrastra a `ir.rule.domain_force`, `ir.actions.*`, `ir.ui.view` e `ir.ui.menu`. **Consecuencia práctica**: cualquier consulta SQL o dominio que referencie grupos por la tabla de relación clásica hay que **verificarla en PRE** antes de fiarse de ella (ver §1.5).

---

## 0. Modelo mental: las 3 preguntas de la auditoría

| Pregunta | Mecanismo | Nativo / OCA |
|---|---|---|
| ¿Quién creó/modificó **este registro** y cuándo? | `log_access` (`create_uid`, `write_uid`, `create_date`, `write_date`) + chatter/`mail.tracking` | Nativo |
| ¿Qué **valor tenía antes** un campo maestro y quién lo cambió? | `mail.tracking` (solo campos con `tracking=True`) o **auditlog** OCA (forense completo) | Nativo limitado / OCA |
| ¿Quién **entró, falló al entrar o tocó la seguridad**? | `res.users.log`, logs del servidor, `ir.logging`, auditlog sobre modelos de seguridad | Nativo + OCA |

La auditoría nativa de Odoo es **limitada**: no hay audit-trail forense generalista. El hueco lo rellena OCA `auditlog` (§2), con los caveats de instalar OCA en Enterprise.

---

## 1. Trazabilidad NATIVA (sin instalar nada)

### 1.1 `log_access`: quién creó/modificó cada registro

Todo modelo con `_log_access = True` (el default) tiene 4 campos automáticos, consultables por SQL y visibles en modo desarrollador (Ver metadatos):

| Campo | Contenido |
|---|---|
| `create_uid` | Usuario que creó el registro |
| `create_date` | Fecha/hora de creación |
| `write_uid` | **Último** usuario que lo modificó |
| `write_date` | Fecha/hora de la última modificación |

**Limitación crítica**: `write_uid`/`write_date` solo guardan **la última** escritura. No hay histórico ni valores anteriores. Para el incidente de la UdM, esto solo te diría *quién la tocó por última vez*, no *qué le cambió*. Sirve como primer indicio, no como forense.

Query de diagnóstico rápido (solo lectura, segura en PRO) — quién tocó por última vez la UdM Horas y el producto de servicio:

```sql
-- UdM Horas (el xmlid 'uom.product_uom_hour' es el estándar; verificar en PRE)
-- OJO: 'login' está en res_users, NO en res_partner. Se une por write_uid a res_users.
SELECT u.id, u.name, u.write_uid, ru.login AS ultimo_editor, u.write_date
FROM uom_uom u
LEFT JOIN res_users ru ON ru.id = u.write_uid
WHERE u.id = (SELECT res_id FROM ir_model_data
              WHERE module='uom' AND name='product_uom_hour');   -- (verificar en PRE)

-- Productos de servicio tipo timesheet (posible "producto Horas")
SELECT pt.id, pt.name, pt.write_uid, pt.write_date, pt.type, pt.service_policy
FROM product_template pt
WHERE pt.type='service' AND pt.service_policy='delivered_timesheet';
```

> ⚠️ **Corrección respecto a versiones previas de este doc**: la columna `login` **no existe** en `res_partner`; vive en `res_users`. Une siempre por `write_uid → res_users` para obtener el login del editor. El `partner_id` solo hace falta si quieres el nombre comercial del contacto.

### 1.2 Chatter / `mail.tracking`: histórico por campo (solo campos marcados)

El chatter registra cambios **solo de campos con `tracking=True`** en su definición Python. Deja el histórico *en el propio registro* (mensajes "Campo X: valor viejo → valor nuevo"), nominal y con fecha. Es la trazabilidad que el usuario funcional puede consultar sin ser técnico.

- **Ventaja**: nativo, cero instalación, visible en la ficha.
- **Límite grave para datos maestros**: `uom.uom`, `product.template` (campo `name`, `type`, `uom_id`), `account.account`, `ir.sequence`, `res.currency` **NO traen `tracking=True`** en esos campos por defecto. Es decir, el chatter nativo **no habría registrado** el renombrado de la UdM ni del producto Horas. Por eso hace falta OCA (§2) o, como parche ligero, OCA `tracking_manager` que activa tracking sobre cualquier campo sin código.

Modelos maestros que **sí** conviene tener con chatter/tracking activo si se opta por vía nativa/`tracking_manager`:

| Modelo | Campos mínimos a trackear |
|---|---|
| `uom.uom` | `name`, `category_id`, `factor`, `uom_type`, `active` |
| `uom.category` | `name` |
| `product.template` | `name`, `type`, `service_policy`, `uom_id`, `active`, `sale_ok` |
| `account.account` | `name`, `code`, `account_type`, `deprecated` |
| `account.journal` | `name`, `code`, `type` |
| `account.analytic.account` | `name`, `plan_id`, `company_id` |
| `ir.sequence` | `name`, `prefix`, `suffix`, `number_next` |
| `res.currency` | `name`, `active`, `rounding` |
| `account.analytic.distribution.model` | `analytic_distribution`, `company_id` |

### 1.3 `res.users.log` y `login_date`: última conexión

Cada login actualiza `res.users.login_date`. Existe también el modelo `res.users.log` (histórico de accesos ligero). Útil para detectar cuentas inactivas o accesos fuera de horario. No registra **fallos** de login (eso son los logs del servidor, §6).

### 1.4 `ir.logging`: log técnico de la aplicación

Modelo `ir.logging` almacena mensajes de log del servidor persistidos en BD (nivel, módulo, función, línea, mensaje). No es audit-trail de datos, es diagnóstico técnico. Útil para rastrear errores de server actions/Studio. No lo actives con verbosidad alta en PRO: infla la BD.

### 1.5 Metadatos de configuración de seguridad (quién cambió permisos)

Los propios registros de seguridad tienen `log_access`. Para saber si alguien tocó reglas o accesos:

```sql
-- Reglas de registro modificadas recientemente
SELECT r.id, m.model, r.name, r.write_uid, r.write_date, r.active
FROM ir_rule r JOIN ir_model m ON m.id=r.model_id
ORDER BY r.write_date DESC NULLS LAST LIMIT 50;

-- ACL modificadas recientemente
SELECT a.id, m.model, a.name, a.group_id, a.write_uid, a.write_date,
       a.perm_read, a.perm_write, a.perm_create, a.perm_unlink
FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id
ORDER BY a.write_date DESC NULLS LAST LIMIT 50;
```

Para **saber quién tiene el grupo Administrador de sistema (`base.group_system`)**, en v19 hay dos matices importantes:

1. La tabla de relación clásica era `res_groups_users_rel(gid, uid)` para el M2M de grupos **directos**. Con el rename de `groups_id → group_ids` en v19, **el nombre de la tabla y de las columnas puede haber cambiado → (verificar en PRE)**.
2. Esa relación solo lista los grupos **asignados directamente**. Un usuario puede tener `group_system` de forma **efectiva** por herencia (`implied_ids`), que se refleja en `all_group_ids`, no en el M2M directo.

> ⚠️ **Recomendación**: para una lista **fiable** de quién tiene realmente `base.group_system`, no te fíes solo del SQL sobre la tabla directa. Usa la UI (Ajustes > Usuarios y Compañías > Usuarios, filtro/agrupación por grupo) o el ORM, que sí resuelve la herencia:
>
> ```python
> # En un shell de Odoo (odoo-bin shell) sobre PRE:
> grp = env.ref('base.group_system')
> users = env['res.users'].search([('all_group_ids', 'in', grp.ids)])
> for u in users:
>     print(u.login, u.name)
> ```
>
> Si aun así necesitas SQL directo, **confirma en PRE** el nombre real de la tabla de relación antes de escribir la consulta.

---

## 2. Auditoría de cambios en DATOS MAESTROS — OCA `auditlog`

La pieza que rellena el hueco forense de Odoo. **Es la recomendación central de este documento para el incidente.**

### 2.1 Qué es y qué resuelve

- Repo: `OCA/server-tools` rama `19.0` — https://github.com/OCA/server-tools/tree/19.0/auditlog — **disponibilidad 19 CONFIRMADA** (verificar el commit/versión concreta en PRE al instalar).
- Registra operaciones **create / read / write / unlink** por modelo y por campo: **quién, qué, cuándo, valor antes → valor después**.
- Se configura una **regla de auditoría** (`auditlog.rule`) por modelo, activable/desactivable.
- **Clave para el incidente**: si alguien renombra el producto *Horas* o toca una `uom.uom`, queda registro nominal **aunque la acción venga de Studio, de un server action o de importación CSV** — vías que el chatter nativo no cubre.

### 2.2 Qué modelos auditar (y qué operaciones) — tabla accionable

Auditar create/write/unlink **solo de datos maestros y de seguridad**. NO auditar modelos transaccionales de alto volumen (revientan la BD).

| Modelo | Operaciones | Prioridad | Motivo |
|---|---|---|---|
| `uom.uom` | write, unlink | **CRÍTICA** | Vector directo del incidente |
| `uom.category` | write, unlink | **CRÍTICA** | Cambiar ratio/referencia corrompe conversiones hora↔día |
| `product.template` | write, unlink | **CRÍTICA** | Renombrado/cambio de tipo del producto Horas |
| `product.product` | write, unlink | ALTA | Variantes del producto de servicio |
| `account.account` | write, unlink | ALTA | Plan de cuentas |
| `account.journal` | write, unlink | ALTA | Diarios (secuencias/asientos por compañía) |
| `account.analytic.account` | write, unlink | ALTA | Cuentas 90/271/155 (fuga cross-company) |
| `account.analytic.plan` | write, unlink | MEDIA | Plan "Horas internas/externas" (`x_plan3_id`) |
| `account.analytic.distribution.model` | create, write, unlink | **CRÍTICA** | Origen de la fuga de la 90 a CITRIC (ver [[05-record-rules-multiempresa]]) |
| `ir.sequence` | write, unlink | MEDIA | Numeración de documentos |
| `res.currency` | write, unlink | MEDIA | Moneda global, no aislable por compañía |
| `res.users` | create, write, unlink | **CRÍTICA** | Alta de usuarios y cambios de grupos |
| `res.groups` | write | **CRÍTICA** | Cambios de composición de grupos |
| `res.groups.privilege` | write | MEDIA | (v19) Reasignación de grupos a privilegios/categorías |
| `ir.rule` | create, write, unlink | ALTA | Quién tocó las record rules |
| `ir.model.access` | create, write, unlink | ALTA | Quién tocó los ACL |
| `ir.actions.server` | create, write, unlink | ALTA | Server actions (Studio no viaja con código) |
| `base.automation` | create, write, unlink | ALTA | Automatizaciones Studio |
| `res.users.apikeys` | create, unlink | ALTA | Alta/borrado de credenciales de larga vida (nombre de modelo confirmado; **el write apenas aplica**, la key es inmutable) |
| `ir.ui.menu` | write, unlink | MEDIA | Ocultar/mostrar menús técnicos |
| `ir.model.fields` | create, write, unlink | MEDIA | Campos custom Studio |

> **Regla de acotación**: para casi todo basta **write + unlink** (los renombrados y borrados son el riesgo). Añade **create** solo donde el alta indebida es el riesgo (`res.users`, `account.analytic.distribution.model`, server actions/automatizaciones, `res.users.apikeys`). **Nunca audites `read`** en producción salvo investigación puntual acotada: multiplica el volumen de log por cada consulta.

> ⚠️ **Auditlog sobre `res.users.apikeys`**: las API keys se crean y se borran, pero **no se editan** (no hay flujo de `write` sobre el secreto). Audita **create/unlink**, no `write`. El secreto va con hash y auditlog pone en blacklist campos tipo `password`/`key` — verifica en PRE que **no** se está almacenando ningún valor sensible en el log.

### 2.3 Caveats de instalar OCA `auditlog` en Enterprise

1. **Rendimiento/volumen**: auditar create/write en modelos transaccionales (`account.move.line`, `stock.move`, `mail.message`, `account.analytic.line`) infla la BD muy rápido. **Acotar SIEMPRE a datos maestros + seguridad** (tabla §2.2).
2. **Retención**: auditlog **no purga solo**. Prever un cron de limpieza de logs antiguos (p.ej. conservar 24 meses). Si el módulo no trae la opción en esta versión, cron custom sobre `auditlog.log`.
3. **Blacklist**: auditlog pone en blacklist campos llamados `password` (correcto, no los captures). Verifica el comportamiento con `res.users`/`res.users.apikeys` en PRE.
4. **Soporte Enterprise**: instalar módulos de terceros/OCA puede afectar la cobertura del contrato de soporte oficial en incidencias donde el módulo esté implicado; Odoo puede pedir reproducir sin él.
5. **Migraciones anuales**: cada upgrade hay que re-portar/re-validar. `auditlog` **sí** está en 19, riesgo bajo.
6. **Probar en PRE**: instalar en `grupo_zambudio_prod_pruebas`, ejecutar los flujos reales (partes de horas, facturación WIP) y medir el crecimiento de `auditlog.log` antes de PRO.
7. **Multiempresa**: las `auditlog.rule` son configuración global; asegúrate de que auditan por igual registros de AUNNA y de CITRIC (los modelos maestros compartidos no llevan `company_id` o lo llevan opcional).

### 2.4 Alternativa/complemento ligero: `tracking_manager`

- `OCA/server-tools/tree/19.0/tracking_manager` — **disponibilidad 19 CONFIRMADA** (verificar versión en PRE).
- Activa chatter/tracking sobre cualquier campo de cualquier modelo **sin código**, dejando el histórico en el propio registro. Más "consultable por el funcional", menos potente para forense global.
- **Límite**: se centra en `write` (histórico de cambios de valor); no sustituye el registro forense de create/unlink de auditlog. Úsalo como capa de UX encima de los modelos de §1.2; `auditlog` como capa forense.

**Recomendación**: `auditlog` (forense, sobre §2.2) + opcionalmente `tracking_manager` para que Administración/Dirección consulten cambios desde la ficha. No son excluyentes.

### 2.5 Riesgo residual: el blindaje NO frena a uid 1 ni a `sudo` (C7)

> 🚨 **Declaración explícita de riesgo residual (coordinada con el doc 00)**: tras aplicar el blindaje de record rules del doc [[02-catalogo-de-roles]], **queda un riesgo que NINGÚN control técnico de la BD elimina**. Que el **propio custodio**, una **automatización de Studio** o **cualquier código que corra en `sudo`** repitan el incidente (renombrar el producto *Horas*, alterar la UdM, tocar la 90) es un **control PROCEDIMENTAL, no técnico**:
>
> - El **superusuario (uid 1 / `base.user_root` / `__system__`) ignora las record rules** por completo.
> - **`sudo()` salta las reglas de registro y los ACL** — y **Studio corre en `sudo`**, por lo que una automatización Studio puede escribir maestros aunque las reglas prohíban a los humanos hacerlo.
> - `base.group_system` **NO** ignora las record rules (por eso el blindaje sí frena al "admin" del incidente), pero un usuario con `group_system` **puede desactivar la propia regla o la alerta** antes de actuar.
>
> Por eso el blindaje se **complementa obligatoriamente** con las tres capas siguientes (a/b/c). Sin ellas, el blindaje da una falsa sensación de seguridad.

**(a) auditlog OBLIGATORIO sobre el conjunto mínimo forense.** Estos modelos deben tener `auditlog.rule` activa **sí o sí** (subconjunto crítico de la tabla §2.2; ver ahí operaciones y motivos):

| Modelo | Por qué es imprescindible |
|---|---|
| `uom.uom` | Vector directo del incidente |
| `uom.category` | Ratio/referencia de conversión hora↔día |
| `product.template` | Producto de servicio *Horas* (renombrado/tipo) |
| `product.product` | Variante del producto *Horas* (la que usa el parte) |
| `account.account` | Plan de cuentas |
| `account.journal` | Diarios |
| `res.currency` | Moneda global (no aislable por compañía) |
| `ir.sequence` | Numeración de documentos |
| `res.groups` | Composición de grupos (incl. custodio/system) |
| `ir.rule` | Quién tocó/desactivó las record rules del blindaje |
| `ir.model.access` | Quién tocó los ACL |
| `base.automation` | Automatizaciones Studio (corren en sudo) |
| `ir.actions.server` | Server actions (código que corre en sudo) |

Auditar `ir.rule`, `ir.model.access`, `base.automation` e `ir.actions.server` es lo que permite detectar **que alguien apagó el propio blindaje o la alerta** — es la vigilancia "hacia arriba".

**(b) Alerta `base.automation` ante `write` en los dos vectores calientes.** Configurar automatización que **notifique al custodio** ante cualquier `write` sobre `uom.uom` y sobre el **producto de servicio *Horas*** (`product.template`/`product.product`) — ver §4.1 y el snippet §4.2. Es la detección casi en tiempo real que convierte el forense (pasivo) en aviso (activo).

**(c) Revisión OBLIGATORIA de TODAS las automatizaciones Studio existentes ANTES de dar por cerrado el blindaje.** Como Studio corre en `sudo` y **puede saltarse las reglas**, hay que **inventariar y revisar toda automatización/server action existente que escriba datos maestros** antes de declarar el blindaje operativo. Query de arranque del inventario:

```sql
-- Automatizaciones y server actions que ESCRIBEN sobre modelos maestros (revisar TODAS)
SELECT ba.id, ba.name, m.model, ba.trigger, ba.active
FROM base_automation ba
JOIN ir_actions_server act ON act.id = ba.action_server_id   -- (verificar en PRE el nombre del enlace)
JOIN ir_model m ON m.id = act.model_id
WHERE m.model IN ('uom.uom','uom.category','product.template','product.product',
                  'account.account','account.journal','res.currency','ir.sequence',
                  'account.analytic.distribution.model')
ORDER BY ba.active DESC, m.model;

-- Server actions de tipo código (Studio) que puedan tocar maestros en sudo
SELECT act.id, act.name, m.model, act.state
FROM ir_actions_server act
JOIN ir_model m ON m.id = act.model_id
WHERE act.state = 'code'
  AND m.model IN ('uom.uom','product.template','product.product','account.account',
                  'account.analytic.distribution.model');
```

Cada automatización encontrada se documenta (qué escribe, por qué, quién la creó) y se decide **conservar / restringir / eliminar** ANTES del go-live del blindaje. El blindaje **no se declara cerrado** mientras haya automatizaciones Studio sin revisar que escriban maestros.

---

## 3. Seguridad de ACCESO (hardening de autenticación)

### 3.1 2FA obligatorio para administradores — NATIVO Enterprise

**No requiere módulo OCA.** Odoo Community y Enterprise traen 2FA (TOTP + FIDO U2F/passkeys).

- Activación forzada: **Ajustes > Permisos/Usuarios > "Forzar autenticación de dos factores"** (aplicable a *Empleados* o *Todos*). El nombre exacto del literal puede variar según traducción — **verificar en PRE**.
- Doc 19: https://www.odoo.com/documentation/19.0/applications/general/users/2fa.html

**Norma Zambudio**: 2FA **obligatorio** como mínimo para:
- Todo usuario con `base.group_system` (Administrador de sistema / custodio).
- Todo usuario con `base.group_erp_manager` (gestor de accesos).
- El **Custodio de datos maestros** (grupo funcional definido en [[02-catalogo-de-roles]]). **xmlid canónico**: `zambudio_permisos.group_master_data_custodian`. Este grupo **NO** implica `base.group_system` ni es el uid 1; es un rol funcional al que las reglas de blindaje **re-permiten** explícitamente la edición de maestros. Si el grupo se crea por UI en vez de por el módulo `zambudio_permisos`, su xmlid real se resolverá **(verificar en PRE)**. *Cualquier otro nombre en versiones previas (`zambudio_custom`, `zambudio_master_data`, `group_master_data_custody`, etc.) es histórico; usar siempre el canónico.*
- Contabilidad con `account.group_account_manager` (tesorería/pagos).

Recomendado extenderlo a **todos los empleados internos** dado que el catálogo de apps es amplio.

### 3.2 Política de contraseñas — OCA `password_security`

- Repo: `OCA/server-auth`. Confirmado en 16/17/18. **En rama 19.0 NO he podido confirmar el port → (verificar port a 19 antes de contar con él).**
- Qué haría: longitud mínima, complejidad, expiración periódica, historial (no reutilizar últimas N), bloqueo de reutilización.
- **Mientras no esté portado/confirmado en 19**: apoyarse en **2FA nativo forzado** (§3.1) + política manual documentada (longitud ≥ 12, no reutilizar, cambio ante sospecha). Si hubiera SSO/OIDC/SAML, la política la manda el IdP externo, no este módulo.

### 3.3 Timeout de sesión por inactividad — OCA `auth_session_timeout`

- Repo: `OCA/server-auth/tree/19.0/auth_session_timeout` — **disponibilidad 19 CONFIRMADA** (verificar versión exacta en PRE).
- Cierra (logout) sesiones inactivas pasado un delay; valida en cada request. Parámetro de sistema `inactive_session_time_out_delay` (segundos; el default histórico es 7200 = 2h — **confirmar el default de esta versión en PRE**).
- **Caveat**: afecta a TODOS. Define **excepción por grupo** para usuarios técnicos/integraciones API, o las conexiones automáticas se cortarán. El módulo permite excluir por grupo (`inactive_session_time_out_ignored_url_prefixes` y/o grupo de exclusión — verificar el mecanismo exacto en PRE).
- **Recomendación Zambudio**: 30-60 min para perfiles funcionales; excepción para el/los usuario(s) de integración API.

### 3.4 Control de API keys

Las API keys (`res.users.apikeys`) son credenciales de larga vida que **saltan el 2FA**. Riesgo alto si se filtran.

- **Inventario y caducidad**: revisar periódicamente qué keys existen, de quién, y su fecha de caducidad. **AVISO OPERATIVO: la API key de PRE caduca el 2026-10-12** — planificar su rotación antes de esa fecha para no romper integraciones de pruebas.
- Odoo 19 permite fijar **fecha de expiración** al crear la key: úsala siempre, nunca keys sin caducidad.
- Auditar creación/borrado de keys con auditlog sobre `res.users.apikeys` (modelo confirmado; **audita create/unlink, no write** — ver §2.2).
- Query de inventario:

```sql
SELECT k.id, k.name, ru.login, k.scope, k.expiration_date, k.create_date
FROM res_users_apikeys k
JOIN res_users ru ON ru.id = k.user_id
ORDER BY k.expiration_date NULLS FIRST;
```

- **Norma**: una API key por integración (no compartir), scope mínimo, caducidad obligatoria, rotación documentada, y **nunca** en repos ni en texto plano.

### 3.5 Gestión de sesiones

- Sesiones activas visibles/revocables desde la ficha del usuario (modo desarrollador) y por tabla de sesiones del servidor.
- Ante baja de un empleado o sospecha: cambiar contraseña + revocar API keys + cerrar sesiones + retirar grupos (`group_ids`) — y **archivar** el usuario (`active=False`) en vez de borrarlo, para conservar la trazabilidad de sus registros históricos (`create_uid`/`write_uid` seguirían resolviendo).

### 3.6 Brute-force / rate limiting de login — NATIVO servidor

El servidor Odoo trae protección brute-force / rate limiting de login (configurable en `odoo.conf`, gestionado por el hosting). **No requiere módulo OCA.** Ver §6 para la detección de los fallos.

---

## 4. ALERTAS: detectar acciones peligrosas en tiempo (casi) real

La auditoría registra; las **alertas avisan**. Dos vías nativas (base_automation / server actions) + revisión periódica.

### 4.1 Automatización de alerta (nativo `base.automation`)

Crear reglas de automatización que, ante un cambio peligroso, **envíen aviso al custodio**. Ejemplos de disparadores a configurar:

| Evento a vigilar | Modelo | Disparador | Acción |
|---|---|---|---|
| Renombrado/cambio de tipo del producto Horas | `product.template` | On Update de `name`/`type`/`uom_id` en productos de servicio | Email/Discuss al custodio |
| Cambio en UdM | `uom.uom` | On Update de `name`/`factor`/`uom_type` | Email al custodio |
| Borrado de UdM o producto | `uom.uom` / `product.template` | On Delete | Email + log |
| Alta de usuario con `base.group_system` | `res.users` | On Create/Update con grupo system | Aviso al custodio de sistema |
| Modelo de distribución analítica con `company_id` vacío apuntando a cuenta de compañía | `account.analytic.distribution.model` | On Create/Update | Aviso (previene la fuga de la 90, ver [[05-record-rules-multiempresa]]) |

> **Aviso doble**: las propias automatizaciones son datos de configuración editables. **Audítalas con auditlog** (`base.automation`, `ir.actions.server` en §2.2), o un usuario con `group_system` podría desactivar la alerta antes de actuar. Y recuerda: **las automatizaciones de Studio NO viajan con código** entre PRE y PRO; hay que recrearlas y auditarlas en cada entorno.

### 4.2 Ejemplo de acción de servidor de alerta (referencia, Python de server action)

```python
# Server action ligada a base.automation sobre uom.uom (On Update de name/factor/uom_type).
# Avisa por Discuss al partner custodio cuando cambia el nombre o el factor de una UdM.
# Contexto disponible en server actions: env, model, record(s), log, _, UserError...
custodio = env.ref('base.partner_admin')  # (verificar en PRE el partner real del custodio)
for record in records:
    body = _("ALERTA: la UdM '%s' (id %s) ha sido modificada por %s") % (
        record.display_name, record.id, env.user.name)
    record.message_notify(
        partner_ids=custodio.ids,
        subject=_("Cambio en Unidad de Medida"),
        body=body,
    )
```

> ⚠️ **Correcciones respecto a la versión previa del snippet**:
> - Usa **`env.ref(...)`**, no `ref(...)`: en el contexto de server action el helper garantizado es `env.ref`.
> - `message_notify` se invoca sobre un **registro con chatter**. `uom.uom` no hereda `mail.thread` por defecto, así que `record.message_notify(...)` puede fallar. Alternativas seguras: (a) enviar por `env['mail.mail']`/plantilla de correo; (b) `env['bus.bus']` o un canal Discuss; o (c) activar `mail.thread` en `uom.uom` vía `tracking_manager`/módulo. **Verificar en PRE** qué vía de notificación funciona antes de darla por buena en PRO.

### 4.3 Revisión periódica (queries de vigilancia)

Programar un **cron mensual** (o revisión manual) con estas queries de higiene. Recuerda el caveat de §1.5 sobre la tabla de relación de grupos en v19.

```sql
-- 1) ¿Alguien con group_system? (comparar contra lista blanca conocida)
--    NOTA v19: 'res_groups_users_rel' lista solo grupos DIRECTOS y su nombre/columnas
--    pueden haber cambiado -> (verificar en PRE). Para lista fiable (incluye herencia)
--    usar la UI o el ORM: search([('all_group_ids','in', grp.ids)]).
SELECT ru.login, rp.name FROM res_groups_users_rel rel
JOIN res_users ru ON ru.id=rel.uid JOIN res_partner rp ON rp.id=ru.partner_id
WHERE rel.gid=(SELECT res_id FROM ir_model_data
               WHERE module='base' AND name='group_system');   -- (verificar en PRE)

-- 3) Reglas de registro desactivadas (alguien pudo apagar un blindaje)
SELECT r.id, m.model, r.name, r.active, r.write_uid, r.write_date
FROM ir_rule r JOIN ir_model m ON m.id=r.model_id
WHERE r.active = false;

-- 4) API keys sin caducidad o caducadas
SELECT k.name, ru.login, k.expiration_date FROM res_users_apikeys k
JOIN res_users ru ON ru.id=k.user_id
WHERE k.expiration_date IS NULL OR k.expiration_date < now();
```

Para la **query 2 (modelos de distribución analítica peligrosos)**, cuidado: en `account.analytic.distribution.model` el campo `analytic_distribution` es **JSONB cuyas claves son los IDs de la cuenta analítica** (no el código "90"). Un `LIKE '%90%'` sobre el texto matchearía cualquier ID que contenga "90", dando falsos positivos/negativos. Hazlo en dos pasos, resolviendo primero el ID de la cuenta 90:

```sql
-- 2a) Obtener el id de la cuenta analitica 90 (Horas internas AUNNA) y 271 (CITRIC)
SELECT id, code, name, company_id FROM account_analytic_account
WHERE code IN ('90','271');

-- 2b) Modelos de distribucion SIN compania que referencian esas cuentas por su ID (jsonb '?')
--     Sustituir <ID90>/<ID271> por los ids obtenidos en 2a.
SELECT m.id, m.company_id, m.analytic_distribution
FROM account_analytic_distribution_model m
WHERE m.company_id IS NULL
  AND (m.analytic_distribution ? '<ID90>' OR m.analytic_distribution ? '<ID271>');
```

> ⚠️ **Por qué importa**: un modelo de distribución sin `company_id` que apunte a la cuenta 90 (de AUNNA) puede aplicarse a asientos de CITRIC → es exactamente el vector de fuga cross-company de [[05-record-rules-multiempresa]]. La query anterior lo detecta sin falsos positivos por código.

---

## 5. Backups: la RED FINAL

Cuando todo lo anterior falla (o un `group_system` legítimo hace daño legítimo pero equivocado, como en el incidente), **el backup es lo único que devuelve el trabajo perdido**. En el incidente se restauró backup del día anterior y **se perdió el trabajo del día** — eso marca el suelo del RPO actual.

### 5.1 Principios

- **Fuente de verdad de la operativa de backups**: doc operativa en `new/doc/`, concretamente `new/doc/04-backups-y-restauracion.md` (servidores PRE/PRO, módulos, despliegue, **backups**, incidencias) y el script `/root/backup_odoo19_prod.sh`. Este documento **no duplica** los procedimientos; los referencia.
- **Regla 3-2-1**: 3 copias, 2 medios, 1 fuera de sitio.
- **RPO objetivo (valor concreto, no blando)**: para `grupo_zambudio_prod` el RPO objetivo es **≤ 2-4 horas** (el incidente costó ~24 h de trabajo rehecho; un backup diario deja hasta ~24 h de exposición, que es inaceptable). Implica backups **cada pocas horas** de la BD de PRO, además del backup manual pre-cambio.
- **RTO objetivo y prueba trimestral**: cada prueba de restauración (§5.2) debe **cronometrarse y documentar el RTO real** en `new/doc/04-backups-y-restauracion.md`. La prueba de restauración es **TRIMESTRAL** y obligatoria.

> 🔒 **NORMA DE BACKUP DURA (no negociable) — C6**: es **OBLIGATORIO** hacer un **backup manual verificado y ETIQUETADO inmediatamente ANTES** de cualquier cambio en datos maestros o en permisos en PRO. "Verificado" = el dump se genera **y** se comprueba que existe y tiene tamaño coherente; "etiquetado" = nombre con fecha/hora y motivo del cambio (p.ej. `grupo_zambudio_prod_pre-cambio-uom-20260722_0930.sql`). Sin este backup **no se toca PRO**. Referencia operativa: `new/doc/04-backups-y-restauracion.md` y `/root/backup_odoo19_prod.sh`. Es el ancla de rollback inmediato del incidente tipo "renombrado de UdM / producto Horas".

### 5.2 Prueba de restauración (imprescindible)

Un backup no probado **no es un backup**. Procedimiento:

1. Restaurar periódicamente (trimestral) el dump de PRO **en PRE** (`grupo_zambudio_prod_pruebas`).
2. Verificar que la restauración levanta: login, partes de horas, facturación WIP, y que la UdM Horas y el producto de servicio están intactos.
3. Documentar el tiempo de restauración (RTO real) en la doc operativa.
4. PRE ya se nutre de PRO, así que esta prueba encaja con el flujo habitual: aprovecharla como validación de backups.

> ⚠️ **Aviso multiempresa al restaurar**: al copiar PRO→PRE se arrastran datos reales de AUNNA **y** CITRIC. Trata PRE como entorno con datos productivos (mismos controles de acceso), y **desactiva correos/SMS salientes** (modo test de `ir.mail_server`/`fetchmail`) antes de operar, para no notificar a clientes reales desde pruebas.

### 5.3 Qué respaldar además del dump SQL

- **Filestore** (adjuntos, `ir.attachment` en disco): el dump SQL **no** lo incluye por defecto. Verificar que el backup abarca filestore.
- **`odoo.conf`** y lista de módulos instalados (incluidos custom `zambudio_*`/`aunna_*` y OCA).
- **Automatizaciones de Studio**: recordar que **no viajan con código**; documentar su estado o exportarlas, porque un restore de código sin ellas deja la instancia incompleta.

---

## 6. Registro y monitorización de LOGINS FALLIDOS

Los intentos fallidos de login **no** quedan en un modelo de datos consultable de forma cómoda; viven en los **logs del servidor** (`odoo-server.log`), gestionados por el hosting/infra.

### 6.1 Qué buscar en el log del servidor

- Líneas de autenticación fallida (patrón `Login failed` / `authentication failed`) con IP y login intentado.
- Picos de fallos sobre un mismo login = posible brute-force (mitigado por el rate limiting nativo, §3.6, pero hay que **verlo**).
- Accesos correctos fuera de horario o desde IPs inesperadas.

### 6.2 Recomendaciones de monitorización

- **Centralizar logs** del servidor Odoo (envío a un colector/sistema de logs del hosting) y definir alertas sobre umbrales de fallos.
- Cruzar con `res.users.login_date` para detectar cuentas dormidas que de repente se usan.
- Registrar y revisar accesos del/los usuario(s) con `base.group_system` — su actividad es la más sensible.
- Si el hosting lo permite, **fail2ban** o equivalente sobre los patrones de login fallido a nivel de sistema operativo/proxy.

> Odoo **no** trae un panel nativo de "logins fallidos". Es responsabilidad de infra/hosting. Documentar en la doc operativa dónde están los logs y quién los revisa.

---

## 7. Tabla maestra: QUÉ auditar / CON QUÉ / PRIORIDAD

Leyenda: **N** = nativo Enterprise (sin módulo) · **OCA** = requiere módulo comunitario (riesgo soporte/migración) · **INFRA** = capa de hosting/servidor.

| # | Qué vigilar | Con qué | Tipo | Prioridad | Riesgo de la herramienta |
|---|---|---|---|---|---|
| 1 | Cambios en `uom.uom` / `uom.category` | auditlog (write/unlink) + alerta base_automation | OCA + N | **CRÍTICA** | Volumen bajo (maestro); vía OCA |
| 2 | Cambios en producto de servicio *Horas* (`product.template`) | auditlog + alerta | OCA + N | **CRÍTICA** | Bajo |
| 3 | `account.analytic.distribution.model` con `company_id` vacío | Query de vigilancia (§4.3, por ID no por código) + auditlog | N + OCA | **CRÍTICA** | Nulo (query) |
| 4 | Alta/cambio de usuarios y grupos (`res.users`, `res.groups`) | auditlog + query/UI mensual | OCA + N | **CRÍTICA** | Bajo |
| 5 | 2FA en admins y custodios | Enforce 2FA nativo | **N** | **CRÍTICA** | Ninguno (nativo) |
| 6 | Cambios en `ir.rule` / `ir.model.access` | auditlog + query | OCA + N | ALTA | Bajo |
| 7 | Server actions / `base.automation` (Studio) | auditlog | OCA | ALTA | Bajo; recordar Studio no viaja con código |
| 8 | Plan de cuentas / diarios / analíticas | auditlog (write/unlink) | OCA | ALTA | Bajo |
| 9 | API keys (inventario, caducidad, PRE caduca 2026-10-12) | Query + política de caducidad + auditlog (create/unlink) | **N** + OCA | ALTA | Ninguno |
| 10 | Timeout de sesión inactiva | auth_session_timeout | OCA | ALTA | (CONFIRMADO 19); excepción API obligatoria |
| 11 | Logins fallidos / brute-force | Logs servidor + rate limiting nativo | **N + INFRA** | ALTA | Requiere infra/hosting |
| 12 | Última conexión / cuentas dormidas | `res.users.login_date` + `res.users.log` | **N** | MEDIA | Ninguno |
| 13 | Política de contraseñas | password_security | OCA | MEDIA | **Port 19 NO confirmado (verificar); mientras, 2FA + manual** |
| 14 | `ir.sequence`, `res.currency` | auditlog (write/unlink) | OCA | MEDIA | Bajo |
| 15 | Menús técnicos / campos Studio (`ir.ui.menu`, `ir.model.fields`) | auditlog | OCA | MEDIA | Bajo |
| 16 | Export de datos (fuga) | web_disable_export_group / base_export_manager | OCA | MEDIA | **Port 19 NO confirmado (verificar)** |
| 17 | Backups + prueba de restauración | Doc operativa `new/doc/` | **N + INFRA** | **CRÍTICA** | Ninguno; probar restore |
| 18 | Log técnico de la app | `ir.logging` | **N** | BAJA | No subir verbosidad en PRO |

---

## 8. Nativo Enterprise vs OCA — resumen de decisión

**Usar SIEMPRE lo nativo antes que OCA:**

| Necesidad | Solución nativa | ¿Hace falta OCA? |
|---|---|---|
| 2FA obligatorio | Enforce 2FA (Ajustes > Permisos/Usuarios) | **No** |
| Brute-force login | Rate limiting servidor (`odoo.conf`) | **No** |
| Quién creó/modificó (último) | `log_access` (create_uid/write_uid) | **No** |
| Histórico por campo (limitado) | chatter/`mail.tracking` (solo campos con tracking) | **No** para campos ya trackeados |
| Quitar Apps/Store a usuarios | No dar `base.group_system` | **No** |
| Lock dates contables | `fiscalyear_lock_date` / `hard_lock_date` | **No** |

**OCA imprescindible (el hueco que Odoo no cubre):**

| Necesidad | Módulo OCA | Estado 19 | Riesgo |
|---|---|---|---|
| Audit-trail forense de maestros | `auditlog` | **CONFIRMADO 19** | Soporte Enterprise + acotar volumen + purga |
| Tracking sin código para funcionales | `tracking_manager` | **CONFIRMADO 19** | Foco en write; UX no forense |
| Timeout de sesión | `auth_session_timeout` | **CONFIRMADO 19** | Excepción API obligatoria |
| Política de contraseñas | `password_security` | **Port 19 NO confirmado (verificar)** | Diferir; usar 2FA + manual |
| Bloqueo de export | `web_disable_export_group` / `base_export_manager` | **Port 19 NO confirmado (verificar)** | Diferir hasta confirmar |

**Recomendación priorizada mínima viable (todo confirmado en 19), a desplegar primero en PRE:**

1. **auditlog** sobre datos maestros + modelos de seguridad/automatización (§2.2).
2. **auth_session_timeout** con excepción para usuarios API.
3. **2FA nativo forzado** para custodios/admins (sin módulo).
4. **Quitar `base.group_system`** a usuarios finales (mata Apps/store nativamente y previene el vector del incidente — ver [[02-catalogo-de-roles]]).
5. **Alertas base_automation** sobre UdM/producto Horas/distribución analítica (§4), verificando la vía de notificación en PRE.
6. **Prueba de restauración** trimestral de backup en PRE (§5.2).
7. **Rotar la API key de PRE antes del 2026-10-12** (§3.4).
8. Diferir `password_security` y bloqueo de export hasta confirmar port a 19.

---

## 9. Gobernanza de la auditoría (procedimiento, no técnico)

- **Custodia**: 1 titular + 1 suplente con `base.group_system`. Su actividad se audita con auditlog (nadie audita "hacia arriba" salvo el suplente). El superusuario real (uid 1 / `base.user_root` / `__system__`) **ignora record rules y no queda filtrado por ellas** — su uso es excepcional, controlado y registrado. (El `admin` funcional es uid 2 / `base.user_admin`; no confundir con el root uid 1.)
- **Doble control**: cambios en datos maestros y permisos se piden por ticket, se aplican **primero en PRE**, se validan, y luego a PRO con backup manual previo.
- **Revisión periódica**: mensual las queries de §4.3; trimestral la prueba de restauración y la revisión de usuarios con `group_system`/`group_erp_manager` (por UI/ORM, no solo SQL — §1.5).
- **Retención de logs de auditoría**: definir (p.ej. 24 meses) y cron de purga de `auditlog.log`.
- **No credenciales en claro**: ni en este doc, ni en repos, ni en tickets. API keys con caducidad y scope mínimo.
- **Recordatorio permanente**: las automatizaciones de **Studio/base_automation no viajan con código** entre PRE y PRO — auditarlas y recrearlas conscientemente en cada despliegue.

---

### Enlaces a documentación relacionada
- [[02-catalogo-de-roles]] — roles, record rules, custodio de datos maestros, ACL restrictivos.
- [[05-record-rules-multiempresa]] — aislamiento AUNNA/CITRIC, fuga de la cuenta 90, distribución analítica.
- Doc operativa `new/doc/` — servidores PRE/PRO, despliegue, **backups**, incidencias (fuente de verdad para §5).

### Fuentes
- Código fuente `odoo/odoo` rama 19.0 (`res_groups.py`, `res_users.py`, `ir_rule.py`, `base_groups.xml`) — cambios v19 en grupos (`privilege_id`/`res.groups.privilege`, `group_ids`/`all_group_ids`).
- OCA auditlog 19: https://github.com/OCA/server-tools/tree/19.0/auditlog
- OCA tracking_manager 19: https://github.com/OCA/server-tools/tree/19.0/tracking_manager
- OCA auth_session_timeout 19: https://github.com/OCA/server-auth/tree/19.0/auth_session_timeout
- OCA password_security (18, port 19 sin confirmar): https://github.com/OCA/server-auth/tree/18.0/password_security
- 2FA nativo Odoo 19: https://www.odoo.com/documentation/19.0/applications/general/users/2fa.html
- Restricción de acceso a datos / seguridad Odoo 19: https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html