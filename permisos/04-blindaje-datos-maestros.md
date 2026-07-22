# Blindaje de datos maestros (anti-catástrofe)

> **Documento clave.** Aquí se explica por qué el incidente rompió los partes de horas y se define, modelo maestro por modelo maestro, quién puede crear/editar/borrar y **cómo** restringirlo técnicamente en Odoo 19. Todo lo que toca producción se prueba **primero en PRE** (`erp-pre.zambudio.es`, BD `grupo_zambudio_prod_pruebas`).
>
> Relacionado: [[02-catalogo-de-roles]], [[05-record-rules-multiempresa]], [[07-auditoria-trazabilidad-hardening]], [[05-record-rules-multiempresa]].

---

## 1. Qué pasó y por qué (diagnóstico del vector)

Un usuario con perfil "Administrador" (grupo `base.group_system`, etiquetado en v19 **"Role / Administrator"**) hizo dos cosas:

1. **Renombró el producto de servicio "Horas"** (el que usan los partes vía `sale_timesheet`) y lo convirtió en un producto de venta.
2. **Alteró/borró la unidad de medida "Horas"** (`uom.uom`).

Resultado: se rompieron **todos** los partes de horas (`hr_timesheet` depende de la UdM "Horas" y del producto de servicio). Hubo que restaurar el backup del día anterior y se perdió el trabajo del día.

### Por qué las defensas "naturales" NO lo impidieron

| Defensa que se suele asumir | Por qué no frenó el incidente |
|---|---|
| **FK / `ondelete` RESTRICT** | Solo protege el **borrado** (`unlink`), y solo si hay referencias vivas. El incidente fue un **`write`** (renombrar `name`, cambiar tipo de producto, tocar la UdM). Ningún `write` lo para una FK. |
| **`noupdate="1"`** en `uom.product_uom_hour` | Solo evita que un **upgrade de módulo** repise el registro. NO impide que un usuario con permiso lo edite/borre por la UI. El registro ya era `noupdate` y aun así se rompió. |
| **Ocultar el menú de UdM** | Solo es UI. Un `base.group_system` llega a la UdM por Studio, importación, otro menú técnico o RPC. |
| **Añadir una ACL con `perm_write=0`** | Las ACL son **aditivas (OR)**: añadir una línea con 0 no resta nada. Solo reduce **bajar/sobrescribir** las ACL nativas existentes por su xmlid. |

### La causa raíz (en una frase)

> Demasiada gente con `write`/`unlink` sobre `uom.uom`, `uom.category` y `product.template`, concedido por tener `base.group_system` o grupos "Administrator" de app.

**Hecho de gobernanza que sostiene toda la solución:** las `ir.rule` (record rules) e `ir.model.access` **NUNCA** aplican al superusuario real (`base.user_root`, uid 1, `env.su`) ni al código que corre en `sudo()` (crons, automatizaciones internas). Pero un usuario "Administrador" con `base.group_system` **NO es** el superusuario: las record rules **sí** le aplican. Por tanto, **una record rule restrictiva habría frenado a ese admin**, dejando la edición solo al custodio, **sin romper** los crons ni las automatizaciones internas (que corren en `sudo`). Ese es el eje del blindaje.

---

## 2. Estrategia en capas (resumen)

El blindaje real es la **suma** de estas capas. Ninguna basta por sí sola.

| Capa | Qué hace | Mecanismo | ¿Frena al `group_system`? |
|---|---|---|---|
| **1. Gobernanza de grupos** | No dar `base.group_system` ni "Administrator de X" a perfiles funcionales | Asignación de grupos / roles | Sí (les quita el poder de origen) |
| **2. Ocultar `uom.group_uom`** | Casi nadie ve el menú de UdM | `res.groups` / menús | Solo UI (defensa débil sola) |
| **3. `ir.rule` restrictiva (record-scoped)** | `write`/`unlink` imposibles salvo custodio, sobre los maestros críticos | `ir.rule` con `perm_write`/`perm_unlink` + dominio | **Sí** (globales van en AND, no se esquivan) |
| **4. `ir.model.access` de refuerzo** | Baja perms nativos donde se pueda | ACL CSV/XML | Parcial |
| **5. Lock dates contables** | Bloquea asientos por fecha (incl. hard lock) | `res.company` | Sí (hard lock, incluso a asesores) |
| **6. `groups=` en campos** | Campos sensibles no editables ni por RPC | Atributo en `fields.X` | Sí |
| **7. Auditoría (`auditlog`)** | Deja rastro nominal de todo cambio en maestros | OCA `auditlog` | Sí (registra, no impide) |

> **Regla de oro:** la capa que **realmente** blinda es la **3 (`ir.rule`)** + la **1 (no dar el grupo)**. Las demás refuerzan.

---

## 3. Capa 1 — No repartir poder de administrador

### Los dos "admin" que hay que separar

| Concepto | xmlid | Da acceso a | Quién debe tenerlo |
|---|---|---|---|
| Admin técnico (Ajustes) | `base.group_system` ("Role / Administrator") | Ajustes, instalar/activar apps, menús técnicos, **editar UdM/monedas/secuencias**, Studio/base_automation | **Solo custodio de sistema (1 titular + 1 suplente)** |
| Admin de accesos | `base.group_erp_manager` ("Access Rights") | Crear/editar usuarios y asignar grupos | Opcional, gestor de usuarios delegado |
| Técnico oculto | `base.group_no_one` ("Technical Features") | Menús/campos "developer" (solo efectivos en modo desarrollador) | Solo custodio |
| Multiempresa | `base.group_multi_company` | Selector de compañía | Solo quien opera AUNNA + CITRIC |

> ⚠️ **Aviso de dependencias entre grupos:** `base.group_erp_manager` está **implicado por** `base.group_system`. Y a la inversa, en v19 `base.group_system` implica también `base.group_erp_manager`. Quien tenga Ajustes puede gestionar accesos y grupos: es otra razón para no repartir `group_system`. Verifica el árbol real de `implied_ids` **en PRE** antes de asumir herencias.

**Normas capa 1:**

