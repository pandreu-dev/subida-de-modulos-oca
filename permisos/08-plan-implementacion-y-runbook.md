# 08 — Plan de implementación por fases + Runbook operativo (gobernanza de permisos Odoo 19)

> **Ámbito:** Grupo Zambudio / Aunna IT · Odoo 19 Enterprise · multiempresa en una sola BD (AUNNA IT id 1, CITRIC id 2, MONTOYA, ii).
> **Entornos:** PRO = `erp.zambudio.es` / BD `grupo_zambudio_prod` · PRE = `erp-pre.zambudio.es` / BD `grupo_zambudio_prod_pruebas`.
> **Regla de oro que se repite en TODO el documento:** nada se toca en PRO sin haberlo probado antes en PRE y sin backup previo verificado. Ninguna fase se salta la validación en PRE.
> **Motivo del proyecto:** un usuario con perfil "Administrador" (`base.group_system`) renombró el producto de servicio *Horas* y alteró la UdM *Horas* (`uom.uom`), rompiendo TODOS los partes de horas y obligando a restaurar backup del día anterior (día de trabajo perdido). Esto es un fallo de gobernanza de permisos, no un bug.

> ⚠️ **Nota de versión (Odoo 19 — cambios que afectan a TODO este documento).** En v19 el modelo de seguridad cambió respecto a v17/18. Verificado:
> - `res.groups.category_id` → sustituido por `privilege_id` (Many2one a **`res.groups.privilege`**, que a su vez tiene `category_id`). El `privilege_id` es **opcional**: un grupo funciona sin él (solo pierde la agrupación visual en Ajustes).
> - `res.users.groups_id` → **renombrado a `group_ids`** (directos) y aparece `all_group_ids` (calculado: directos + implicados). El rename **arrastra** a `ir.actions.act_window`, `ir.actions.server`, `ir.actions.report`, `ir.ui.view` e `ir.ui.menu` (el atributo/campo `groups_id`).
> - `res.groups.users` → **renombrado a `user_ids`**.
> - `ir.rule.groups` (M2m a `res.groups`) se mantiene como `groups`; `ir.rule.global` es un **campo calculado** (una regla es global si NO tiene grupos — ver Fase 3.2).
> Toda referencia a nombres de tabla/campo marcada **(verificar en PRE)** debe confirmarse contra la BD real antes de usarse en PRO.

Documentos relacionados: [[README]] · [[01-modelo-seguridad-odoo19]] · [[04-blindaje-datos-maestros]] · [[02-catalogo-de-roles]] · [[05-record-rules-multiempresa]] · [[07-auditoria-trazabilidad-hardening]] · [[00-principios-y-gobernanza]] · [[05-record-rules-multiempresa]] · **[[09-anexo-verificacion-y-checklist]] (GATE obligatorio antes de PRO)** (marcados como referencia; verificar nombres reales en la carpeta `new/permisos` / `new/doc`).

---

## 0. Cómo usar este documento

Este es el plan de ejecución. Se recorre de arriba abajo por **fases**; cada fase tiene:

- **Objetivo** y por qué reduce el riesgo del incidente.
- **Pasos concretos** (marcados `[UI]` o `[XML]` según se hagan por interfaz o por módulo/código).
- **Cómo probar en PRE.**
- **Cómo aplicar en PRO** (backup, ventana, verificación, rollback).

Convenciones:

| Marca | Significado |
|---|---|
| `[UI]` | Se hace por interfaz (Ajustes / Técnico). No viaja con código: hay que replicarlo manualmente en PRE y PRO, o exportarlo. |
| `[XML]` | Se entrega en un módulo/data file versionado. Viaja con código: se despliega igual en PRE y PRO. |
| `[SQL-RO]` | Consulta **solo lectura**. Segura en PRO. Nunca hace `UPDATE`/`DELETE`. |
| `(verificar en PRE)` | xmlid o nombre de campo/tabla no confirmado contra fuente; confirmar antes de referenciarlo en PRO. |
| ⚠ / ⚠️ | Toca producción / dato sensible. |

Orden de despliegue **siempre**: escribir → probar en PRE → validar flujos reales (partes de horas, facturación WIP, alta de factura) → **GATE doc 09** → backup PRO etiquetado → ventana → aplicar PRO → verificar → dejar rollback listo.

> 🚪 **GATE obligatorio antes de PRO — [[09-anexo-verificacion-y-checklist]].** Ningún XML de este runbook se pega en PRO hasta haber recorrido el **doc 09** (anexo de verificación): todos los xmlids/ids marcados **(verificar en PRE)** (grupos, modelos, categoría de privilegio, ids del producto *Horas* por compañía, nombres de tabla/campo v19) deben estar **confirmados contra la BD real**. Un xmlid inventado o un `ref()` a un external id inexistente hace fallar la instalación del módulo. El doc 09 es la checklist que cierra ese GATE.

> 💾 **Norma de backup DURA (no blanda) — C6.** Es **OBLIGATORIO** un backup **manual, verificado y ETIQUETADO** inmediatamente **ANTES** de cualquier cambio de datos maestros o de permisos en PRO. Referencia operativa: **`new/doc/04-backups-y-restauracion.md`**, script **`/root/backup_odoo19_prod.sh`**. **RPO objetivo** para `grupo_zambudio_prod`: **≤ 4 horas** (el incidente costó ~24 h de trabajo perdido; no se admite ventana mayor para maestros/permisos). **Prueba de restauración TRIMESTRAL** con **RTO documentado**. "Backup previo" en cualquier fase de abajo significa exactamente esto, no un dump sin verificar.

---

## Fase 0 — Inventario y diagnóstico (sin cambios, solo lectura)

**Objetivo:** saber quién tiene qué HOY. Especialmente: quién tiene `base.group_system`, quién puede escribir/borrar en `uom.uom` y `product.template`, y qué usuarios acumulan grupos incompatibles (SoD). Todo esto es **solo lectura**: se puede correr en PRO sin riesgo.

### 0.1 Pasos `[UI]`

1. **Ajustes → Usuarios y compañías → Usuarios.** Filtrar/agrupar. Añadir a la vista lista las columnas de grupos si se quiere (o usar SQL, más fiable).
2. Para cada usuario sospechoso, abrir su ficha y revisar la pestaña de permisos: desplegables por app (Ninguno / User / Manager / Administrator) y la sección de grupos técnicos.
3. **Ajustes → Técnico → Seguridad → Reglas de acceso a modelos** y **Reglas de registro**: revisar el estado nativo antes de tocar nada.

> Recordatorio v19: los perfiles de sistema se muestran ahora agrupados por **privilegio/categoría**, no como en v17/18. La etiqueta visible exacta de `base.group_system` y `base.group_user` puede haber cambiado **(verificar en PRE la etiqueta que aparece en la ficha de usuario)**. Lo estable es el **xmlid**, no el texto. No confundir el "Administrator" de una app (p. ej. Ventas → Administrator) con `base.group_system` (administrador de sistema).

### 0.2 Consultas `[SQL-RO]` (seguras en PRO)

> ⚠️ **Membresía directa vs efectiva (importante en v19).** En el modelo, `group_ids` son los grupos **directos** y `all_group_ids` los **efectivos** (directos + implicados por `implied_ids`). En la **BD**, la tabla puente de asignación directa sigue siendo (probablemente) `res_groups_users_rel` (columnas `gid`,`uid`), pero **puede existir además una tabla/relación para el cierre transitivo** (all_group_ids) — **(verificar en PRE los nombres reales de ambas tablas)**. Las consultas de abajo usan la tabla directa: para `base.group_system` esto es fiable (ningún grupo funcional lo implica), pero para "quién puede escribir uom" (0.2.c) un permiso concedido a un grupo **implicado** podría no aparecer. Cuando importe la membresía efectiva, repetir la consulta contra la relación transitiva.

**a) Quién tiene `base.group_system` ("Administrador de sistema") — el grupo del incidente:**

```sql
-- [SQL-RO] Usuarios con base.group_system (acceso a Ajustes + datos maestros de sistema)
SELECT u.id, u.login, p.name, u.active
FROM res_users u
JOIN res_partner p        ON p.id = u.partner_id
JOIN res_groups_users_rel rel ON rel.uid = u.id
JOIN ir_model_data d      ON d.res_id = rel.gid AND d.model = 'res.groups'
WHERE d.module = 'base' AND d.name = 'group_system'
ORDER BY u.active DESC, u.login;
```

**b) Quién tiene el "Access Rights" (`base.group_erp_manager`) y el developer/no_one:**

```sql
-- [SQL-RO] Usuarios con grupos de administración transversal
SELECT d.module||'.'||d.name AS grupo, u.id, u.login, p.name
FROM res_users u
JOIN res_partner p ON p.id = u.partner_id
JOIN res_groups_users_rel rel ON rel.uid = u.id
JOIN ir_model_data d ON d.res_id = rel.gid AND d.model = 'res.groups'
WHERE (d.module,d.name) IN
      (('base','group_system'),('base','group_erp_manager'),('base','group_no_one'))
ORDER BY grupo, u.login;
```

**c) Quién puede ESCRIBIR/BORRAR `uom.uom` (el modelo que se rompió) — vía ACL:**

```sql
-- [SQL-RO] Grupos con write/unlink sobre datos maestros y qué usuarios los tienen
SELECT m.model, a.name AS acl,
       g_d.module||'.'||g_d.name AS grupo,
       a.perm_read, a.perm_write, a.perm_create, a.perm_unlink,
       string_agg(u.login, ', ' ORDER BY u.login) AS usuarios
FROM ir_model_access a
JOIN ir_model m         ON m.id = a.model_id
LEFT JOIN res_groups g  ON g.id = a.group_id
LEFT JOIN ir_model_data g_d ON g_d.res_id = g.id AND g_d.model = 'res.groups'
LEFT JOIN res_groups_users_rel rel ON rel.gid = g.id
LEFT JOIN res_users u   ON u.id = rel.uid AND u.active
WHERE m.model IN ('uom.uom','uom.category','product.template','product.product',
                  'account.account','account.journal','account.analytic.account',
                  'account.analytic.plan','ir.sequence','res.currency')
  AND (a.perm_write OR a.perm_unlink)
GROUP BY m.model, a.name, grupo, a.perm_read, a.perm_write, a.perm_create, a.perm_unlink
ORDER BY m.model, grupo;
```

> Interpretación: cualquier grupo funcional que aparezca con `perm_write=t` o `perm_unlink=t` sobre `uom.uom`/`product.template` es un vector del incidente. Los ACL **se suman (OR)**: basta un grupo con el permiso para poder escribir. Ojo: el superusuario real (uid 1, OdooBot/`__system__`) ignora TODO esto; no aparecerá aquí y es correcto. Recuerda la nota de membresía efectiva: si `group_id` es NULL en un ACL, ese permiso lo tiene **todo el mundo** (ACL sin grupo = global).

**d) Reglas de registro existentes que mencionan compañía (inventario multiempresa nativo):**

```sql
-- [SQL-RO] Inventario de record rules por compañía (para Fase 3)
SELECT r.id, m.model, r.name, r.domain_force, r."global" AS es_global
FROM ir_rule r
JOIN ir_model m ON m.id = r.model_id
WHERE r.domain_force ILIKE '%company_id%'
ORDER BY m.model;
```

> Nota: `ir_rule.global` es un campo **calculado y almacenado** (una regla es global si no tiene grupos asociados). Usarlo directamente es más robusto que reconstruir el join con la tabla puente `rule_group_rel` **(verificar nombre en PRE)**. `global` es palabra reservada en SQL → citarla (`r."global"`).

**e) Distribución analítica sin compañía apuntando a la cuenta 90 (raíz de la fuga CITRIC — ver [[05-record-rules-multiempresa]]):**

```sql
-- [SQL-RO] Modelos de distribución analítica peligrosos (company NULL -> cuenta 90 de AUNNA)
SELECT id, company_id, account_prefix, partner_id, product_id, analytic_distribution
FROM account_analytic_distribution_model
WHERE company_id IS NULL
  AND analytic_distribution::text LIKE '%90%'
ORDER BY id;
```

> ⚠️ `analytic_distribution` es un JSON cuyas **claves son IDs de `account.analytic.account`**, no el código "90". El `LIKE '%90%'` es un **primer cribado tosco** (puede dar falsos positivos: id 190, 900…). Para precisión, resolver antes el id real de la cuenta 90 y filtrar por esa clave: `analytic_distribution ? '<id_cuenta_90>'`. Confirmar el id en cada entorno **(verificar en PRE)**.

**f) Usuarios con demasiadas compañías en `company_ids` (fuga cross-company):**

```sql
-- [SQL-RO] Cuántas compañías tiene marcadas cada usuario
SELECT u.login, p.name, count(rel.cid) AS n_companias,
       string_agg(c.name, ', ') AS companias
FROM res_users u
JOIN res_partner p ON p.id = u.partner_id
JOIN res_company_users_rel rel ON rel.user_id = u.id
JOIN res_company c ON c.id = rel.cid
WHERE u.active
GROUP BY u.login, p.name
HAVING count(rel.cid) > 1
ORDER BY n_companias DESC;
```

> Nota: `res_company_users_rel` con columnas `user_id`/`cid` es el nombre habitual **(verificar en PRE)**.

### 0.3 Entregable de la Fase 0

Una hoja (tabla) con:

| Login | Nombre | Compañías (`company_ids`) | ¿group_system? | ¿erp_manager? | Grupos de app (nivel) | ¿write en uom/product? | Riesgo SoD | Acción propuesta |
|---|---|---|---|---|---|---|---|---|
| … | … | … | Sí/No | Sí/No | Ventas:Manager, Cont:User… | Sí/No | (p.ej. compra+pago) | Quitar system, bajar a User… |

**Criterio de "exceso de privilegio" a marcar en rojo:**
- Tiene `base.group_system` y NO es custodio designado.
- Puede escribir `uom.uom` / `product.template` y no es custodio de datos maestros.
- Acumula funciones incompatibles (ver matriz SoD en [[02-catalogo-de-roles]] §5): compras + pago/conciliación; aprobador de gastos que se autoaprueba; aprobador de partes que imputa en el mismo proyecto.
- Tiene más compañías en `company_ids` de las que realmente opera.

---

## Fase 1 — Quick wins sin riesgo (alto impacto, reversible)

**Objetivo:** cerrar el vector del incidente ya, con cambios reversibles y de bajo riesgo. Si solo se hiciera esto, el incidente no se repetiría.

### 1.1 Quitar `base.group_system` y modo desarrollador a todos los no-custodios `[UI]` ⚠

**Por qué:** `base.group_system` = acceso a Ajustes, menús técnicos, UdM, secuencias, Studio. Es **custodia, no un rol de trabajo**. Ningún perfil funcional (contabilidad, ventas, almacén, proyecto…) lo necesita para su día a día.

Pasos:
1. Partir de la lista 0.2.a/b.
2. Para cada usuario que NO sea custodio de sistema (dejar solo 1 titular + 1 suplente): **Ficha de usuario → quitar el grupo Administrator/Settings** (`base.group_system`) y `base.group_no_one` si lo tuviera explícito.
3. Confirmar que conserva sus grupos funcionales (p. ej. `account.group_account_user`, `sales_team.group_sale_salesman`) para no romperle el trabajo.
4. Desactivar modo desarrollador como comportamiento por defecto (no se fuerza por usuario; el peligro real es el grupo, no el modo).

**Probar en PRE:**
- Coger un usuario de prueba representativo de cada rol, quitarle system en PRE, y verificar que:
  - Ya NO ve el menú **Ajustes** ni **Aplicaciones/Apps**.
  - Sigue pudiendo hacer su trabajo (crear pedido, imputar parte, registrar factura según su rol).
- Anotar qué menús de configuración concretos desaparecen (algunos cuelgan de `base.group_erp_manager`, no de `group_system`): documentarlo antes de PRO.