1. `base.group_system` **es custodia, no un rol de trabajo.** Administración, Contabilidad, Almacén, Ventas, etc. **NO lo necesitan** para su día a día.
2. Ningún perfil funcional lleva el grupo **"Administrator"** de su app si no lo exige su función (p. ej. Contabilidad usa `account.group_account_user`, no siempre `account.group_account_manager`).
3. `product.group_product_manager` ("Create") está **implicado por `base.group_system`**: quien tiene Ajustes puede crear/renombrar productos aunque no se lo hayas dado explícitamente. Otra razón para no repartir `group_system`.
4. Revisar periódicamente (mensual) la lista de usuarios con `base.group_system` / `base.group_erp_manager`. (Ver [[07-auditoria-trazabilidad-hardening]].)

Query de revisión (solo lectura, segura en PRO). La tabla puente y sus columnas (`res_groups_users_rel`, `uid`, `gid`) están **verificadas en v19**:

```sql
SELECT u.login, u.id
FROM res_users u
JOIN res_groups_users_rel r ON r.uid = u.id
JOIN ir_model_data d ON d.res_id = r.gid AND d.model = 'res.groups'
WHERE d.module = 'base' AND d.name IN ('group_system','group_erp_manager')
ORDER BY u.login;
```

> **Nota v19:** esta query mira solo grupos **asignados directamente** (`group_ids`). Un usuario puede tener `group_system` **heredado** vía `implied_ids` de otro grupo. Para ver el efectivo, usa en la UI el campo `all_group_ids` o comprueba con `user.has_group('base.group_system')`.

---

## 4. Capa 2 — Retirar `uom.group_uom` a casi todos

- **`uom.group_uom`** ("Manage Multiple Units of Measure") es el toggle que enseña el menú y los campos de gestión de UdM.
- Con el toggle **OFF** para un usuario, no ve el menú de UdM ni los campos de UdM en la UI. **Pero esto NO protege el dato**: la UdM "Horas" sigue existiendo y `hr_timesheet` la sigue necesitando; solo oculta la interfaz.
- **Norma:** que `uom.group_uom` lo tenga **solo el custodio de datos maestros**. El resto opera con la UdM por defecto sin ver el menú.
- Menús/acciones gated por `uom.group_uom` (nombres exactos **verificar en PRE**): acción de categorías `uom.product_uom_categ_form_action`, acción de unidades `uom.product_uom_form_action`.

> Esta capa es **cosmética de seguridad**. Reduce la superficie de error accidental, pero un `group_system` sigue llegando por otras vías. El blindaje duro es la capa 3.

---

## 5. Capa 3 — Record rules `ir.rule` (el blindaje duro)

### 5.1 El grupo custodio (a crear)

Se crea un grupo propio, el **Custodio de Datos Maestros**, cuyo **xmlid canónico es `zambudio_permisos.group_master_data_custodian`** (módulo de refuerzo de referencia `zambudio_permisos`; **el entregable es doc, no se monta módulo** — el grupo puede crearse a futuro por módulo o directamente por UI). Es el único, junto al superusuario, que puede `write`/`unlink` sobre los maestros.

> **Nomenclatura canónica (C1):** el único nombre válido es **`zambudio_permisos.group_master_data_custodian`**. Cualquier otra variante de versiones previas (`zambudio_custom`, `zambudio_master_data`, `zambudio_master_data_custody`, `zambudio_master_data_lock`, `zambudio_security_hardening`, `group_master_data_custody`, `group_master_data_custodian` **sin prefijo**…) es **histórica**: usar siempre el canónico. Este grupo es **funcional**: **NO** implica `base.group_system` y **NO** es el uid 1; las reglas de blindaje lo **re-permiten explícitamente**. Si el grupo se crea por UI en vez de por módulo, su xmlid real se resolverá en PRE **(verificar en PRE)**.

> ⚠️ **Corrección de xmlid:** el privilege `base.res_groups_privilege_administration` **NO existe** en Odoo 19 (los `res.groups.privilege` de `base` son `res_groups_privilege_export`, `res_groups_privilege_contact`, etc.; `base.group_system` ni siquiera tiene `privilege_id`). En v19 el campo `privilege_id` es **opcional**: si lo omites, el grupo aparece bajo "Otros/Extra Rights" y funciona igual. Define el `privilege_id` solo si creas tú un `res.groups.privilege` propio, o asígnalo desde la UI y confirma el xmlid **en PRE**.

Definición recomendada (sin `privilege_id` inventado):

```xml
<!-- Opcional: tu propio privilege para agrupar el rol en la UI -->
<record id="res_groups_privilege_master_data" model="res.groups.privilege">
    <field name="name">Custodia de Datos Maestros</field>
    <field name="category_id" ref="base.module_category_administration"/> <!-- verificar en PRE -->
</record>

<record id="group_master_data_custodian" model="res.groups">
    <field name="name">Custodio de Datos Maestros</field>
    <!-- privilege_id OPCIONAL; si no creas el de arriba, omite esta línea -->
    <field name="privilege_id" ref="res_groups_privilege_master_data"/>
    <field name="implied_ids" eval="[Command.link(ref('base.group_user'))]"/>
</record>
```

`Command.link` está disponible en el contexto de eval de datos en v19; si prefieres la forma clásica, usa `eval="[(4, ref('base.group_user'))]"`. El custodio **debe** implicar `base.group_user` (ser usuario interno).

### 5.2 Tabla de decisión de patrón (C4) — referencia oficial

Recuerda cómo combina Odoo 19 (verificado en fuente):

- Reglas **globales** (sin `groups`) → se combinan en **AND**: todas deben cumplirse; imposible esquivarlas metiéndose en otro grupo.
- Reglas **de grupo** (con `groups`) → **OR** entre las de los grupos del usuario.
- Resultado final = `AND(globales) AND (OR(reglas de grupo))`.
- Una regla solo actúa sobre una operación si su `perm_X = True`. Deja `perm_read=False` para **no** romper la lectura (los maestros aparecen en desplegables de toda la operativa).
- **Solo el uid 1 (superusuario) y `sudo()` ignoran** las record rules. `base.group_system` **NO** las ignora → por eso el blindaje frena al admin del incidente.