**Aplicar en PRO:** ⚠ es un cambio de UI, no viaja con módulo.
- Backup previo (ver Runbook §Backup). Aunque quitar grupos es reversible, backup igual.
- Ventana de bajo uso. Avisar a los afectados ("perderéis el menú Ajustes; vuestro trabajo diario sigue igual; si os falta algo, ticket").
- Aplicar usuario por usuario. Verificar login de una muestra tras el cambio.
- **Rollback:** volver a añadir el grupo al usuario (inmediato).

### 1.2 Forzar 2FA a custodios y administradores `[UI]`

**Por qué:** las cuentas con `base.group_system`/`erp_manager` son las que más daño hacen. 2FA es nativo en Enterprise, sin módulo OCA.

Pasos:
1. **Ajustes → Permisos → "Enforce two-factor authentication".** En v19 se puede aplicar a Empleados o a Todos.
2. Como mínimo, exigir 2FA a los 1-2 custodios de sistema y al custodio de datos maestros. Recomendado: a todos los internos.
3. Cada custodio configura su TOTP (Google Authenticator / similar) o FIDO.

**Probar en PRE:** activar el enforce, cerrar sesión, comprobar el flujo de alta de 2FA y login. Confirmar que las **integraciones/API** (usuarios técnicos) no quedan bloqueadas por 2FA (las API keys no usan TOTP, pero verificar que ningún usuario de integración se autentica por login/contraseña de UI).

**Aplicar en PRO:** ventana coordinada con los custodios presentes (necesitan enrolar su móvil). Rollback: desactivar enforce.

### 1.3 Blindar UdM *Horas* y producto *Horas* — el corazón del incidente `[XML]` ⚠

**Por qué:** aunque quitemos `group_system` a los funcionales, hay que blindar los datos maestros a nivel de datos, no solo de menú. El mecanismo robusto es una **record rule global restrictiva**, porque las globales van en AND y no se sortean con otro grupo; el ACL es aditivo y no "resta".

**Mecanismo elegido:** regla global con dominio siempre-falso sobre `write`/`unlink`/`create`, dejando `read` libre. Las record rules **no** aplican al superusuario real (uid 1). Un "Administrador" (`group_system`) SÍ queda frenado — que es exactamente lo que falló.

> ⚠️ **Implicación práctica que hay que entender antes de elegir este patrón.** Con la regla GLOBAL, **nadie que entre por la interfaz** (ni siquiera un `group_system`) puede editar la UdM: el uid 1 (OdooBot) **no es una cuenta con la que se hace login normalmente** en Enterprise. Por tanto, para una edición legítima de la UdM *Horas* el custodio tiene solo dos vías:
> - **(a)** Desactivar temporalmente la regla en **Técnico → Reglas de registro** (bajo doble control: ticket + testigo), editar, y **reactivarla** inmediatamente; o
> - **(b)** Usar el **patrón OR con `group_master_data_custodian`** (Fase 2.1), que delega la edición sin tocar la credencial de superusuario.
> **Recomendación:** usar el patrón OR (delegado) como **modo por defecto** para datos maestros editables con cierta frecuencia (productos, cuentas, diarios), y reservar la **regla global** solo para las "joyas de la corona" que casi nunca cambian (UdM *Horas* y su categoría). Documentar el procedimiento (a) en [[00-principios-y-gobernanza]].

Fichero de referencia copiable (patrón real ya en el repo: `new/zambudio_timesheet_approval_by_project/security/ir_rule.xml`).

```xml
<!-- [XML] zambudio_permisos/security/ir_rule_master_lock.xml -->
<odoo>
  <!-- 1) UdM: nadie salvo superusuario modifica/borra/crea -->
  <record id="uom_uom_lock_rule" model="ir.rule">
    <field name="name">UdM: solo superusuario (custodio) puede modificar/crear/borrar</field>
    <field name="model_id" ref="uom.model_uom_uom"/>
    <field name="domain_force">[(0, '=', 1)]</field>   <!-- siempre falso -->
    <field name="groups" eval="[]"/>                    <!-- GLOBAL: sin grupos = AND -->
    <field name="perm_read"   eval="False"/>            <!-- lectura NO restringida -->
    <field name="perm_create" eval="True"/>
    <field name="perm_write"  eval="True"/>
    <field name="perm_unlink" eval="True"/>
  </record>

  <!-- 2) Categoría de UdM (ratio/tipo Working Time: si se corrompe, se rompen las conversiones hora<->dia) -->
  <record id="uom_category_lock_rule" model="ir.rule">
    <field name="name">Categoria UdM: solo superusuario</field>
    <field name="model_id" ref="uom.model_uom_category"/>   <!-- (verificar en PRE: en v18/19 hubo refactor de UoM; confirmar model_uom_category vs alternativo) -->
    <field name="domain_force">[(0, '=', 1)]</field>
    <field name="groups" eval="[]"/>
    <field name="perm_read"   eval="False"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_write"  eval="True"/>
    <field name="perm_unlink" eval="True"/>
  </record>
</odoo>
```

**El producto *Horas* no tiene xmlid del núcleo** (es un `product.template` concreto del cliente). No se puede blindar por xmlid genérico sin congelar TODO el catálogo. Dos opciones:

- **Opción A (recomendada, quirúrgica — patrón P3 "GLOBAL scoped por id"):** blindar solo ESE/ESOS producto(s) por su id, con una regla **global** que impide write/unlink sobre el/los registro(s) concreto(s) para todo el mundo, y **re-permite al custodio**. El resto del catálogo sigue editable por sus managers. Requiere resolver el id en cada entorno (distinto en PRE y PRO) y hay **un producto de servicio "Horas" por compañía** (AUNNA, CITRIC, MONTOYA, ii → varios ids).

> 🛑 **BUG A ERRADICAR — `ref()` NO existe dentro de `domain_force`.** El contexto de evaluación de `ir.rule.domain_force` expone `user`, `time`, `company_id`, `company_ids` (y `env` vía `user.env`), pero **NO** una función `ref`. Escribir `ref('modulo.xmlid')` en `domain_force` provoca **`NameError` EN RUNTIME** (la regla revienta y, según versión, bloquea el acceso al modelo). Cualquier borrador previo con `ref(...)` suelto en el dominio es incorrecto. Formas correctas de referenciar un registro por xmlid dentro del dominio:
> - `user.env.ref('zambudio_permisos.product_template_horas_aunna').id` (si el producto tiene un external id estable), **o**
> - resolver los ids reales en cada BD y escribir una **LISTA**: `[('id','not in',[id1,id2,...])]` (nunca `!=` con un solo id: hay varios productos "Horas").

```xml
<!-- [XML] zambudio_permisos/security/ir_rule_product_horas.xml
     Bloquear write/unlink SOLO del/los producto(s) de servicio "Horas".
     El custodio SI puede editarlo; NADIE mas (ni ventas/stock/contabilidad manager).
     ⚠️ NUNCA usar ref(...) dentro de domain_force -> NameError. Usar user.env.ref(...).id
        o una LISTA de ids resueltos en la BD (ver SQL de abajo).
     ⚠️ El id del producto Horas DIFIERE entre PRE y PRO y hay uno POR COMPANIA:
        resolver los ids en cada entorno, o crear su external id via post_init_hook
        localizandolo por service_policy='delivered_timesheet' / default_code. -->

<!-- Regla sobre product.template (el maestro) -->
<record id="product_tmpl_horas_lock_rule" model="ir.rule">
  <field name="name">Producto Horas (template): solo el custodio escribe/borra</field>
  <field name="model_id" ref="product.model_product_template"/>
  <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id', 'not in', [
        user.env.ref('zambudio_permisos.product_template_horas_aunna').id,
        user.env.ref('zambudio_permisos.product_template_horas_citric').id,
        user.env.ref('zambudio_permisos.product_template_horas_montoya').id,
        user.env.ref('zambudio_permisos.product_template_horas_ii').id,
    ])]</field>
  <field name="groups" eval="[]"/>                    <!-- GLOBAL: sin grupos = AND -->
  <field name="perm_read"   eval="False"/>            <!-- lectura NO restringida (desplegables de partes) -->
  <field name="perm_create" eval="False"/>
  <field name="perm_write"  eval="True"/>
  <field name="perm_unlink" eval="True"/>
</record>

<!-- Regla GEMELA obligatoria sobre product.product (la VARIANTE es la que usa el parte de horas) -->
<record id="product_prod_horas_lock_rule" model="ir.rule">
  <field name="name">Producto Horas (variante): solo el custodio escribe/borra</field>
  <field name="model_id" ref="product.model_product_product"/>
  <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('product_tmpl_id', 'not in', [
        user.env.ref('zambudio_permisos.product_template_horas_aunna').id,
        user.env.ref('zambudio_permisos.product_template_horas_citric').id,
        user.env.ref('zambudio_permisos.product_template_horas_montoya').id,
        user.env.ref('zambudio_permisos.product_template_horas_ii').id,
    ])]</field>
  <field name="groups" eval="[]"/>
  <field name="perm_read"   eval="False"/>
  <field name="perm_create" eval="False"/>
  <field name="perm_write"  eval="True"/>
  <field name="perm_unlink" eval="True"/>
</record>
```

> Si prefieres NO depender de external ids, resuelve los ids en cada BD y sustituye las listas `user.env.ref(...).id` por la lista literal de ids `[id1, id2, ...]`. Para obtenerlos:
> ```sql
> -- [SQL-RO] localizar los product.template "Horas" de servicio por compañía
> SELECT pt.id, pt.default_code, pt.service_policy, pt.company_id
> FROM product_template pt
> WHERE pt.type = 'service' AND pt.service_policy = 'delivered_timesheet'
> ORDER BY pt.company_id;   -- (verificar en PRE; ajustar filtro por default_code si hace falta)
> ```
> **(verificar en PRE los ids/xmlids reales del producto Horas en cada BD y en cada compañía — AUNNA, CITRIC, MONTOYA, ii.)** Si algún producto no tiene external id, **crearlo con un `post_init_hook`** que lo localice por `service_policy='delivered_timesheet'` / `default_code` y le fije el `ir.model.data`, para que la regla lo referencie de forma estable en PRE y PRO por igual.
> ⚠️ Como el dominio scoped afecta solo a esos ids, la regla es **inocua para el resto del catálogo** (los demás productos cumplen `id not in [...]` → editables por sus managers). El custodio, por el `has_group`, sí puede escribir. `perm_write=True` cubre **cualquier** write: también renombrar, **archivar** (`active=False`), cambiar `type` y `sale_ok`. No restringe `read`.

- **Opción B (más amplia):** reforzar además con `groups=` a nivel de vista/field en `name` del producto y en `uom_id`, para que ni se muestre editable a no-custodios (defensa de UI + ACL). Ver [[04-blindaje-datos-maestros]] §3. Recuerda que el atributo `groups` en vistas usa xmlids de grupo y NO sustituye a la record rule (es solo capa de UI).

**Reforzar con ACL de solo lectura para grupos funcionales** (capa 2, complementaria). No es el mecanismo principal (aditivo), pero deja explícito el estándar de lectura:

```csv
# [CSV] zambudio_permisos/security/ir.model.access.csv  (solo READ para el grupo general)
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_uom_uom_readonly,uom.uom readonly all,uom.model_uom_uom,base.group_user,1,0,0,0
access_uom_categ_readonly,uom.category readonly all,uom.model_uom_category,base.group_user,1,0,0,0
```

> ⚠ Cuidado: **no** basta con este CSV. Los ACL nativos que ya conceden write (p. ej. a `base.group_system`) siguen sumando; por eso la record rule GLOBAL de arriba es la que realmente frena. El CSV es refuerzo/lectura, no la barrera. Además, **no** declares un ACL con `perm_read=0` sobre `uom.uom` para `base.group_user`: dejaría sin leer la UdM a todos y **rompería los desplegables** de los partes de horas.

**Probar en PRE (imprescindible, este es el cambio crítico):**
1. Instalar el módulo `zambudio_permisos` en PRE.
2. Con un usuario que tenga `base.group_system` (simulando al del incidente): intentar renombrar la UdM *Horas* → **debe fallar** con error de acceso. Intentar cambiar el ratio de la categoría → debe fallar. Intentar convertir el producto *Horas* en producto de venta / cambiarle la UdM → debe fallar.
3. **Prueba por rol funcional manager (obligatoria — gap real del incidente).** Con un usuario de prueba de CADA rol manager, iniciar sesión y comprobar el par "NO puede tocar el maestro / SÍ puede operar":
   - **Ventas manager (`sales_team.group_sale_manager`):** NO puede renombrar ni **archivar** (`active=False`) el producto *Horas*, ni marcarlo `sale_ok`/cambiarle la UdM → **debe fallar**; SÍ puede crear/confirmar un presupuesto y editar/archivar un producto **normal** → debe funcionar.
   - **Almacén manager (`stock.group_stock_manager`):** NO puede renombrar/archivar el producto *Horas* ni tocar la UdM *Horas* ni su categoría → **debe fallar**; SÍ puede hacer un ajuste de inventario, validar un albarán y editar categorías/productos normales → debe funcionar.
   - **Contabilidad manager (`account.group_account_manager`):** NO puede renombrar/archivar el producto *Horas* ni la UdM *Horas* → **debe fallar**; SÍ puede seguir su operativa (crear factura, asiento, editar plan de cuentas/diarios según su rol) → debe funcionar.
   > Objetivo de la prueba: confirmar que el blindaje frena a los tres perfiles manager **sin** romperles su trabajo diario. Repetir el intento sobre `product.template` **y** sobre la variante `product.product` (la que usa el parte).
4. Confirmar la vía de edición legítima (patrón OR del custodio, o desactivación temporal de la regla global bajo doble control — según lo elegido en 1.3): el usuario **custodio** (`zambudio_permisos.group_master_data_custodian`) SÍ puede renombrar el producto *Horas* y la UdM.
5. **Flujos que NO se deben romper:** crear e imputar un parte de horas, facturar por partes (`sale_timesheet`), cálculo WIP. Todo debe seguir funcionando (solo hemos bloqueado escritura de maestros, no la operativa).
6. Verificar que la lectura de UdM sigue disponible en desplegables (no hemos restringido `read`).

**Aplicar en PRO:** ⚠
- **GATE doc 09 cerrado** (ids/xmlids del producto *Horas* por compañía y grupo custodio verificados en PRE — [[09-anexo-verificacion-y-checklist]]).
- **Backup DURO (C6):** manual, verificado y **etiquetado** justo antes (`/root/backup_odoo19_prod.sh`, ver `new/doc/04-backups-y-restauracion.md`).
- Desplegar el módulo (mismo commit que en PRE). Recordar: los **ids/xmlids del producto Horas son distintos** en PRO y hay **uno por compañía** (AUNNA, CITRIC, MONTOYA, ii) → crear sus external ids en PRO (o el `post_init_hook`) **antes** de que carguen las reglas `product.template` **y** `product.product` que los referencian (si no existe el xmlid, el módulo fallará al instalar).
- Ventana corta. Tras instalar: repetir las pruebas 2-6 (incluida la prueba por rol manager) con cuentas de test en PRO.
- **Rollback:** desinstalar el módulo (elimina sus record rules) o desactivar las reglas desde Técnico → Reglas de registro. Reversible.

### 1.4 Restringir el botón Exportar (opcional, quick win) `[UI]`/`[XML]`

**Por qué:** limita fuga de datos maestros/contactos. Nativo: `base.group_allow_export` ("Allowed to Export"). Quitarlo a quien no deba exportar. OCA `web_disable_export_group` / `base_export_manager` como refuerzo (verificar port a 19 — ver [[07-auditoria-trazabilidad-hardening]]).

Probar en PRE (que los perfiles que exportan legítimamente conservan el permiso). Aplicar en PRO por UI o módulo.

---

## Fase 2 — Roles: crear el catálogo y reasignar usuarios