> ⚠️ **Convenio de reglas globales (C2):** una `ir.rule` es **GLOBAL si y solo si NO tiene grupos**. El campo `global` es **calculado** (`global = not groups_id`) y de **solo lectura**: escribir `<field name="global" eval="True"/>` **NO HACE NADA** (el eval se ignora) y la regla acabaría como regla de grupo esquivable. **PROHIBIDO** en todo el corpus `<field name="global" eval="True"/>`; usar **siempre** `<field name="groups" eval="[]"/>` (lista de grupos vacía = global).

> ⚠️ **Convenio de `perm_*` (C9):** toda regla de blindaje declara los **cuatro** `perm_*` explícitamente. `perm_read=False` salvo que se quiera restringir lectura (no es el caso en maestros).

**Los tres patrones canónicos y a qué modelo aplica cada uno** (esta tabla es la **fuente de verdad**; el resto del documento la cita):

| Patrón | Regla | Dominio (`domain_force`) | Quién puede write/create/unlink | Modelos donde se aplica |
|---|---|---|---|---|
| **P1** · GLOBAL + `has_group` (solo custodio) | GLOBAL (`groups` eval `[]`) | `[(1,'=',1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [(0,'=',1)]` | Solo el **custodio**; el resto solo lee | `uom.uom`, `uom.category`, `res.currency`, `ir.sequence` |
| **P2** · GLOBAL + `has_group` ampliado (contabilidad + custodio) | 2 reglas GLOBALES (`groups` eval `[]`) | write/create: `[(1,'=',1)] if (user.has_group('account.group_account_manager') or user.has_group('zambudio_permisos.group_master_data_custodian')) else [(0,'=',1)]`; **unlink**: 2ª regla global solo-custodio | **Contabilidad manager + custodio** para write/create; **unlink solo custodio** | `account.account`, `account.journal`, `account.tax`, `account.fiscal.position`, `account.analytic.account`, `account.analytic.plan` |
| **P3** · GLOBAL *scoped* por `id` (joya puntual, resto editable) | GLOBAL (`groups` eval `[]`) + **regla gemela** | `[(1,'=',1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id','not in', IDS)]` | Solo el **custodio** toca el/los registro(s) protegido(s); el resto del modelo lo siguen editando sus managers | Producto de servicio **"Horas"** (`product.template` **+** `product.product`) |

> **Motivo por patrón:** P1 → editar UdM/moneda/secuencia es raro y solo el custodio debe hacerlo; el resto solo lee (partes y desplegables siguen funcionando). P2 → Contabilidad mantiene el plan contable legítimamente en su día a día, pero el **borrado** de cuentas/diarios queda solo en el custodio. P3 → el producto "Horas" no lo puede tocar **NADIE** (ni ventas/stock/contabilidad manager) salvo el custodio, mientras los productos normales siguen editables por sus managers.