**Objetivo:** materializar el catálogo de roles de [[02-catalogo-de-roles]] con mínimo privilegio, y reasignar a cada usuario su rol limpio. Incluye crear el rol nuevo **Custodio de Datos Maestros**.

### 2.1 Crear el grupo custodio `[XML]`

> 📌 **Nombre canónico (fuente de verdad).** El módulo de refuerzo es **`zambudio_permisos`** y el grupo custodio tiene el xmlid **`zambudio_permisos.group_master_data_custodian`** (rol "Custodio de Datos Maestros"). Es un grupo **funcional**: NO implica `base.group_system` ni es el uid 1; las reglas de blindaje lo re-permiten explícitamente. Quedan **obsoletos** (usar siempre el canónico): `zambudio_custom`, `zambudio_master_data`, `zambudio_master_data_custody`, `zambudio_master_data_lock`, `zambudio_security_hardening`, `group_master_data_custody` y cualquier otra variante — si aparecen en versiones previas son históricas. Si el grupo se crea por UI en vez de por módulo, su xmlid real se resolverá en PRE **(verificar en PRE)**.

```xml
<!-- [XML] zambudio_permisos/security/groups.xml -->
<odoo>
  <!-- (opcional en v19) Privilegio propio para agrupar el rol en Ajustes -->
  <record id="privilege_master_data" model="res.groups.privilege">
    <field name="name">Datos Maestros</field>
    <field name="category_id" ref="base.module_category_administration"/> <!-- (verificar en PRE el xmlid de categoría) -->
  </record>

  <record id="group_master_data_custodian" model="res.groups">
    <field name="name">Custodio de Datos Maestros</field>
    <!-- v19: el grupo cuelga de un privilege (opcional). Si se omite, el grupo sigue funcionando. -->
    <field name="privilege_id" ref="privilege_master_data"/>
    <field name="implied_ids" eval="[Command.link(ref('base.group_user'))]"/>
    <field name="comment">Unico rol (aparte del superusuario) autorizado a escribir/borrar UdM, productos, plan de cuentas, diarios, cuentas y planes analiticos, secuencias y monedas. 1-2 personas.</field>
  </record>
</odoo>
```

> ⚠️ En v19 `privilege_id` apunta a `res.groups.privilege` (no directamente a `ir.module.category`). Si no quieres crear un privilege propio, **omite el campo `privilege_id`** por completo: el grupo funciona igual y solo aparecerá sin categoría en la ficha. **No** uses `category_id` en `res.groups` (ya no existe en v19).

Y el patrón OR para que el custodio SÍ pueda editar donde el resto no. Para cada modelo maestro: una regla que bloquea a `base.group_user` y otra que re-permite al custodio (las reglas **de distintos grupos** sobre el mismo modelo se combinan en OR).

```xml
<!-- Bloquea a todo internal user -->
<record id="pt_block_users" model="ir.rule">
  <field name="name">Producto: bloquear a usuarios internos</field>
  <field name="model_id" ref="product.model_product_template"/>
  <field name="domain_force">[(0, '=', 1)]</field>
  <field name="groups" eval="[Command.link(ref('base.group_user'))]"/>
  <field name="perm_read" eval="False"/>
  <field name="perm_create" eval="True"/><field name="perm_write" eval="True"/><field name="perm_unlink" eval="True"/>
</record>
<!-- Re-permite al custodio (OR gana) -->
<record id="pt_allow_custodian" model="ir.rule">
  <field name="name">Producto: permitir al custodio</field>
  <field name="model_id" ref="product.model_product_template"/>
  <field name="domain_force">[(1, '=', 1)]</field>
  <field name="groups" eval="[Command.link(ref('zambudio_permisos.group_master_data_custodian'))]"/>
  <field name="perm_read" eval="False"/>
  <field name="perm_create" eval="True"/><field name="perm_write" eval="True"/><field name="perm_unlink" eval="True"/>
</record>
```

> ⚠ **Límites del patrón OR (dos avisos):**
> 1. Si el usuario está en OTRO grupo con una regla **permisiva** sobre el mismo modelo, "gana" la permisiva. Por eso para lo MÁS crítico (UdM/categoría) se prefiere la **regla global** de 1.3.
> 2. El custodio hereda `base.group_user` (por `implied_ids`), así que **le aplica también** la regla `pt_block_users`. Al combinarse en OR con `pt_allow_custodian` (dominio verdadero), el resultado es "permitido" → correcto. Verifícalo en PRE: bloquear a `base.group_user` y estar seguro de que el custodio, que también es `base.group_user`, sigue pudiendo escribir gracias al OR.

### 2.2 Catálogo rol → grupos (resumen; detalle en [[02-catalogo-de-roles]])

| Perfil | Grupos base | App-por-app (xmlids) | NO debe tener |
|---|---|---|---|
| **Consultor/Técnico (imputa horas)** | `base.group_user` | `project.group_project_user`, `hr_timesheet.group_hr_timesheet_user`, `planning.group_planning_user` | Nada de Manager; sin write en productos/UdM; sin `group_system` |
| **Jefe de Proyecto** | `base.group_user` | `project.group_project_manager`, `hr_timesheet.group_hr_timesheet_approver`, `sales_team.group_sale_salesman`, `analytic.group_analytic_accounting` (lectura) | `group_system` |
| **Administración/Contabilidad** | `base.group_user` | `account.group_account_user` (o `account.group_account_manager` si lleva cierre), `analytic.group_analytic_accounting` | `group_system`; write en maestros salvo custodio |
| **Compras** | `base.group_user` | `purchase.group_purchase_user`, `stock.group_stock_user` (lectura) | `account.group_account_manager` (SoD: quien compra no paga) |
| **Almacén** | `base.group_user` | `stock.group_stock_user` (o `stock.group_stock_manager`), toggles según operativa | `group_system` |
| **Producción/Taller** | `base.group_user` | `mrp.group_mrp_user`, `repair.group_repair_user` (verificar en PRE), `stock.group_stock_user` | — |
| **RRHH** | `base.group_user` | `hr.group_hr_user`/`hr.group_hr_manager`, `hr_holidays.group_hr_holidays_manager`, `hr_expense.group_hr_expense_manager` | `group_system` |
| **Comercial** | `base.group_user` | `sales_team.group_sale_salesman` / `sales_team.group_sale_salesman_all_leads` | `sales_team.group_sale_manager` salvo responsable (`sale.group_sale_manager` es alias → usar `sales_team.group_sale_manager`) |
| **Dirección/Gerencia** | `base.group_user`, `base.group_multi_company` | Managers de operaciones + `account.group_account_readonly` | `group_system`; contabilidad en solo lectura |
| **Custodio de Datos Maestros** | `base.group_user` + `group_master_data_custodian` | write/unlink maestros | otras funciones operativas (rol dedicado) |
| **Superadmin/Custodio de sistema** | `base.group_system`, `base.group_erp_manager`, `base.group_no_one` | Todo | — (1 titular + 1 suplente, auditado) |
| **Portal Cliente** | `base.group_portal` | (ninguno interno) | NUNCA `base.group_user` |

> Notas de herencia (para no asignar grupos redundantes):
> - `account.group_account_user` **ya implica** `account.group_account_invoice` y `account.group_account_readonly` → no hace falta añadirlos aparte (verificado en la definición nativa). Añadir `account.group_account_invoice` solo tiene sentido para un perfil de "solo facturación" que NO deba tener el resto de contabilidad.
> - `base.group_system` implica `base.group_erp_manager` en el árbol nativo; listar ambos en el superadmin es explícito, no dañino **(verificar en PRE la cadena de implied_ids)**.
> - `analytic.group_analytic_accounting`, `sales_team.group_sale_salesman_all_leads`, `account.group_account_readonly`, `hr_timesheet.group_hr_timesheet_approver` → **confirmados**. `repair.group_repair_user` → **(verificar en PRE)** (Repair se rehízo en versiones recientes).

> Recomendación de gobernanza: valorar OCA **`base_user_role`** (roles = agregación fija de grupos; impide añadir grupos sueltos a mano). **Verificar port a 19** antes de adoptarlo (ver [[07-auditoria-trazabilidad-hardening]] §3). Mientras tanto, gestionar los roles con grupos nativos + esta tabla.

### 2.3 Reasignación de usuarios `[UI]`

1. Con la hoja de Fase 0, asignar a cada usuario su rol del catálogo.
2. Quitar grupos sobrantes (los que no pertenecen a su rol).
3. Ajustar `company_ids`: dejar **solo** las compañías donde realmente opera (mínimo privilegio de compañía — el control más eficaz contra fugas cross-company). Revisar también `company_id` (compañía por defecto): debe pertenecer a `company_ids`.

**Probar en PRE:** por cada rol, un usuario de prueba recorre su checklist funcional (crear/leer/editar lo que le toca; verificar que NO puede lo que no le toca). Especial atención al Consultor: debe imputar horas y NADA de maestros.

**Aplicar en PRO:** backup, ventana, cambios usuario a usuario, verificación por muestra. Rollback: reasignar grupos previos (tener la hoja Fase 0 como estado anterior).

---

## Fase 3 — Record rules de datos maestros y multiempresa

**Objetivo:** (a) reforzar el aislamiento AUNNA/CITRIC en lectura y (b) impedir mezclar compañías al guardar. Ver [[05-record-rules-multiempresa]] y [[05-record-rules-multiempresa]].

### 3.1 Auditar reglas nativas de compañía `[SQL-RO]`

Correr la query 0.2.d. Confirmar que existen y no están huérfanas las reglas por modelo (`sale.order`, `purchase.order`, `account.move`, `account.journal`, `stock.picking`, `project.project`, `project.task`, `account.analytic.line`, `hr.employee`). Una desinstalación/reinstalación de app puede haberlas dejado rotas. El dominio canónico multiempresa en v19 es:

```
['|', ('company_id','=',False), ('company_id','in',company_ids)]
```

> `company_ids` en el dominio de una record rule se refiere a las **compañías permitidas activas** del usuario en la sesión (las que tiene marcadas en el selector), no a todo `company_ids` de la ficha. Es el comportamiento nativo correcto: no lo cambies.

### 3.2 Reglas custom de refuerzo `[XML]`

Para cualquier modelo custom que ate documentos a compañía, regla **global** con el patrón canónico (globales = AND, no se saltan):

```xml
<record id="rule_mimodelo_multicompany" model="ir.rule">
  <field name="name">MiModelo multi-company</field>
  <field name="model_id" ref="model_mi_modelo"/>
  <!-- NO se pone <field name="global">: es un campo CALCULADO.
       Una regla es GLOBAL simplemente por NO tener grupos asociados.
       (si acaso, dejar explicito el vacio) -->
  <field name="groups" eval="[]"/>
  <field name="domain_force">['|', ('company_id','=',False), ('company_id','in',company_ids)]</field>
</record>
```

> ⚠️ **Corrección importante respecto a borradores previos:** `ir.rule.global` es un campo **calculado y de solo lectura** (`compute` a partir de si `groups` está vacío). Escribir `<field name="global" eval="True"/>` **no** hace la regla global (se ignora o da comportamiento inconsistente). La forma correcta y única de crear una regla global es **no asignarle grupos**. Para leer si una regla es global, sí puedes consultar el campo calculado (query 0.2.d).

> Ejemplo real en el repo: `new/aunna_project_cost_account_moves/security/project_cost_move_link_rules.xml` (usa `[('company_id','in',company_ids)]`; añadir el `'|',('company_id','=',False)` si algún enlace pudiera no tener compañía, para no ocultar registros sin compañía).

### 3.3 `check_company=True` en campos relacionales custom `[XML]`

Defensa de **escritura** (las record rules solo filtran lectura). En todo campo relacional a cuenta/diario/analítica/almacén de un modelo con compañía:

```python
account_id  = fields.Many2one('account.account',  check_company=True)
journal_id  = fields.Many2one('account.journal',  check_company=True)
analytic_id = fields.Many2one('account.analytic.account', check_company=True)
```

Esto es lo que habría **bloqueado al guardar** la inyección de la cuenta 90 en un parte de CITRIC.

> Requisito: `check_company=True` solo actúa si el modelo tiene un campo `company_id` (o define `_check_company_auto`). Verifica que el modelo custom expone `company_id`; si no, el check no dispara. **(verificar en PRE por modelo.)** Ojo: `account.analytic.account` cuelga de un plan y su `company_id` puede ser nulo (analítica compartida) — en ese caso `check_company` no restringe; el aislamiento real de la analítica se logra con la corrección de 3.4.

### 3.4 Sanear distribución analítica cross-company `[SQL-RO]` + corrección ⚠

1. `[SQL-RO]` query 0.2.e: localizar modelos `account.analytic.distribution.model` con `company_id IS NULL` que apunten a la 90 (usando el id real de la cuenta, no `LIKE '%90%'`).
2. Corrección (⚠ **primero en PRE**): setear `company_id` en cada modelo de distribución. Crear el par correcto: uno `company_id=1` → cuenta 90 (AUNNA), otro `company_id=2` → cuenta 271 (CITRIC). Prohibir `company_id=False` en modelos que referencian cuentas de P&L de compañía.
3. Revisar las **automatizaciones de Studio/base_automation** que fijan distribución: no viajan con código y suelen estar escritas contra la 90 fija. Rehacerlas conscientes de compañía (`env.company` → elegir 90 vs 271). Esta es la vía más probable de reintroducir el bug tras un despliegue.

**Probar en PRE:** imputar un parte de CITRIC con un usuario que tenga AUNNA como activa → debe resolver la 271, no la 90, y NO reventar por `_check_company`.

**Aplicar en PRO:** cualquier `UPDATE` sobre `company_id` de cuentas/analíticas/distribución = backup + PRE primero + ventana.

---

## Fase 4 — Auditoría y hardening

**Objetivo:** trazabilidad nominal de quién toca los datos maestros y endurecimiento de sesiones. Ver [[07-auditoria-trazabilidad-hardening]].

### 4.1 `auditlog` (OCA server-tools — verificar rama 19.0) `[XML]`/`[UI]`

**Por qué:** Odoo no trae audit-trail forense generalista. Con `auditlog` queda registro nominal (quién, qué, antes/después) aunque el cambio venga de Studio o server action.

> ⚠️ **(verificar en PRE el port a 19.0 de `auditlog`.)** OCA server-tools no siempre tiene todos los módulos portados a la última versión el día 1. Confirmar rama 19.0 disponible antes de planificarlo como pieza fija; si no está, dejar como pendiente y apoyarse en `write_uid`/`write_date` + lock dates mientras tanto.

Pasos:
1. Instalar `auditlog` en PRE.
2. Crear reglas de auditoría **solo sobre datos maestros y modelos de seguridad** (no sobre modelos transaccionales, que inflan la BD):
   - Maestros: `product.template`, `product.product`, `uom.uom`, `uom.category`, `account.account`, `account.journal`, `account.analytic.account`, `account.analytic.plan`, `ir.sequence`, `res.currency`.
   - Seguridad/automatización: `res.groups`, `ir.model.access`, `ir.rule`, `res.users`, `base.automation`, `ir.actions.server`, `ir.ui.menu`, `ir.model.fields`.
3. Configurar un **cron de purga/retención** (p. ej. conservar 12-24 meses) para no crecer sin control.

**Probar en PRE:** renombrar una UdM con el custodio → confirmar que auditlog registra el cambio con usuario, campo, valor antes/después.

**Aplicar en PRO:** ⚠ instalar OCA en BD Enterprise puede afectar cobertura de soporte para incidencias donde el módulo esté implicado; probar exhaustivamente en PRE (partes, WIP, facturación) antes. Acotar bien los modelos para no degradar rendimiento.

### 4.2 `auth_session_timeout` (OCA server-auth — verificar rama 19.0) `[XML]`/`[UI]`

Logout por inactividad. Parámetro tipo `inactive_session_time_out_delay` (segundos; default habitual 7200) **(verificar nombre exacto del parámetro en la versión portada)**. **Excluir usuarios API/integraciones** por grupo para no romper conexiones automáticas. Probar en PRE con un usuario normal y uno de integración.