> 🔧 **Cómo resuelve la contradicción del custodio (gap #3):** en las tres variantes el custodio **SÍ** puede editar (rama `[(1,'=',1)]` del ternario), y **nadie más** (rama `[(0,'=',1)]` o `not in`). **NO** se usa el global-falso puro `[(0,'=',1)]` sin ternario para los maestros que el custodio debe mantener — ese dominio dejaría la edición **solo al uid 1** y volvería a bloquear al propio custodio. El global-falso puro se reserva, si acaso, para una "joya" que solo el superusuario deba tocar.

#### P1 — GLOBAL + `has_group` (solo custodio)

Aplica a `uom.uom`, `uom.category`, `res.currency`, `ir.sequence`.

```xml
<record id="uom_lock_custodian_rule" model="ir.rule">
    <field name="name">UdM: write/create/unlink solo custodio</field>
    <field name="model_id" ref="uom.model_uom_uom"/>
    <!-- ternario has_group: custodio SÍ, resto NO. NO usar [(0,'=',1)] puro -->
    <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [(0, '=', 1)]</field>
    <field name="groups" eval="[]"/>                    <!-- SIN grupos = GLOBAL (AND) -->
    <field name="perm_read"   eval="False"/>            <!-- no restringe lectura -->
    <field name="perm_create" eval="True"/>
    <field name="perm_write"  eval="True"/>
    <field name="perm_unlink" eval="True"/>
</record>
```

Lectura: la regla actúa sobre `create/write/unlink`; su dominio solo se cumple para el custodio → **solo el custodio** (y el uid 1) puede escribir/crear/borrar UdM. Todos siguen **leyéndolas** con normalidad (los partes funcionan).

> ⚠️ **Sobre `perm_create` en `ir.sequence`:** algunos procesos crean secuencias automáticamente (alta de diario, de producto que genera su secuencia…). Esas creaciones internas corren en `sudo`/cron y **ignoran** la regla, así que `perm_create=True` no las rompe. Si algún flujo por UI de un manager necesitara crear secuencias, pásalo a un ternario ampliado (estilo P2) o deja `perm_create=False` para ese modelo. Documenta la decisión por modelo.

#### P2 — GLOBAL + `has_group` ampliado (contabilidad + custodio)

Aplica a `account.account`, `account.journal`, `account.tax`, `account.fiscal.position`, `account.analytic.account`, `account.analytic.plan`. **Dos reglas globales**: una para write/create (contabilidad manager **o** custodio) y otra para unlink (solo custodio).

```xml
<!-- Regla 1: write/create permitido a contabilidad manager O custodio -->
<record id="account_write_p2" model="ir.rule">
    <field name="name">Cuentas: write/create contabilidad+custodio</field>
    <field name="model_id" ref="account.model_account_account"/>
    <field name="domain_force">[(1, '=', 1)] if (user.has_group('account.group_account_manager') or user.has_group('zambudio_permisos.group_master_data_custodian')) else [(0, '=', 1)]</field>
    <field name="groups" eval="[]"/>                    <!-- GLOBAL (AND) -->
    <field name="perm_read"   eval="False"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_write"  eval="True"/>
    <field name="perm_unlink" eval="False"/>            <!-- unlink NO aquí -->
</record>
<!-- Regla 2: unlink SOLO custodio (2ª regla global) -->
<record id="account_unlink_p2" model="ir.rule">
    <field name="name">Cuentas: unlink solo custodio</field>
    <field name="model_id" ref="account.model_account_account"/>
    <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [(0, '=', 1)]</field>
    <field name="groups" eval="[]"/>                    <!-- GLOBAL (AND) -->
    <field name="perm_read"   eval="False"/>
    <field name="perm_create" eval="False"/>
    <field name="perm_write"  eval="False"/>
    <field name="perm_unlink" eval="True"/>
</record>
```

> ⚠️ **Por qué dos reglas globales y no re-permisos de grupo:** ambas van en **AND** y no se pueden esquivar entrando en otro grupo. Un esquema de "bloqueo a `base.group_user` + re-permiso de grupo" es **más frágil** (los re-permisos de grupo se OR-ean y pueden fugarse si otro grupo trae una regla permisiva sobre el mismo modelo). Con P2 el borrado queda **garantizado** solo en el custodio.

#### P3 — GLOBAL *scoped* por `id` (el patrón correcto para el producto "Horas")

Aplica al producto de servicio **"Horas"**, con **regla gemela obligatoria** sobre `product.product` (la variante es la que usa el parte) además de `product.template`.

```xml
<!-- Protege SOLO el/los product.template críticos; el resto de productos se editan normal -->
<record id="product_tmpl_lock_hours" model="ir.rule">
    <field name="name">Producto Horas: write/create/unlink solo custodio</field>
    <field name="model_id" ref="product.model_product_template"/>
    <!-- IDS = ids resueltos en PRE/PRO con la query de §10.2 (DISTINTOS por entorno) -->
    <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id', 'not in', [ID_TMPL_HORAS_PRE_O_PRO])]</field>
    <field name="groups" eval="[]"/>
    <field name="perm_read"   eval="False"/>
    <field name="perm_create" eval="False"/>
    <field name="perm_write"  eval="True"/>
    <field name="perm_unlink" eval="True"/>
</record>
<!-- REGLA GEMELA OBLIGATORIA sobre product.product (la variante del parte) -->
<record id="product_product_lock_hours" model="ir.rule">
    <field name="name">Variante Horas: write/create/unlink solo custodio</field>
    <field name="model_id" ref="product.model_product_product"/>
    <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id', 'not in', [ID_VARIANT_HORAS_PRE_O_PRO])]</field>
    <field name="groups" eval="[]"/>
    <field name="perm_read"   eval="False"/>
    <field name="perm_create" eval="False"/>
    <field name="perm_write"  eval="True"/>
    <field name="perm_unlink" eval="True"/>
</record>
```

> ⚠️ **Resolver los `id` por entorno (C3):** hay un producto de servicio "Horas" **por compañía**, con `id` **DISTINTOS** en PRE y en PRO. Resuelve los ids en **cada BD** (query §10.2) y usa una **LISTA** `[('id','not in',[id1,id2,...])]` (no `!=` con un solo id). Alternativas: `user.env.ref('modulo.xmlid').id` si tienen external id estable, o un `post_init_hook` que los localice (`service_policy='delivered_timesheet'` / `default_code`) y cree su external id.

> ⚠️ **BUG CORREGIDO — nunca `ref()` suelto en `domain_force` (C3):** el contexto de evaluación de `ir.rule.domain_force` incluye `user`, `time`, `company_id`, `company_ids` (y `env` vía `user.env`). **NO incluye `ref`.** Usar `ref('modulo.xmlid')` en `domain_force` provoca **`NameError` en runtime**. La forma correcta de referenciar un registro por xmlid dentro de `domain_force` es **`user.env.ref('modulo.xmlid').id`**. Es **falso** que "`ref()` funciona en `domain_force`".

> ⚠️ **BUG CORREGIDO — no bloquear el modelo entero de productos:** aplicar un dominio falso `[(0,'=',1)]` sobre **todo** `product.template`/`product.product` **rompería TODA la edición de productos** para todos los perfiles (Administración no podría crear ni tocar ningún producto: precios, stock, etc.). Por eso P3 **acota por `id`** con `not in`. Recuerda que en `ir.rule` el dominio es una **lista blanca** (lo que el usuario **SÍ** puede tocar): para bloquear un registro se **excluye** con `not in`, nunca con `in`.

> 🔧 **Nota (gap #14) — archivar/`active`/`type`/`sale_ok` quedan cubiertos:** como `perm_write=True` cubre **cualquier** `write`, P3 protege también **archivar** el producto (`active=False`), cambiar `type`, `sale_ok`, la UdM, etc. No hace falta enumerar campos: cualquier escritura sobre el registro protegido queda vetada a los no-custodios.

#### Excepción razonada: `product.category`

`product.category`: **unlink solo custodio**, pero **write/create permitido a inventario manager** (`stock.group_stock_manager`) — no conviene bloquear la operativa normal de categorías. Se documenta como **excepción**: usa el esquema **P2** pero con `stock.group_stock_manager` en lugar de `account.group_account_manager` para write/create, y `unlink` solo custodio (2ª regla global).

### 5.3 Notas técnicas de `ir.rule` (Odoo 19, verificado)

- El campo de grupos en `ir.rule` se llama `groups` (Many2many a `res.groups`); **no** cambió de nombre en v19.
- Contexto disponible en `domain_force`: `user` (registro del usuario), `company_id` (= `env.company.id`), `company_ids` (= `env.companies.ids`), y `time` (y `env` vía `user.env`). Es una expresión Python que devuelve un dominio; puedes usar `user.company_id.id` o `user.has_group('xmlid')` como valores/condición. **`ref` NO está en ese contexto:** `ref('modulo.xmlid')` suelto en `domain_force` lanza `NameError` en runtime → para resolver un registro por xmlid usa **`user.env.ref('modulo.xmlid').id`**.
- Para **bloquear `write`/`unlink`** pon `perm_write=True` / `perm_unlink=True` con dominio falso (o `not in`). Mantén `perm_read=False` para **no** romper la lectura.
- **Superusuario y `sudo()` ignoran todas las rules** → la custodia del root/`__system__` es crítica (ver [[07-auditoria-trazabilidad-hardening]]). Ventaja: crons, automatizaciones internas y actualizaciones de tasa de moneda (que corren en `sudo`) **siguen funcionando** pese al blindaje.

---

## 6. Ficha por modelo maestro crítico

Leyenda de "Quién": **C** = Custodio de datos maestros (o superusuario), **Adm** = Administración/Contabilidad (edición controlada), **R** = resto de perfiles (solo lectura).

| Modelo | Crear | Editar | Borrar | Patrón (C4) | Riesgo concreto |
|---|---|---|---|---|---|
| `uom.uom` | C | C | C | **P1** | Renombrar/borrar la UdM "Horas" → rompe TODOS los partes. **Vector del incidente.** |
| `uom.category` | C | C | C | **P1** | Cambiar ratio/referencia de "Working Time" → corrompe **silenciosamente** las conversiones hora↔día. |
| `product.template` / `product.product` | Adm (resto) | **C** (registro "Horas") | C | **P3** (regla gemela) | Convertir "Horas" en producto de venta, cambiar `type`/UdM/`active`/`sale_ok` → rompe facturación de partes. |
| `product.category` | Inv. mgr | Inv. mgr | C | **P2\*** (inv. manager; unlink custodio) | Cambiar cuentas contables de la categoría (property, company_dependent) → contabilización errónea. |
| `account.account` | Adm/C | Adm/C | C | **P2** | Renombrar/reclasificar cuentas; borrado bloqueado por FK si tiene apuntes, pero rename no. |
| `account.journal` | Adm/C | Adm/C | C | **P2** | Cambiar cuentas/config de un diario → numeración y asientos corruptos. |
| `account.analytic.account` | Adm/C | Adm/C | C | **P2** | Mover compañía de la 90/271, borrar → rompe P&L. Origen de la fuga CITRIC. |
| `account.analytic.plan` | Adm/C | Adm/C | C | **P2** | Alterar el plan "Horas internas/externas" (`x_plan3_id`) → distribución analítica rota. |
| `res.currency` | C | C | C | **P1** | Cambiar redondeo/nombre → valoración descuadrada. Global, no aislable por compañía. **Las tasas viven en `res.currency.rate` (modelo aparte).** |
| `ir.sequence` | Adm/C | C | C | **P1** | Tocar prefijo/next_number → saltos y duplicados de numeración legal. |
| `account.tax` | Adm/C | Adm/C | C | **P2** | Cambiar % o cuentas de un impuesto en uso → declaraciones mal. |
| `account.fiscal.position` | Adm/C | Adm/C | C | **P2** | Alterar mapeos de impuestos/cuentas → facturación intracomunitaria/exenta errónea. |
| `account.analytic.distribution.model` | Adm/C | Adm/C | C | **P2** | Modelo con `company_id=False` apuntando a la 90 → inyecta 90 en CITRIC → `_check_company` revienta el parte. |
| `res.company` (config partes) | — | **C** | — | **P1** sobre `res.company` (solo `write`) | Cambiar `timesheet_encode_uom_id` / `project_time_mode_id` → recodifica el tiempo y descuadra TODOS los partes. Ver §10.1. |
| Lock dates (`res.company`) | C | C | — | Capa 5 | Desbloquear un periodo cerrado y reeditar asientos. |

**Norma general:** por defecto **C**. Solo donde la tabla marca **Adm** se permite edición controlada de Administración/Contabilidad (patrón **P2**), y aun así el **borrado** queda en C.

> ⚠️ **`res.currency` vs `res.currency.rate`:** bloquear `write` sobre `res.currency` protege nombre/símbolo/redondeo pero **no** toca las tasas, que están en `res.currency.rate`. Es lo deseable: la actualización automática de tasas (cron OCA/nativo, en `sudo`) sigue funcionando. Si además quieres blindar la entrada manual de tasas, aplica una regla aparte sobre `res.currency.rate`.

> ⚠️ **`res.company` (config de partes):** los campos `timesheet_encode_uom_id` y `project_time_mode_id` deciden en qué UdM se codifica el tiempo; cambiarlos recodifica **todos** los partes. Blíndalos con **P1** sobre `res.company` (solo `perm_write=True`, `perm_read=False`), que restringe la escritura de la ficha de compañía al custodio. Si Administración necesita seguir editando otros campos de la compañía (dirección, logo…), la alternativa más quirúrgica es dejar `res.company` sin regla global y proteger **solo esos dos campos** con `groups='zambudio_permisos.group_master_data_custodian'` en la definición del field (§9). Decide y documenta cuál de las dos aplicas en PRE.

> 🔧 **Nivel de protección de `mrp.bom`, tarifas (`product.pricelist`) y atributos (`product.attribute` / `product.attribute.value`) — decisión explícita (gap #12):** **ACEPTADO SIN blindaje `ir.rule` específico**, decisión justificada: (a) no intervinieron en el incidente; (b) su edición es parte de la operativa legítima de Producción/Ventas y bloquearla molestaría sin reducir el riesgo real; (c) un cambio erróneo en ellos es **reversible** y no corrompe **silenciosamente** los partes como sí lo hace la UdM/categoría "Working Time" o el producto "Horas". Quedan cubiertos por la **capa 1** (no repartir `group_system`) y por **`auditlog`** (§11) para trazabilidad. Si en el futuro una tarifa o una BOM concreta se vuelve "joya" crítica, aplíquesele **P3** (scoped por `id`) sobre ese registro puntual.

### 6.1 xmlids de modelo de referencia (para el `model_id`)

| Modelo | `model_id` (ref) |
|---|---|
| `uom.uom` | `uom.model_uom_uom` |
| `uom.category` | `uom.model_uom_category` (verificar en PRE) |
| `product.template` | `product.model_product_template` |
| `product.product` | `product.model_product_product` |
| `product.category` | `product.model_product_category` |
| `account.account` | `account.model_account_account` |
| `account.journal` | `account.model_account_journal` |
| `account.analytic.account` | `analytic.model_account_analytic_account` (verificar en PRE) |
| `account.analytic.plan` | `analytic.model_account_analytic_plan` (verificar en PRE) |
| `res.currency` | `base.model_res_currency` |
| `ir.sequence` | `base.model_ir_sequence` |
| `account.tax` | `account.model_account_tax` |
| `account.fiscal.position` | `account.model_account_fiscal_position` |
| `account.analytic.distribution.model` | `account.model_account_analytic_distribution_model` (verificar en PRE) |

> Para los modelos marcados **P2** en la tabla, la 1ª regla global re-permite write/create a `account.group_account_manager` (o `stock.group_stock_manager` en el caso `product.category`) **y** al custodio, y la 2ª regla global restringe `unlink` **solo** al custodio (todo con el xmlid canónico `zambudio_permisos.group_master_data_custodian`). Para `uom.uom`, `uom.category`, `res.currency` e `ir.sequence` usa **P1** (ternario solo-custodio). Para el producto "Horas" usa **P3** (scoped por `id`, con **regla gemela** en `product.product`).

---

## 7. Capa 4 — Refuerzo con `ir.model.access`

Las ACL son **aditivas (OR)**: no se puede "restar" con una línea nueva a 0. Solo se reduce **sobrescribiendo por su xmlid** las ACL nativas que conceden write/unlink. Es frágil entre upgrades y hay que localizar **todas** las que conceden el permiso. Por eso es **refuerzo**, no mecanismo principal (el que sí "resta" es la `ir.rule` de la capa 3).

Cabecera del CSV (nota: en v19 la columna de grupo sigue siendo `group_id:id`):

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

Ejemplo: dar al resto de perfiles **solo lectura** de UdM, y CRUD completo solo al custodio (además de la regla de capa 3):

```csv
access_uom_uom_readonly_all,uom.uom readonly,uom.model_uom_uom,base.group_user,1,0,0,0
access_uom_uom_custodian,uom.uom custodio,uom.model_uom_uom,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_uom_categ_readonly_all,uom.category readonly,uom.model_uom_category,base.group_user,1,0,0,0
access_uom_categ_custodian,uom.category custodio,uom.model_uom_category,zambudio_permisos.group_master_data_custodian,1,1,1,1
```

> **Ojo:** dar `1,0,0,0` a `base.group_user` **no anula** una ACL nativa que otro grupo (p. ej. `stock.group_stock_manager`) tenga con write=1. Hay que localizar y bajar **esas** ACL nativas por su xmlid, o confiar en la regla de la capa 3 (que sí resta). Localiza las ACL que conceden write:

```sql
SELECT a.name, g.name AS grupo, a.perm_write, a.perm_unlink
FROM ir_model_access a
JOIN ir_model m ON m.id = a.model_id
LEFT JOIN res_groups g ON g.id = a.group_id
WHERE m.model = 'uom.uom' AND (a.perm_write OR a.perm_unlink);
```

---

## 8. Capa 5 — Lock dates contables

Complementan el blindaje de definiciones: protegen los **asientos por fecha**, no los nombres del plan. Campos en `res.company` (**nombres exactos verificar en PRE**, v18/19 refactorizó esto y añadió el modelo de excepciones):

| Campo (verificar en PRE) | Qué bloquea |
|---|---|
| `fiscalyear_lock_date` | Nadie (salvo excepción) crea/edita asientos con fecha ≤ esa. |
| `tax_lock_date` | Bloqueo de declaración de impuestos. |
| `hard_lock_date` | **Bloqueo duro/irreversible** (v18+): ni asesores ni el superusuario desbloquean. Para cierres definitivos. |
| `sale_lock_date` / `purchase_lock_date` | Bloqueo por tipo de diario (v18+). |
| Excepciones puntuales | Modelo `account.lock_exception` (v18+); solo para admin o "todos". |

**Normas:**
- Fijar `fiscalyear_lock_date` tras cada cierre mensual/anual.
- Usar `hard_lock_date` para ejercicios definitivamente cerrados (**irreversible**: probar el flujo en PRE antes, nunca "practicar" en PRO).
- Las lock dates NO protegen renombrado del plan de cuentas ni config de diarios → eso lo hace la capa 3.

---

## 9. Capa 6 — `groups=` en campos sensibles

- `groups="modulo.xmlid"` **en la definición del `fields.X(...)`** es **seguridad real**: el ORM elimina el campo de lectura/escritura para quien no esté en el grupo (ni siquiera por RPC).
- `<field name="x" groups="..."/>` **en la vista** es **solo visibilidad de UI**, NO seguridad (accesible por RPC si la ACL/rule lo permite). *"Visibility != security."*

Para blindar de verdad, `groups=` en el field (o ACL/record rule), nunca solo ocultar en vista. Ejemplo conceptual: proteger el `name` del producto de servicio o la UdM del producto contra no-custodios requiere heredar el modelo y añadir `groups='zambudio_permisos.group_master_data_custodian'` al campo — se documenta como referencia; **no se entrega módulo montado**. En la práctica, para el producto "Horas" el **patrón P3** de la capa 3 ya lo cubre sin tocar código (y también es la vía para blindar los campos `timesheet_encode_uom_id` / `project_time_mode_id` de `res.company` sin bloquear el resto de la ficha de compañía).

---

## 10. Proteger la UdM "Horas" y el producto de partes (apartado específico)

Este es el corazón del incidente. Dos objetos hay que blindar:

### 10.1 La UdM "Horas" — `uom.product_uom_hour`

- xmlid: **`uom.product_uom_hour`** (modelo `uom.uom`, "Hours"/"Horas"), definido en el módulo `uom` con `noupdate="1"`.
- Hermana: `uom.product_uom_day` ("Days"/"Días").
- Categoría: **`uom.uom_categ_wtime`** ("Working Time"/"Tiempo de trabajo"), agrupa Horas y Días con ratio (por defecto 8 h = 1 día). Referencia de la categoría y `uom_type`/factor de cada unidad: **verificar en PRE**.

Dónde se usa (qué se rompe si se toca):
- `res.company.timesheet_encode_uom_id` (Ajustes > Partes de horas, "Codificar tiempo en") → por defecto `uom.product_uom_hour`.
- `res.company.project_time_mode_id` (modo de tiempo de proyecto).
- Cada línea de parte (`account.analytic.line.product_uom_id`) hereda esa UdM.
- `hr_timesheet` convierte `unit_amount` entre la UdM de codificación y la referencia de "Working Time". **Toda conversión hora↔día pasa por esa categoría.**

Efectos:
- **Borrar** `uom.product_uom_hour`: normalmente lo impide la FK. Pero si no hubiera referencias vivas, la codificación deja de resolver → los partes no se guardan.
- **Renombrar** la UdM o **alterar categoría/ratio/factor**: la FK **NO** protege (es `write`). Cambiar ratio/referencia **corrompe silenciosamente** todas las conversiones. **Este es el vector exacto.**

**Blindaje:** regla **P1** (ternario solo-custodio) sobre `uom.uom` **y** sobre `uom.category` (§5.2) — o **P3** scoped a `uom_categ_wtime` si prefieres seguir permitiendo crear otras UdM — + retirar `uom.group_uom` (§4) + ACL readonly (§7) + `auditlog` sobre `uom.uom` y `uom.category` (§11). Recuerda blindar también `res.company.timesheet_encode_uom_id` / `project_time_mode_id` (P1 sobre `res.company` o `groups=` en el field, §6/§9).

### 10.2 El producto de servicio "Horas"

- No hay xmlid fijo del núcleo: es un `product.template`/`product.product` con `type='service'` y `service_policy='delivered_timesheet'` (facturar según partes) — lo arrastra `sale_timesheet`.
- Al venderlo genera proyecto/tarea; los partes se enlazan por `sale_line_id` / `service_type='timesheet'`.
- **Qué se rompe** si un admin le quita el tipo servicio, le cambia la UdM o lo despublica: las nuevas ventas dejan de crear líneas facturables por tiempo, se rompe el enlace parte↔pedido y la facturación de proyectos deja de cuadrar.

**Identificar el/los registros exactos en PRE antes de blindar** (necesitas el `id` para el patrón **P3** scoped, distinto en PRE y PRO):

```sql
SELECT pt.id AS tmpl_id, pt.name, pt.type, pt.service_policy, pt.uom_id
FROM product_template pt
WHERE pt.service_policy = 'delivered_timesheet'
   OR pt.name::text ILIKE '%hora%';
-- Y la(s) variante(s) product.product asociada(s):
SELECT pp.id AS variant_id, pp.product_tmpl_id
FROM product_product pp
WHERE pp.product_tmpl_id IN ( /* ids del select anterior */ );
```

**Blindaje:** regla **P3 (scoped por `id`)** sobre `product.template` (ternario custodio / `not in [ID_TMPL_HORAS]`) **y regla gemela obligatoria** sobre `product.product` (ternario custodio / `not in [ID_VARIANT_HORAS]`), como en §5.2 — esto deja el resto de productos plenamente editables por Administración y solo blinda el de partes. Como `perm_write=True` cubre cualquier `write`, quedan protegidos también `type`, `uom_id`, `name`, `active` (archivar) y `sale_ok` (gap #14). Resuelve los `id` en **cada entorno** (PRE/PRO son distintos). Refuerzo: `groups=` en campos clave como referencia + `auditlog` sobre ambos modelos.

---

## 11. Capa 7 — Auditoría (dejar rastro)

Odoo **no** trae audit-trail forense generalista. Instalar **`auditlog`** (OCA/server-tools; **confirmar rama 19.0 disponible en el OCA installer antes de instalar**) y crear reglas de auditoría **solo sobre datos maestros y de seguridad**:

- Maestros: `uom.uom`, `uom.category`, `product.template`, `product.product`, `product.category`, `account.account`, `account.journal`, `account.analytic.account`, `account.analytic.plan`, `account.analytic.distribution.model`, `ir.sequence`, `res.currency`, `res.currency.rate`, `account.tax`, `account.fiscal.position`.
- Seguridad/automatización (para saber quién cambió la propia seguridad): `res.groups`, `res.groups.privilege`, `ir.model.access`, `ir.rule`, `ir.actions.server`, `base.automation`, `ir.ui.menu`, `ir.model.fields`.

Caveats: no auditar `create/write` en modelos transaccionales (`account.move.line`, `stock.move`, `mail.message`) → infla la BD. Prever cron de purga. Detalle en [[07-auditoria-trazabilidad-hardening]].

> ⚠️ **Riesgo residual — control procedimental, no técnico (C7):** el blindaje `ir.rule` frena a `base.group_system`, pero **nada en la BD frena al uid 1 ni al código en `sudo()`**. Que el **propio custodio**, una **automatización Studio** o código en `sudo` repita el incidente es un control **procedimental**, no técnico. Refuerzo **obligatorio** antes de dar por cerrado el blindaje:
> 1. `auditlog` sobre maestros **y** sobre seguridad (`res.groups`, `ir.rule`, `ir.model.access`, `base.automation`, `ir.actions.server`) — ya listado arriba.
> 2. Alerta `base.automation` ante `write` en `uom.uom` / producto "Horas".
> 3. **Revisión OBLIGATORIA de TODAS las automatizaciones Studio existentes** que escriban maestros **antes** de cerrar el blindaje: Studio corre en `sudo` y **se salta las reglas**. Una automatización que reescriba la UdM o el producto "Horas" reproduciría el incidente aunque las `ir.rule` estén puestas.

---

## 12. Aislamiento multiempresa (AUNNA / CITRIC) frente al blindaje

El blindaje de maestros y el aislamiento multiempresa **no se pisan**, pero conviene coordinarlos:

- Las reglas de bloqueo de capa 3 usan dominios falsos (`[(0,'=',1)]`, `not in`), **independientes de compañía**: se combinan en **AND** con las reglas multi-compañía nativas, así que un usuario de AUNNA sigue sin ver datos de CITRIC **y** además no puede tocar los maestros. No hay conflicto.
- **Punto crítico ya conocido:** `account.analytic.distribution.model` con `company_id=False` apuntando a la cuenta 90 inyecta la analítica de AUNNA en CITRIC y `_check_company` revienta el parte. Manténlo bajo **P2** (solo Adm/C editan; unlink solo custodio) **y** exige `company_id` seteado por compañía. Ver [[05-record-rules-multiempresa]].
- `res.currency` es **global** (no aislable por compañía): su blindaje protege a las dos empresas a la vez.
- Cuentas/diarios/analítica tienen `company_id`: al re-permitir en **P2** a `account.group_account_manager`, ese manager solo verá/editará los de **su(s)** compañía(s) por las reglas nativas de compañía. Correcto.
- **Las 4 compañías (C8):** el aislamiento y el blindaje aplican a **AUNNA IT (id 1)**, **CITRIC NETWORKS (id 2)**, **MONTOYA** e **ii** (ids de MONTOYA e ii: **resolver en PRE**). Cada una tiene su cuenta de P&L de horas equivalente a la **90 (AUNNA)** / **271 (CITRIC)** — resolver la de MONTOYA e ii en PRE. **Check de go-live:** **NINGUNA** de las 4 compañías debe tener un `account.analytic.distribution.model` con `company_id` **NULL** apuntando a una cuenta de P&L de **otra** compañía. Detalle multiempresa en [[05-record-rules-multiempresa]] y [[05-record-rules-multiempresa]].

---

## 13. Por qué "borrar por xmlid o FK" ya está impedido pero NO basta

- Registros con **xmlid** (`ir.model.data`) y `noupdate="1"`: protegidos solo frente a **upgrades de módulo**, no frente a edición/borrado por UI.
- **FK / `ondelete` RESTRICT**: `account.account` con apuntes, `account.journal` con asientos, `uom.uom` referenciada → `unlink` lanza error. **Red parcial**: solo cubre **borrado** y solo con referencias vivas. **No** impide **renombrar** (`write`), ni cambiar ratio/categoría/tipo. El incidente fue exactamente eso.

**Conclusión:** FK + xmlid no son blindaje anti-vandalismo. El blindaje efectivo es **capa 3 (`ir.rule`)** + **capa 1 (no dar el grupo)**, con las demás como refuerzo.

---

## 14. Checklist de despliegue (probar SIEMPRE en PRE primero)

1. [ ] Crear grupo `zambudio_permisos.group_master_data_custodian` (sin `privilege_id` inventado; **NO** implica `base.group_system`) y asignar 1-2 personas.
2. [ ] Retirar `base.group_system` a todo perfil funcional; dejar 1 titular + 1 suplente. Verificar con `all_group_ids` / `has_group` que nadie lo hereda de rebote.
3. [ ] Retirar `uom.group_uom` a todos salvo custodio.
4. [ ] Reglas **P1** (ternario `has_group` solo-custodio, global) para `uom.uom`, `uom.category`, `res.currency`, `ir.sequence`.
5. [ ] Regla **P1** (o `groups=` en field) para `res.company.timesheet_encode_uom_id` / `project_time_mode_id`.
6. [ ] Reglas **P3 (scoped por `id`)** para el producto "Horas": `product.template` **+ regla gemela** en `product.product`, confirmando los `id` con la query de §10.2 **en cada entorno**. **No** bloquear el modelo entero.
7. [ ] Reglas **P2** (2 reglas globales: write/create a `account.group_account_manager` + custodio; **unlink solo custodio**) para `account.account`, `account.journal`, `account.tax`, `account.fiscal.position`, `account.analytic.account`, `account.analytic.plan`, `account.analytic.distribution.model`. `product.category`: **P2\*** con `stock.group_stock_manager`.
8. [ ] `mrp.bom` / tarifas / atributos: **aceptados sin blindaje `ir.rule`** (decisión justificada §6, gap #12) — solo `auditlog`.
9. [ ] ACL readonly de refuerzo + bajar ACL nativas de write que sobren.
10. [ ] Fijar lock dates tras cierres; `hard_lock_date` (irreversible) solo para ejercicios definitivamente cerrados.
11. [ ] Instalar `auditlog` (rama 19.0 confirmada) y crear reglas sobre maestros + seguridad. **Revisar TODAS las automatizaciones Studio** que escriban maestros (corren en `sudo`, se saltan las reglas) antes de cerrar el blindaje (C7).
12. [ ] Multiempresa: confirmar ids y cuenta P&L de horas de **MONTOYA** e **ii** (además de 90/271); ningún `analytic.distribution.model` con `company_id` NULL cruzado (C8).
13. [ ] **Probar los flujos reales en PRE**: crear parte de horas, facturar proyecto WIP, **crear y editar un producto normal** (debe seguir funcionando para Adm), verificar que un usuario funcional NO puede renombrar la UdM ni el producto "Horas", que el **custodio SÍ puede editarlos**, y que crons/automatizaciones (`sudo`) siguen operando.
14. [ ] Confirmar los xmlids marcados "verificar en PRE" antes de referenciarlos.
15. [ ] **BACKUP manual verificado y ETIQUETADO inmediatamente ANTES** de tocar maestros o permisos en PRO (C6): ref. `new/doc/04-backups-y-restauracion.md`, script `/root/backup_odoo19_prod.sh`. RPO objetivo para `grupo_zambudio_prod` ≤ **pocas horas** (el incidente costó ~24 h de trabajo); prueba de restauración **trimestral** con RTO documentado.
16. [ ] Solo entonces, replicar en PRO con doble control (ticket + validación).

---

### xmlids y campos a verificar en PRE (no inventados, pendientes de confirmar)

- `uom.model_uom_category`, `analytic.model_account_analytic_account`, `analytic.model_account_analytic_plan`, `account.model_account_analytic_distribution_model`.
- **`privilege_id` del grupo custodio: NO existe `base.res_groups_privilege_administration`.** Déjalo sin `privilege_id`, o crea tu propio `res.groups.privilege` (con `category_id` a confirmar, p. ej. `base.module_category_administration`).
- Referencia/`uom_type`/factor de `uom.uom_categ_wtime`; nombres de menú de UdM.
- Nombres exactos de campos de lock dates en v19 (`fiscalyear_lock_date`, `hard_lock_date`, `sale_lock_date`, `purchase_lock_date`, `tax_lock_date`) y el modelo `account.lock_exception`.
- xmlid del grupo analítico (`analytic.group_analytic_accounting`) y de las ACL nativas de `uom.uom`.
- `id` reales del `product.template`/`product.product` "Horas" (query §10.2) para el patrón **P3** (scoped por `id`, distintos en PRE y PRO).

> **Confirmado en v19 (no requiere verificación):** en `res.users` los grupos están en `group_ids` (directos) y `all_group_ids` (con implicados); **ya no** existe `groups_id`. En dominios usa `user.has_group('xmlid')`. Las `res.groups` se categorizan vía `privilege_id` → `res.groups.privilege` → `category_id` (sustituye al `category_id` directo de v17/18). El campo de grupos en `ir.rule` sigue siendo `groups`. La tabla puente usuario-grupo es `res_groups_users_rel(uid, gid)`.