### 4.3 Diferir (verificar port a 19)

- `password_security` (OCA): **verificar port a 19** → mientras tanto, política manual + 2FA nativo.
- `base_user_role`: **verificar port a 19** antes de adoptar.
- `web_disable_export_group` / `base_export_manager`: **verificar port a 19**.

### 4.4 Nativo Enterprise (usar antes que OCA)

- 2FA (ya en Fase 1.2).
- Brute-force / rate-limiting de login: configuración de servidor (`odoo.conf`) y proxy, no requiere módulo.
- Lock dates contables (proteger periodos, complementa el blindaje de definiciones):

| Campo | Efecto | Nota |
|---|---|---|
| `fiscalyear_lock_date` | Bloquea asientos ≤ fecha para todos | |
| `tax_lock_date` | Bloquea periodos ya declarados de impuestos | |
| `hard_lock_date` | Bloqueo **irreversible** (v18+), ni superusuario desbloquea | Muy potente para cierres definitivos |
| `sale_lock_date` / `purchase_lock_date` | Bloqueo por tipo de diario (v18+) | |

> ⚠️ **(verificar en PRE dónde viven estos campos en v18/19.)** En v18 se refactorizaron las lock dates: en versiones recientes ya no son todas campos directos de `res.company` editables a mano, sino que se gestionan desde **Contabilidad → Contabilidad → Cierre / Fechas de bloqueo** (con un mecanismo/asistente dedicado y, para `hard_lock_date`, confirmación irreversible). Configúralas por la UI de Contabilidad, no por SQL. Confirmar el nombre técnico exacto de cada campo antes de referenciarlo en cualquier automatización.

---

## Runbook de EMERGENCIA — "alguien volvió a romper datos maestros"

> Objetivo: minutos, no horas. Prioridad = parar el daño y recuperar el trabajo del día sin restaurar todo si se puede evitar.

### E.1 Detección

Señales típicas:
- Los usuarios no pueden **crear/guardar partes de horas** (error de UdM o de producto de servicio).
- Errores tipo *"El proyecto, la tarea y las cuentas analíticas del parte deben pertenecer a la misma compañía"* (fuga cross-company, cuenta 90 en CITRIC).
- Facturación por partes que deja de generar líneas.

Confirmar qué se tocó y quién (con auditlog instalado, es inmediato):

```sql
-- [SQL-RO] Ultimos cambios auditados sobre datos maestros (requiere auditlog)
SELECT l.create_date, u.login, l.model_id, l.method, l.res_id
FROM auditlog_log l JOIN res_users u ON u.id = l.user_id
ORDER BY l.create_date DESC
LIMIT 50;
```

Sin auditlog, revisar `write_uid`/`write_date` del propio registro:

```sql
-- [SQL-RO] Quien y cuando modifico la UdM "Horas" por ultima vez
-- (verificar en PRE el xmlid nativo de la UdM Horas: puede ser uom.product_uom_hour)
SELECT id, name, write_uid, write_date FROM uom_uom
WHERE id = (SELECT res_id FROM ir_model_data
            WHERE model='uom.uom' AND module='uom' AND name='product_uom_hour');
```

### E.2 Contención (parar el daño, minutos)

1. **Identificar al autor** (E.1) y **retirarle de inmediato** el grupo que se lo permitió: quitar `base.group_system` / write en maestros. Si es cuenta comprometida, desactivar el usuario (`active=False` por UI).
2. Si el blindaje de Fase 1.3 estaba puesto y aun así ocurrió, revisar si el cambio lo hizo el **superusuario real (uid 1)** o alguien con la regla desactivada temporalmente — que ignoran/saltan las reglas. En ese caso, revisar la custodia de esa credencial y el registro de quién desactivó la regla (auditlog sobre `ir.rule`).
3. Comunicar a los usuarios que **no sigan trabajando** en el flujo afectado hasta el "OK" (para no acumular datos sobre un estado corrupto que luego habría que descartar en la restauración).

### E.3 Evaluar: reparación in situ vs restauración

| Situación | Acción recomendada |
|---|---|
| Solo se **renombró** la UdM/producto (write reversible, sin borrado) | **Reparación in situ**: el custodio revierte el nombre y la UdM/categoría al valor correcto. NO hace falta restaurar backup. Verificar el ratio de la categoría (p. ej. Working Time 8h=1día por defecto — **verificar en PRE**). |
| Se **borró** la UdM/categoría o el producto y las FK no lo impidieron | Restaurar **solo** los registros afectados desde backup si es viable, o restauración parcial (ver E.4). |
| Corrupción extendida (muchos registros/conversiones mal recalculadas, importes de partes alterados) | **Restauración total** del backup del punto bueno más reciente. Se pierde el trabajo posterior al backup → por eso E.2 corta el trabajo cuanto antes. |

> Preferir siempre la reparación in situ o parcial. La restauración total es el último recurso (pierde trabajo del día). El incidente original fue restauración total porque no había ni blindaje ni auditoría; con auditlog + reparación in situ se evita.

### E.4 Restauración (referencia a doc operativa)

- Scripts de restore y procedimiento de backups: ver **[[doc-operativa]]** / carpeta `new/doc` (servidores PRE/PRO, backups, incidencias) — fuente de verdad operativa.
- **Restauración parcial** (preferida): montar una copia del backup en un entorno aparte (o en PRE), extraer los registros buenos (UdM, categoría, producto) y reponerlos en PRO por el custodio. Verificar FKs.
- **Restauración total** (⚠ último recurso): en PRO, backup del estado ACTUAL (por si acaso, para forense) → restaurar dump del punto bueno → verificar flujos.
- Tras restaurar, **reponer inmediatamente el blindaje** (Fase 1.3) si no estaba, para que no se repita.

### E.5 Post-incidente

1. Documentar en `new/doc` (incidencias): qué pasó, quién, cómo se contuvo, qué se restauró.
2. Cerrar el vector: ¿faltaba una record rule? ¿un usuario tenía system de más? ¿una automatización de Studio reintrodujo la 90? ¿se dejó una regla global desactivada? Aplicar el fix en PRE → PRO.
3. Revisar auditlog para confirmar que no hubo otros cambios colaterales.

---

## Checklist final imprimible

### Fase 0 — Inventario
- [ ] Lista de todos los usuarios con sus grupos y `company_ids` (hoja completa).
- [ ] Identificados los que tienen `base.group_system` (query 0.2.a). Objetivo: dejar 1 titular + 1 suplente.
- [ ] Identificados grupos con write/unlink en `uom.uom`/`product.template` (query 0.2.c), incluyendo membresía **efectiva** (grupos implicados).
- [ ] Detectados usuarios con SoD incompatible y con exceso de `company_ids`.

### Fase 1 — Quick wins
- [ ] Quitado `base.group_system` a todos los no-custodios (probado en PRE, aplicado en PRO).
- [ ] 2FA forzado a custodios/admins (enrolados).
- [ ] Módulo de blindaje UdM/categoría instalado — probado que un `group_system` NO puede renombrar la UdM y que los partes SIGUEN funcionando.
- [ ] **Probado por rol manager:** ventas / almacén / contabilidad manager NO pueden renombrar ni archivar el producto *Horas* ni la UdM, y SÍ pueden seguir su operativa normal (sobre `product.template` **y** `product.product`).
- [ ] **Custodio** (`zambudio_permisos.group_master_data_custodian`) SÍ puede editar el producto *Horas* y la UdM (vía de edición legítima verificada).
- [ ] Definida y documentada la **vía de edición legítima** (patrón OR del custodio, o desactivación temporal de la regla global bajo doble control).
- [ ] Producto *Horas* blindado (**regla gemela en `product.template` y `product.product`**; ids/xmlids verificados y creados en cada entorno y por compañía — AUNNA, CITRIC, MONTOYA, ii).
- [ ] Confirmado que **ningún `domain_force` usa `ref()`** suelto (solo `user.env.ref(...).id` o listas de ids).
- [ ] (Opcional) Export restringido.

### Fase 2 — Roles
- [ ] Grupo `zambudio_permisos.group_master_data_custodian` creado (sin `category_id`; `privilege_id` opcional) y asignado (1-2 personas). Sin variantes obsoletas (`zambudio_master_data_lock`, etc.).
- [ ] Cada usuario reasignado a su rol del catálogo; grupos sobrantes retirados; sin redundancias (account_user ya trae invoice+readonly).
- [ ] `company_ids` reducido al mínimo por usuario; `company_id` por defecto dentro de `company_ids`.
- [ ] Portal Cliente sin `base.group_user`.

### Fase 3 — Record rules / multiempresa
- [ ] Reglas nativas de compañía auditadas (query 0.2.d) — todas presentes y correctas.
- [ ] Reglas custom globales **sin grupos** (no usar `<field name="global">`) con patrón canónico donde haga falta.
- [ ] `check_company=True` en campos relacionales custom (modelos con `company_id`).
- [ ] Distribución analítica sin `company_id` → 90 saneada; automatizaciones Studio conscientes de compañía.

### Fase 4 — Auditoría / hardening
- [ ] `auditlog` (rama 19.0 verificada) sobre maestros + modelos de seguridad; cron de purga.
- [ ] `auth_session_timeout` (rama 19.0 verificada) con excepción para API.
- [ ] Lock dates contables configuradas por la UI de Contabilidad donde aplique.
- [ ] 2FA nativo / brute-force verificados.

### GATE previo a PRO (doc 09)

- [ ] Recorrido el **[[09-anexo-verificacion-y-checklist]]**: TODOS los xmlids/ids `(verificar en PRE)` confirmados contra la BD real (grupos, modelos, `res.groups.privilege`, ids del producto *Horas* por compañía, nombres de tabla/campo v19). Sin este GATE cerrado, no se despliega en PRO.

### Gobernanza (transversal)
- [ ] Todo probado en PRE antes de PRO.
- [ ] **Backup DURO (C6)**: manual, verificado y **etiquetado** inmediatamente antes de cada cambio de maestros/permisos en PRO (`/root/backup_odoo19_prod.sh`, ver `new/doc/04-backups-y-restauracion.md`). RPO ≤ 4 h; prueba de restauración trimestral con RTO documentado.
- [ ] Doble control para cambios de maestros/permisos (ticket → PRE → validar → PRO), incluida la desactivación temporal de cualquier regla global.
- [ ] Runbook de emergencia impreso y accesible; scripts de restore localizados en `new/doc`.

---

## Anexo — Consultas SQL útiles (todas `[SQL-RO]`, seguras en PRO)

> Ninguna hace `UPDATE`/`DELETE`. Confirmar nombres de tablas puente en PRE (`res_groups_users_rel`, `res_company_users_rel`, `rule_group_rel`) y recordar que en v19 la membresía **efectiva** puede requerir la relación de `all_group_ids` **(verificar en PRE)**.

```sql
-- A) Usuarios con base.group_system (el grupo del incidente)
SELECT u.login, p.name FROM res_users u
JOIN res_partner p ON p.id=u.partner_id
JOIN res_groups_users_rel rel ON rel.uid=u.id
JOIN ir_model_data d ON d.res_id=rel.gid AND d.model='res.groups'
WHERE d.module='base' AND d.name='group_system' AND u.active ORDER BY u.login;

-- B) Quien puede BORRAR/ESCRIBIR en uom.uom (via ACL de grupo)
SELECT g_d.module||'.'||g_d.name AS grupo, a.perm_write, a.perm_unlink
FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id
LEFT JOIN res_groups g ON g.id=a.group_id
LEFT JOIN ir_model_data g_d ON g_d.res_id=g.id AND g_d.model='res.groups'
WHERE m.model='uom.uom' AND (a.perm_write OR a.perm_unlink);

-- C) Ultima modificacion de la UdM "Horas" (quien y cuando)
SELECT id, name, write_uid, write_date FROM uom_uom
WHERE id=(SELECT res_id FROM ir_model_data
          WHERE model='uom.uom' AND module='uom' AND name='product_uom_hour');  -- (verificar xmlid en PRE)

-- D) Record rules por compañia (auditar aislamiento multiempresa)
SELECT r.id, m.model, r.name, r.domain_force, r."global" FROM ir_rule r
JOIN ir_model m ON m.id=r.model_id
WHERE r.domain_force ILIKE '%company_id%' ORDER BY m.model;

-- E) Distribucion analitica sin compañia apuntando a la 90 (fuga CITRIC)
--    (mejor filtrar por el id real de la cuenta 90 como clave del JSON)
SELECT id, company_id, account_prefix, analytic_distribution
FROM account_analytic_distribution_model
WHERE company_id IS NULL
  AND analytic_distribution::text LIKE '%90%';   -- cribado tosco; refinar con la clave-id real

-- F) Usuarios con mas de una compañia en company_ids (riesgo cross-company)
SELECT u.login, count(rel.cid) n FROM res_users u
JOIN res_company_users_rel rel ON rel.user_id=u.id
WHERE u.active GROUP BY u.login HAVING count(rel.cid)>1 ORDER BY n DESC;

-- G) Reglas globales (usar el campo calculado 'global', mas robusto que reconstruir joins)
SELECT r.id, m.model, r.name FROM ir_rule r
JOIN ir_model m ON m.id=r.model_id
WHERE r."global" = true
ORDER BY m.model;

-- H) Ultimos cambios auditados sobre maestros (requiere auditlog instalado)
SELECT l.create_date, u.login, l.model_id, l.method, l.res_id
FROM auditlog_log l JOIN res_users u ON u.id=l.user_id
ORDER BY l.create_date DESC LIMIT 50;
```

---

### Recordatorios finales (no negociables)

1. **PRE siempre antes que PRO.** Sin excepción.
2. **Backup DURO (C6) antes de cada cambio en PRO**, incluso los reversibles: manual, **verificado** y **etiquetado** justo antes del cambio (`/root/backup_odoo19_prod.sh`, `new/doc/04-backups-y-restauracion.md`). RPO ≤ 4 h; prueba de restauración trimestral con RTO documentado.
3. **GATE doc 09 antes de PRO.** Ningún XML se pega en PRO sin cerrar [[09-anexo-verificacion-y-checklist]] (todos los xmlids/ids `(verificar en PRE)` confirmados). Un xmlid inventado o un `ref()` inexistente rompe la instalación.
4. **NUNCA `ref()` dentro de `domain_force`** (NameError en runtime): usar `user.env.ref('modulo.xmlid').id` o una **lista** de ids resueltos por BD. El producto *Horas* tiene un registro **por compañía** → lista, no `!=` con un id.
5. **El producto *Horas* se blinda en pareja:** regla sobre `product.template` **y** su gemela sobre `product.product` (la variante es la que usa el parte). `perm_write=True` cubre renombrar, archivar (`active=False`), `type` y `sale_ok`.
6. **`base.group_system` es custodia, no un rol de trabajo.** Ese fue el origen del incidente.
7. **La barrera real de los maestros es la record rule GLOBAL** (va en AND, no se sortea); el ACL es refuerzo (aditivo, no resta). Una regla es global **por no tener grupos** (`groups eval []`), no por el campo calculado `global` (escribir `<field name="global" eval="True"/>` no hace nada).
8. **El superusuario real (uid 1) ignora todas las reglas** y desactivar una regla global también las salta → custodiar esa credencial y auditar `ir.rule` es crítico. La regla global "congela" el maestro también para `group_system`: prevé la vía de edición legítima (patrón OR del custodio o desactivación temporal bajo doble control).
9. **Muchas automatizaciones son de Studio y NO viajan con código** → auditarlas aparte en cada entorno y rehacerlas conscientes de compañía.
10. **v19 cambió el modelo de seguridad:** `privilege_id`/`res.groups.privilege` (no `category_id`), `group_ids`/`all_group_ids` (no `groups_id`), `user_ids` (no `users`). xmlids/campos/tablas marcados **(verificar en PRE)** deben confirmarse contra la BD antes de referenciarlos en PRO.