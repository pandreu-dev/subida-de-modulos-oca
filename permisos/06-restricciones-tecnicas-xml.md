# Restricciones técnicas concretas (XML/CSV)

> **Qué es este documento.** Un catálogo de restricciones técnicas **concretas y copiables** para blindar datos maestros y menús sensibles en la BD Odoo 19 Enterprise del Grupo Zambudio. Es una **referencia de implementación**, NO se entrega como módulo montado. Los snippets están pensados para pegarse tal cual (con ajuste de xmlids) en un módulo de refuerzo o aplicarse por UI.
>
> **Contexto del incidente que motiva todo esto:** un usuario con perfil *Administrador* (`base.group_system`) renombró el producto de servicio *Horas* y alteró la UdM *Horas* (`uom.uom`), rompiendo todos los partes de horas. El vector fue un **`write` (renombrado / cambio de tipo), no un `unlink`**: ni las FK ni `noupdate` lo pararon. Todo lo que sigue ataca ese vector.
>
> **AVISO PRODUCCIÓN:** todo lo de aquí toca seguridad efectiva. Se prueba **SIEMPRE primero en PRE** (`erp-pre.zambudio.es`, BD `grupo_zambudio_prod_pruebas`) ejecutando los flujos reales (crear parte de horas, facturar proyecto WIP, alta de producto, **postear una factura y comprobar su numeración**) antes de subir a PRO. Los xmlids del núcleo que no he podido confirmar contra fuente van marcados **(verificar en PRE)**.

Documentos relacionados: [[01-modelo-seguridad-odoo19]] · [[04-blindaje-datos-maestros]] · [[02-catalogo-de-roles]] · [[05-record-rules-multiempresa]] · [[07-auditoria-trazabilidad-hardening]] · [[00-principios-y-gobernanza]] *(ajustar nombres reales de la carpeta `new/permisos`)*

---

## 0. Cómo leer este catálogo: las 3 capas y qué resuelve cada una

| Capa | Modelo | Qué controla | Se combina | ¿Frena el incidente? |
|---|---|---|---|---|
| Acceso a modelo (ACL) | `ir.model.access` (CSV) | CRUD por **modelo** y grupo | **Aditivo / OR** (suman permisos) | Solo si bajas los perms nativos; **no resta** añadiendo líneas nuevas |
| Regla de registro | `ir.rule` (XML) | Qué **filas** dentro del modelo | **Global → AND** · **Grupo → OR** | **SÍ**: regla global restrictiva es imposible de sortear (salvo superusuario) |
| Campo | `groups=` en el `fields.X(...)` | Visibilidad/escritura de un **campo** por RPC | El ORM lo elimina de lectura/escritura | Sí a nivel de campo (p. ej. `name` del producto) |

**Reglas de oro:**
1. **El superusuario real (`base.user_root`, uid 1) IGNORA todas las ACL y record rules.** Un usuario "Administrador" con `base.group_system` **NO es** el superusuario → las record rules **SÍ le aplican**. Por eso la solución central es una **`ir.rule`** (global §1.A o block/allow §1.B): habría frenado al admin del incidente.
2. **Las ACL son permisivas y se UNEN.** Añadir una línea con `perm_write=0` **no quita** nada; solo reduces bajando los perms de la ACL **nativa** (sobrescribiéndola por su xmlid). Frágil entre upgrades → úsalo como refuerzo, no como mecanismo principal.
3. **`noupdate="1"` NO es blindaje.** Solo evita que un upgrade de módulo reponga el registro; no impide que un usuario con permiso lo edite/borre. `uom.product_uom_hour` ya es `noupdate="1"` y aun así se rompió.
4. **Ocultar en la vista ≠ seguridad.** `<field ... groups="..."/>` en una vista es solo UI; el campo sigue accesible por RPC. Seguridad real = `groups=` en el **field Python** o ACL/rule.

> ⚠️ **Combinación de reglas (clave para no romper nada):** las reglas **de grupo** que aplican a un usuario se combinan en **OR** (gana la más permisiva); las reglas **globales** (sin grupos) se combinan en **AND** entre sí y con el resultado de las de grupo. Consecuencia: **no mezcles una regla global restrictiva (§1.A) con el patrón block/allow (§1.B) sobre el MISMO modelo**, porque la global haría AND y bloquearía también al custodio. Para cada maestro, elige **una** de las dos estrategias.

---

## 1. `ir.rule`: impedir write/unlink de datos maestros salvo al custodio

Este es el mecanismo **principal**. Dos patrones según quién deba poder editar. Elige uno por modelo (ver aviso de §0).

> 📌 **Nombre canónico (fuente de verdad).** El grupo custodio se llama SIEMPRE `zambudio_permisos.group_master_data_custodian` (rol "Custodio de Datos Maestros"). Es un grupo **funcional**: **NO** implica `base.group_system` ni es el uid 1; las reglas de blindaje lo **re-permiten** explícitamente. El módulo de refuerzo de referencia es `zambudio_permisos`. Cualquier otro nombre de versiones previas (`zambudio_custom`, `zambudio_master_data`, `zambudio_master_data_custody`, `zambudio_master_data_lock`, `zambudio_security_hardening`, `group_master_data_custody`, …) es **histórico**: usar solo el canónico. Si el grupo se crea por UI en vez de por módulo, su xmlid real se resuelve en PRE **(verificar en PRE)**.
>
> 📌 **Convenio de reglas globales (`ir.rule`).** Una regla es GLOBAL **si y solo si NO tiene grupos**. El campo `global` es **calculado** (`global = not groups_id`) y de **solo lectura**: escribir `<field name="global" eval="True"/>` **no hace nada** (el `eval` se ignora) y la regla acabaría como regla de grupo esquivable. Por eso en todo este documento el "global" se declara con **`<field name="groups" eval="[]"/>`** (lista de grupos vacía). Globales → **AND** (restringen de verdad); de grupo → **OR** (añaden). Solo el uid 1 ignora las record rules; `base.group_system` **NO** las ignora.

### 1.A Patrón GLOBAL "solo el superusuario edita" (el más robusto, sin delegación humana)

Una regla **global** (sin `groups`) se combina en **AND** con todo → **nadie normal puede saltarla**, ni siquiera `base.group_system`. Solo el superusuario real (uid 1) la ignora. Es el blindaje recomendado para los maestros que **nadie** debe tocar en el día a día (categoría UdM y su ratio, moneda). Para editarlos, se entra como superusuario en un procedimiento controlado.

> ⚠️ Si quieres que exista un **custodio humano** que sí pueda arreglar estos maestros sin ser superusuario, **NO uses 1.A**, usa **1.B**. La global también bloquea al custodio.

**Qué hace:** bloquea `write`, `create` y `unlink` sobre `uom.uom` para todo usuario interno; la lectura queda intacta (`perm_read=False` → la regla no aplica a lectura). 

**Dónde se pone:** fichero `security/ir_rule_master_data.xml` del módulo de refuerzo, declarado en `data` del `__manifest__.py`.

```xml
<odoo>
    <data noupdate="1">
        <!-- UdM: nadie salvo superusuario puede crear/modificar/borrar -->
        <record id="uom_lock_all_rule" model="ir.rule">
            <field name="name">UdM: bloqueo total salvo superusuario</field>
            <field name="model_id" ref="uom.model_uom_uom"/>
            <field name="domain_force">[(0, '=', 1)]</field>   <!-- dominio SIEMPRE falso -->
            <field name="groups" eval="[]"/>                    <!-- SIN grupos = GLOBAL -->
            <field name="perm_read"   eval="False"/>            <!-- no restringe lectura -->
            <field name="perm_create" eval="True"/>
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="True"/>
        </record>
    </data>
</odoo>
```

> Detalle clave: una `ir.rule` solo aplica a la operación cuyo `perm_X=True`. Aquí `perm_read=False` → lectura libre; `perm_write/create/unlink=True` con dominio falso → esas tres operaciones se bloquean para todos los no-superusuario. Los partes de horas solo **leen** la UdM, así que no se rompen.

**Maestros técnicos sin compañía** candidatos a global (no se aíslan por empresa, solo por permisos):

| Modelo | `model_id` ref | Notas |
|---|---|---|
| Unidades de medida | `uom.model_uom_uom` | La del incidente (mejor por §1.B si hay custodio) |
| Categorías de UdM | `uom.model_uom_category` (verificar en PRE) | Cambiar el ratio corrompe conversiones hora↔día |
| Monedas | `base.model_res_currency` | Global, sin compañía |
| Secuencias | `base.model_ir_sequence` | **Ver aviso ⚠️ abajo antes de bloquear write** |

> ⚠️ **`res.currency`:** bloquear `write/create/unlink` en `res.currency` es seguro para la operativa diaria porque el cron de tipos de cambio escribe en **`res.currency.rate`** (otro modelo), no en `res.currency`. Verifica en PRE que el cron de divisas sigue funcionando si lo activáis.
>
> ⚠️ **`ir.sequence` (cuidado):** el incremento de secuencias `no_gap` se hace por SQL directo (no pasa por el ORM), así que una `ir.rule` **no** suele frenar la numeración de documentos; pero para no arriesgar, **prueba en PRE postear una factura, un albarán y un pedido tras aplicar la regla**. Si algo falla, deja `perm_write=False` y bloquea solo `perm_create`/`perm_unlink` en `ir.sequence`, o limítate a ocultar el menú (§3) + auditoría (§5). El riesgo real de `ir.sequence` es más el borrado/recreación que la escritura.

### 1.B Patrón "grupo custodio SÍ edita, el resto no" (delegación sin superusuario) — RECOMENDADO para UdM y maestros que alguien deba mantener

Si Pablo quiere que un **Custodio de Datos Maestros** (rol humano, no superusuario) pueda editar, se usan **dos reglas de grupo** que, para el custodio, se combinan en **OR** y "gana" la permisiva. Funciona porque el custodio también pertenece a `base.group_user` (por `implied_ids`), así que las dos reglas le aplican y el OR lo desbloquea.

**Qué hace:** bloquea a todo internal user (`base.group_user`); re-permite al grupo custodio.

**Dónde se pone:** requiere haber creado antes el grupo `zambudio_permisos.group_master_data_custodian` (ver §10). En `security/ir_rule_master_data.xml`.

```xml
<odoo>
    <data noupdate="1">
        <!-- (1) Bloquea a TODO usuario interno -->
        <record id="uom_block_internal_users" model="ir.rule">
            <field name="name">UdM: bloquea escritura a usuarios internos</field>
            <field name="model_id" ref="uom.model_uom_uom"/>
            <field name="domain_force">[(0, '=', 1)]</field>
            <field name="groups" eval="[Command.link(ref('base.group_user'))]"/>
            <field name="perm_read"   eval="False"/>
            <field name="perm_create" eval="True"/>
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="True"/>
        </record>
        <!-- (2) Re-permite al custodio (OR gana) -->
        <record id="uom_allow_custodian" model="ir.rule">
            <field name="name">UdM: permite escritura al Custodio de Datos Maestros</field>
            <field name="model_id" ref="uom.model_uom_uom"/>
            <field name="domain_force">[(1, '=', 1)]</field>
            <field name="groups" eval="[Command.link(ref('zambudio_permisos.group_master_data_custodian'))]"/>
            <field name="perm_read"   eval="False"/>
            <field name="perm_create" eval="True"/>
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="True"/>
        </record>
    </data>
</odoo>
```

> `Command.link(ref('...'))` equivale a `(4, id)` y está disponible en el `eval` de los XML de datos en Odoo 17+. Alternativa clásica igual de válida: `eval="[(4, ref('base.group_user'))]"`.

> ⚠️ **Fragilidad del patrón OR (avisar):** si el usuario está además en **otro grupo** que tenga una regla permisiva sobre el mismo modelo, esa OR le abre la puerta. Con maestros técnicos (UdM, moneda) casi ningún grupo funcional tiene rule propia, así que es seguro; con `product.template` hay más grupos en juego → **verificar en PRE** que ningún otro grupo del usuario re-permite (query de §8 sobre `ir_rule`).

### 1.C Ejemplos por cada maestro contable/analítico

Estos maestros SÍ tienen compañía; el blindaje de escritura (patrón 1.B, block+allow) se combina con el aislamiento multiempresa de [[05-record-rules-multiempresa]]. Tabla de refs:

| Maestro | `model_id` ref | Quién lo edita hoy (nativo) | Riesgo si se toca |
|---|---|---|---|
| Producto (plantilla) | `product.model_product_template` | sales/purchase/stock/mrp managers **y** users → sobreexpuesto | Renombrar/cambiar tipo del producto *Horas* = incidente |
| Producto (variante) | `product.model_product_product` | idem | idem |
| Categoría de producto | `product.model_product_category` | managers de apps | Reasignar cuentas contables por categoría |
| Cuenta contable | `account.model_account_account` | `account.group_account_manager` | Renombrar/recodificar plan |
| Diario | `account.model_account_journal` | `account.group_account_manager` | Cambiar secuencia/cuentas por defecto |
| Impuesto | `account.model_account_tax` | `account.group_account_manager` | Cambiar %/cuentas |
| Posición fiscal | `account.model_account_fiscal_position` | `account.group_account_manager` | — |
| Cuenta analítica | `analytic.model_account_analytic_account` (verificar en PRE) | `analytic.group_analytic_accounting` (verificar en PRE) | La 90/271 del incidente CITRIC |
| Plan analítico | `analytic.model_account_analytic_plan` (verificar en PRE) | idem | El plan "Horas internas/externas" (`x_plan3_id`) |
| Modelo de distribución analítica | `account.model_account_analytic_distribution_model` (verificar en PRE) | contabilidad | Fuga cross-company de la 90 |
| Secuencia | `base.model_ir_sequence` | `base.group_system` | Numeración (ver aviso §1.A) |
| Moneda | `base.model_res_currency` | `base.group_system` | — |

> ⚠️ **Analítica en Odoo 19:** la analítica vive en el módulo **`analytic`**, no en `account`. Por eso el xmlid del modelo suele ser `analytic.model_account_analytic_account` / `analytic.model_account_analytic_plan` (y el grupo `analytic.group_analytic_accounting`). Confírmalo con la query de §8; el `account_analytic_distribution_model` puede colgar de `account` o de `analytic` según versión → **verificar en PRE**.

**Ejemplo completo para `product.template`** (patrón block + allow, incluye la variante `product.product` para que no se sortee editando la variante):

```xml
<odoo>
    <data noupdate="1">
        <record id="product_tmpl_block_users" model="ir.rule">
            <field name="name">Producto: bloquea escritura a no-custodios</field>
            <field name="model_id" ref="product.model_product_template"/>
            <field name="domain_force">[(0, '=', 1)]</field>
            <field name="groups" eval="[Command.link(ref('base.group_user'))]"/>
            <field name="perm_read"   eval="False"/>
            <field name="perm_create" eval="True"/>
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="True"/>
        </record>
        <record id="product_tmpl_allow_custodian" model="ir.rule">
            <field name="name">Producto: permite escritura al Custodio</field>
            <field name="model_id" ref="product.model_product_template"/>
            <field name="domain_force">[(1, '=', 1)]</field>
            <field name="groups" eval="[Command.link(ref('zambudio_permisos.group_master_data_custodian'))]"/>
            <field name="perm_read"   eval="False"/>
            <field name="perm_create" eval="True"/>
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="True"/>
        </record>
        <!-- Repetir el par para product.product con model_id ref="product.model_product_product" -->
    </data>
</odoo>
```

> ⚠️ **Aviso producción (fuerte):** bloquear `product.template` con `perm_write`/`perm_create` afecta a MUCHOS flujos (un comercial que ajusta un precio, un almacenero que cambia una ruta, alta de producto on-the-fly desde una línea de pedido). **La recomendación NO es bloquear todo el modelo `product.template`**, sino:
> - proteger **solo el producto *Horas*** con la record rule por registro de **§1.D**, y/o
> - proteger **campos concretos** (`name`, `uom_id`, `type`) — pero **NO vía `groups=` en el field** para campos centrales (ver §6, rompe informes); mejor por §1.D.
>
> El bloqueo total de modelo (block/allow completo) resérvalo para maestros de baja rotación (categoría UdM, moneda), no para `product.template`.

> ⚠️ **Multiempresa:** el par block/allow de arriba **no** aísla por compañía; para que AUNNA no vea/edite datos de CITRIC y viceversa, esto se **combina** con las record rules multicompañía nativas (`res.company` en el dominio) descritas en [[05-record-rules-multiempresa]]. Presta atención especial a `account.analytic.distribution.model`: debe filtrar por `company_id` para que la distribución que fija la cuenta 90 de AUNNA no se aplique a CITRIC (271).

### 1.D Alternativa por dominio: bloquear solo el registro concreto (no todo el modelo) — VÍA PREFERIDA para *Horas*

Si no quieres congelar toda la tabla `product.template` sino **solo el producto *Horas*** (y **solo la UdM *Horas***), usa un dominio que aísle esos registros. Menos invasivo, protege exactamente lo que rompió el incidente.

Usa **una regla GLOBAL por modelo** (patrón **P3** de la tabla de decisión §1.E) cuyo dominio dependa de `user.has_group(...)`: para el custodio el dominio es verdadero (edita cualquier registro), para el resto **excluye por `id`** el/los registro(s) protegido(s). Una sola regla global hace **AND** y **no es esquivable** por el OR de otro grupo → no necesitas el par block/allow, y evitas la fragilidad del patrón OR (§1.B).

**IDs del producto *Horas* — lo delicado.** Hay **un producto de servicio *Horas* por compañía** (AUNNA, CITRIC, MONTOYA, ii) con **ids DISTINTOS en PRE y en PRO**: por eso el dominio usa una **lista** `('id','not in',[...])`, nunca un `!=` con un solo id. Dos formas **correctas** de resolverlos dentro de `domain_force`:

> ⚠️ **`ref()` NO existe en el contexto de `domain_force`.** El dominio se evalúa **en runtime** con un contexto que expone `user`, `time`, `company_id`, `company_ids` (y `env` vía `user.env`), **pero NO `ref`**. Escribir `ref('modulo.xmlid')` en un `domain_force` provoca **`NameError` en runtime**. (El `ref(...)` de los `<field name="groups" eval="...">` de §1.A–§1.C sí es válido: ese `eval` corre en el **contexto de carga del XML**, no en runtime.)
>
> - **Lista de ids** resueltos en cada BD (PRE y PRO por separado): `[('id','not in',[id1,id2,...])]`.
> - **`user.env.ref('modulo.xmlid').id`** si das a cada producto un **external id estable** (p. ej. con un `post_init_hook` que los localice por `service_policy='delivered_timesheet'` / `default_code` y cree su `ir.model.data`).

**Regla GEMELA obligatoria:** el mismo blindaje sobre `product.product` **y** sobre `product.template` (el parte usa la **variante**; sin la gemela se sortea editando la plantilla, o al revés).

```xml
<odoo>
    <data noupdate="1">
        <!-- product.product: la variante "Horas" solo la toca el custodio -->
        <record id="product_horas_lock_variant" model="ir.rule">
            <field name="name">Producto Horas (variante): solo el Custodio modifica</field>
            <field name="model_id" ref="product.model_product_product"/>
            <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id', 'not in', [PRODUCT_HORAS_VARIANT_IDS])]</field>
            <field name="groups" eval="[]"/>                    <!-- SIN grupos = GLOBAL (AND) -->
            <field name="perm_read"   eval="False"/>            <!-- lectura libre: Horas sale en desplegables -->
            <field name="perm_create" eval="False"/>            <!-- no restringe crear productos nuevos -->
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="True"/>
        </record>
        <!-- product.template: gemela obligatoria (mismo blindaje sobre la plantilla) -->
        <record id="product_horas_lock_template" model="ir.rule">
            <field name="name">Producto Horas (plantilla): solo el Custodio modifica</field>
            <field name="model_id" ref="product.model_product_template"/>
            <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id', 'not in', [PRODUCT_HORAS_TMPL_IDS])]</field>
            <field name="groups" eval="[]"/>
            <field name="perm_read"   eval="False"/>
            <field name="perm_create" eval="False"/>
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="True"/>
        </record>
    </data>
</odoo>
```

> `PRODUCT_HORAS_VARIANT_IDS` / `PRODUCT_HORAS_TMPL_IDS` = los ids reales resueltos **en cada BD** (una fila por compañía; **verificar en PRE** y de nuevo en PRO, porque difieren). Si prefieres external ids estables, sustituye la lista por `[user.env.ref('zambudio_permisos.product_horas_aunna').id, user.env.ref('zambudio_permisos.product_horas_citric').id, user.env.ref('zambudio_permisos.product_horas_montoya').id, user.env.ref('zambudio_permisos.product_horas_ii').id]` (creados por `post_init_hook`).

> **Efecto:** el producto *Horas* no lo puede tocar **NADIE** (ni ventas/stock/contabilidad manager, ni `base.group_system`) salvo el custodio; los productos **normales** siguen editables por sus managers. `perm_write=True` con dominio que excluye esos ids cubre **cualquier** `write`: renombrar, **archivar** (`active=False`), cambiar `type` o `sale_ok`. `perm_create=False` (no molesta el alta de productos nuevos); `perm_read=False` (lectura libre, *Horas* aparece en desplegables de toda la operativa). Es exactamente el vector del incidente (`write` de renombrado + cambio de tipo).
>
> ⚠️ **Aplica el mismo patrón a la UdM *Horas*** por registro si no quieres congelar toda `uom.uom` (§1.A/1.B): `model_id ref="uom.model_uom_uom"`, dominio `[(1,'=',1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id','not in',[user.env.ref('uom.product_uom_hour').id])]`. El xmlid `uom.product_uom_hour` **sí es del núcleo** y resuelve igual en PRE/PRO, así que aquí `user.env.ref(...).id` es seguro (external id estable) — y **sigue sin usarse `ref()` suelto**.

---

### 1.E Tabla de decisión de patrón (fuente de verdad: qué patrón usar en cada maestro)

Tres patrones canónicos. Todos declaran los **cuatro** `perm_*` explícitamente y en maestros `perm_read=False` (no se restringe la lectura: los maestros aparecen en desplegables de toda la operativa). Todos son **reglas GLOBALES** (`<field name="groups" eval="[]"/>`) que se combinan en **AND** → no esquivables por el OR de otro grupo.

| Patrón | Dominio (`domain_force`) | perm_write/create/unlink | Aplica a |
|---|---|---|---|
| **P1 · GLOBAL + `has_group` (solo custodio)** | `[(1,'=',1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [(0,'=',1)]` | write/create/unlink=True (read=False) | `uom.uom`, `uom.category`, `res.currency`, `ir.sequence` |
| **P2 · GLOBAL + `has_group` AMPLIADO (contabilidad + custodio)** | write/create: `[(1,'=',1)] if (user.has_group('account.group_account_manager') or user.has_group('zambudio_permisos.group_master_data_custodian')) else [(0,'=',1)]` · unlink: **2ª regla global** solo custodio | write/create=True (ampliado); unlink=True (solo custodio) | `account.account`, `account.journal`, `account.tax`, `account.fiscal.position`, `account.analytic.account`, `account.analytic.plan` |
| **P3 · GLOBAL SCOPED por id (joya puntual)** | `[(1,'=',1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [('id','not in', IDS)]` | write=True, unlink=True, create=False (read=False) | producto **Horas** (`product.template` **+** `product.product`, regla gemela) |

**P1 (canónico) — sustituye al bloqueo "solo superusuario" de §1.A y al par block/allow de §1.B.** Una **única** regla global resuelve la contradicción "el custodio SÍ puede editar; nadie más" sin la fragilidad del OR (§1.B) ni la necesidad de entrar como uid 1 (§1.A):

```xml
<odoo>
    <data noupdate="1">
        <record id="uom_master_lock" model="ir.rule">
            <field name="name">UdM: solo el Custodio de Datos Maestros modifica</field>
            <field name="model_id" ref="uom.model_uom_uom"/>
            <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [(0, '=', 1)]</field>
            <field name="groups" eval="[]"/>                    <!-- SIN grupos = GLOBAL (AND) -->
            <field name="perm_read"   eval="False"/>
            <field name="perm_create" eval="True"/>
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="True"/>
        </record>
    </data>
</odoo>
```

**P2 (contabilidad + custodio) — para maestros que Contabilidad mantiene legítimamente** (el plan de cuentas se toca en el día a día). Se permite write/create a `account.group_account_manager` **o** al custodio; el `unlink` se restringe **solo** al custodio con una **segunda** regla global:

```xml
<odoo>
    <data noupdate="1">
        <!-- write/create: contabilidad O custodio -->
        <record id="account_account_write_lock" model="ir.rule">
            <field name="name">Cuenta contable: write/create a Contabilidad o Custodio</field>
            <field name="model_id" ref="account.model_account_account"/>
            <field name="domain_force">[(1, '=', 1)] if (user.has_group('account.group_account_manager') or user.has_group('zambudio_permisos.group_master_data_custodian')) else [(0, '=', 1)]</field>
            <field name="groups" eval="[]"/>
            <field name="perm_read"   eval="False"/>
            <field name="perm_create" eval="True"/>
            <field name="perm_write"  eval="True"/>
            <field name="perm_unlink" eval="False"/>       <!-- unlink NO va aquí -->
        </record>
        <!-- unlink: SOLO custodio (2ª regla global) -->
        <record id="account_account_unlink_lock" model="ir.rule">
            <field name="name">Cuenta contable: unlink solo Custodio</field>
            <field name="model_id" ref="account.model_account_account"/>
            <field name="domain_force">[(1, '=', 1)] if user.has_group('zambudio_permisos.group_master_data_custodian') else [(0, '=', 1)]</field>
            <field name="groups" eval="[]"/>
            <field name="perm_read"   eval="False"/>
            <field name="perm_create" eval="False"/>
            <field name="perm_write"  eval="False"/>
            <field name="perm_unlink" eval="True"/>
        </record>
    </data>
</odoo>
```

> **`product.category`** (excepción razonada): el `unlink` solo al custodio (patrón P2, 2ª regla), pero **write/create permitido a `stock.group_stock_manager`** — no se bloquea la operativa de categorías; el riesgo real es el borrado/reasignación de cuentas por categoría, no la edición.
>
> **P3** es el de §1.D (producto *Horas*): scoped por id, con regla **gemela** sobre `product.template` y `product.product`.
>
> ⚠️ Las secciones §1.A (bloqueo total "solo superusuario") y §1.B (block/allow con OR) quedan como **material histórico / didáctico**: explican por qué la global frena a `base.group_system` y por qué el OR es frágil. El patrón **primario a desplegar es esta tabla (P1/P2/P3)**. No mezcles P1/P2/P3 con el par block/allow sobre el **mismo** modelo.

---

## 2. `ir.model.access`: quitar `unlink` (y `write`) a modelos maestros

Recuerda: **las ACL suman**; una línea nueva con `perm_unlink=0` no resta. Para reducir de verdad hay que **sobrescribir la ACL nativa por su xmlid** bajando el perm. Esto es refuerzo secundario y **frágil entre upgrades**.

### 2.A Sobrescribir una ACL nativa para quitar unlink

**Qué hace:** localiza la ACL nativa que da `unlink` sobre `uom.uom` y la reescribe con `perm_unlink=0`. Como es el **mismo xmlid**, la sustituye (no añade otra).

**Dónde se pone:** para sobrescribir una ACL nativa usa un `<record>` XML apuntando al xmlid nativo:

```xml
<!-- security/override_native_acl.xml -->
<odoo>
    <data noupdate="0">
        <!-- Reescribe la ACL nativa de uom para quitar unlink/write/create a los usuarios base.
             ATENCION: el xmlid nativo exacto se VERIFICA EN PRE (query de §8). El de abajo
             (uom.access_uom_uom) es CONJETURA, no un xmlid confirmado. -->
        <record id="uom.access_uom_uom" model="ir.model.access">
            <field name="perm_read"   eval="True"/>
            <field name="perm_write"  eval="False"/>
            <field name="perm_create" eval="False"/>
            <field name="perm_unlink" eval="False"/>
        </record>
    </data>
</odoo>
```

> ⚠️ **(verificar en PRE):** el xmlid `uom.access_uom_uom` es una **conjetura**, no está confirmado. Localiza el real con la query de §8 antes de escribirlo. Sobrescribir la ACL de OTRO módulo por su xmlid funciona en Odoo pero es delicado en upgrades: **documenta que hay que revalidarlo tras cada actualización**. Esta capa es refuerzo; el mecanismo principal sigue siendo §1.

### 2.B ACL propia para tu grupo custodio (esto SÍ es una línea nueva legítima)

Cuando creas el grupo custodio, necesita su ACL de escritura sobre los maestros. Aquí **añadir** líneas es correcto (concedes permiso, no lo quitas):

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_custodian_uom,custodian.uom,uom.model_uom_uom,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_custodian_uom_categ,custodian.uom.categ,uom.model_uom_category,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_custodian_product_tmpl,custodian.product.template,product.model_product_template,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_custodian_product_prod,custodian.product.product,product.model_product_product,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_custodian_account,custodian.account.account,account.model_account_account,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_custodian_journal,custodian.account.journal,account.model_account_journal,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_custodian_analytic,custodian.analytic.account,analytic.model_account_analytic_account,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_custodian_sequence,custodian.ir.sequence,base.model_ir_sequence,zambudio_permisos.group_master_data_custodian,1,1,1,1
access_custodian_currency,custodian.res.currency,base.model_res_currency,zambudio_permisos.group_master_data_custodian,1,1,1,1
```

> Cabecera exacta de `ir.model.access.csv`: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`. Verifica en PRE los `model_id:id` marcados dudosos en §1.C (analítica, categoría UdM). **Recuerda:** dar ACL al custodio no basta si además hay una `ir.rule` **global** (§1.A) sobre ese modelo — la global bloquearía también al custodio. Por eso para lo que gestione el custodio usa §1.B, no §1.A.

### 2.C Regla de red que ya tienes gratis: las FK

Muchos maestros no se pueden **borrar** por FK (ondelete RESTRICT): UdM usada por productos/líneas analíticas, cuenta con apuntes, diario con asientos. Es una red **parcial**: solo cubre `unlink` y solo si hay referencias vivas; **no impide renombrar** (`write`). Por eso el incidente (renombrado + cambio de tipo) no lo paró ninguna FK. **No confíes en las FK como blindaje.**

---

## 3. Ocultar menús técnicos y de datos maestros por grupo

Esto es **UI, no seguridad de fondo** (la seguridad la dan §1 y §2), pero reduce la superficie de error: si el menú de UdM no se ve, nadie entra por accidente. Se hace ocultando `ir.ui.menu` a grupos que no deban verlos.

### 3.A Restringir un menú a un grupo (por UI o por XML)

**Por UI (Ajustes técnicos):** Activar modo desarrollador → Ajustes → Técnico → Interfaz de usuario → **Menús** → abrir el menú (p. ej. "Unidades de medida") → campo **Grupos** → poner solo `zambudio_permisos.group_master_data_custodian`. Reversible, no requiere módulo. **Aviso:** se pierde en algunos upgrades y no queda en código → documentarlo.

**Por XML (recomendado, viaja con el módulo):**

```xml
<odoo>
    <data noupdate="0">
        <!-- Oculta menús de UdM a todos salvo custodio.
             xmlids de menú/acción (verificar en PRE con la query de §8). -->
        <menuitem id="uom.menu_uom_categ_form_action"
                  groups="zambudio_permisos.group_master_data_custodian"/>
        <menuitem id="uom.product_uom_menu"
                  groups="zambudio_permisos.group_master_data_custodian"/>
    </data>
</odoo>
```

> ⚠️ **(verificar en PRE)** los xmlids `uom.menu_uom_categ_form_action`, `uom.product_uom_menu` son **conjeturas**; los nombres de menú/acción de UdM varían entre versiones. Confírmalos con la query de §8 antes de escribirlos.

### 3.B Menús de datos maestros a restringir (tabla operativa)

| Menú / zona | Módulo | A quién dejarlo | Nota |
|---|---|---|---|
| Unidades de medida (unidades y categorías) | `uom` | Custodio | Gated además por `uom.group_uom` |
| Productos → Categorías | `product` | Custodio + managers que lo necesiten | Reasigna cuentas contables |
| Contabilidad → Configuración → Plan de cuentas | `account` | Contable + custodio | — |
| Contabilidad → Configuración → Diarios | `account` | Custodio | Secuencias |
| Contabilidad → Configuración → Cuentas analíticas / Planes | `account`/`analytic` | Custodio | La 90/271 |
| Ajustes técnicos → Secuencias | `base` | Custodio (solo dev mode) | Gated por `base.group_no_one` |
| Ajustes técnicos → Automatizaciones (base_automation) | `base_automation` | Custodio de sistema | Studio; ver §5 |
| Ajustes técnicos → Acciones del servidor | `base` | Custodio de sistema | Ver §5 |
| Ajustes técnicos → Reglas de registro / Reglas de acceso | `base` | Custodio de sistema | No dejar que se auto-desactiven |

### 3.C Desactivar la *función* UdM múltiple (opcional, y su límite)

El toggle **`uom.group_uom`** ("Manage Multiple Units of Measure") en Ajustes generales oculta los campos de UdM en la UI. **NO protege los datos:** la UdM *Horas* sigue existiendo y `hr_timesheet` la sigue necesitando; solo desaparece de la interfaz. Úsalo únicamente si nadie necesita múltiples UdM de forma cotidiana; el blindaje real es §1.

---

## 4. Restringir developer mode y el acceso a Ajustes a custodios

El "Administrador" del incidente es `base.group_system` ("Administración: Ajustes" en v19). **`base.group_system` es CUSTODIA, no un rol de trabajo.** La medida más eficaz y sin código: **quitar `base.group_system` a todos los usuarios funcionales.** Sin ese grupo no ven Ajustes, ni Apps/store, ni menús técnicos, y **conservan su trabajo diario** si mantienen sus grupos funcionales (`account.group_account_user`, `stock.group_stock_user`, etc.).

### 4.A Los dos "admin" que hay que separar

| Concepto | xmlid | Da acceso a | Quién |
|---|---|---|---|
| Admin técnico (Ajustes) | `base.group_system` | Ajustes, instalar funciones, menús técnicos, editar maestros de sistema, Studio | Solo custodio de sistema (1 titular + 1 suplente) |
| Admin de accesos | `base.group_erp_manager` | Crear/editar usuarios y asignar grupos (sin el resto de Ajustes) | Gestor de usuarios delegado (opcional) |
| Técnico oculto (dev) | `base.group_no_one` | Campos/menús "developer" (solo visibles en modo desarrollador) | Todos los internos lo llevan; solo se "revela" en dev mode |

Jerarquía real v19: `base.group_system ⊃ base.group_erp_manager ⊃ base.group_user`. `base.group_system` implica `base.group_erp_manager`.

> **(verificar en PRE)** si `base.group_system` sigue implicando `base.group_sanitize_override` (grupo de override de saneado HTML) en v19 — no lo doy por confirmado.

### 4.B Sobre "restringir el developer mode"

**No se puede "quitar" `base.group_no_one`** a alguien de forma útil: los internal users lo llevan de facto y el modo desarrollador solo **desvela** menús/campos técnicos en la UI; no concede permisos de datos por sí mismo. El peligro real es la combinación **`base.group_system` + dev mode**, que muestra los menús técnicos peligrosos (UdM, secuencias, automatizaciones). Conclusión: **el control efectivo es quitar `base.group_system`**, no perseguir el dev mode.

Refuerzo opcional (ocultar menús técnicos aunque alguien active dev mode): restringir los `ir.ui.menu` técnicos a un grupo custodio (§3.A), de modo que el menú no aparezca aunque el usuario esté en modo desarrollador.

### 4.C Forzar 2FA a los custodios (nativo, sin módulo)

Ajustes → Permisos → **"Enforce two-factor authentication"** (aplicable a Empleados o Todos). Recomendación: forzarlo al menos para el grupo Settings/custodios. No requiere OCA.

---

## 5. Restringir importaciones/exportaciones masivas y server actions peligrosas

Una importación CSV puede **pisar datos maestros** en masa (reescribir nombres de productos, UdM) sorteando la UI campo a campo. Las server actions y automatizaciones de Studio ejecutan `write`/`unlink` programáticos.

### 5.A Exportación: restringir a un grupo

El acceso a **Exportar** lo da `base.group_allow_export` ("Allowed to export", implicado por `base.group_system`). Para limitar la fuga de datos maestros/contactos:

- **Nativo:** quitar `base.group_allow_export` a quien no deba exportar. **Verificar en PRE** que el botón Exportar desaparece.
- **OCA (evaluar, verificar port 19):** `web_disable_export_group` (OCA/web) limita el botón Exportar a un grupo; `base_export_manager` (OCA/server-ux) añade permiso de export **por modelo**. Ambos **verificar port a 19** antes de PRO. Ver [[07-auditoria-trazabilidad-hardening]].

### 5.B Importación: restringir a un grupo

No hay grupo nativo dedicado a "importar". Opciones:
- **OCA:** `base_import_security_group` hace el import CSV/Excel opcional por grupo (verificar port 19).
- **Sin módulo:** el import está ligado a tener `create`/`write` sobre el modelo; si el custodio es el único con `write` sobre los maestros (§1/§2), un import de no-custodio sobre esos modelos **falla igualmente** por la record rule. Es decir: **el blindaje de §1 ya cubre el import masivo de maestros.**

### 5.C Server actions y automatizaciones (Studio / base_automation)

**Problema de gobernanza:** muchas automatizaciones son de **Studio / `base_automation` / `ir.actions.server`** y **NO viajan con código**; se editan en la UI y pueden ejecutar cambios masivos. Además, **una server action se ejecuta con los permisos del usuario que la dispara** (salvo que fuerce sudo internamente), así que las record rules de §1 **también frenan** una automatización mal escrita que intente tocar *Horas* desde un usuario normal. Medidas:

1. **Restringir quién ve/edita** los menús de Automatizaciones y Acciones del servidor al custodio de sistema (§3.A — **verificar xmlids de menú en PRE**).
2. **Auditar quién los cambia** con `auditlog` (OCA/server-tools 19) sobre los modelos `base.automation`, `ir.actions.server`, `ir.rule`, `ir.model.access`, `ir.ui.menu`, `ir.model.fields`. Así "quién cambió la seguridad/automatización" queda registrado. Ver [[07-auditoria-trazabilidad-hardening]].
3. Recordatorio operativo: al desplegar, **revisar que ninguna automatización de Studio reintroduce el bug** (p. ej. una que fije la cuenta 90 sin ser consciente de compañía). Ver [[05-record-rules-multiempresa]].

---

## 6. Campos sensibles con `groups=` (blindaje a nivel de campo)

Poner `groups=` **en la definición del field** es seguridad REAL: el ORM elimina el campo de lectura/escritura para quien no esté en el grupo, incluso por RPC. (En la **vista** solo sería visibilidad, no sirve.) Para editar el field nativo hay que extender el modelo:

```python
# models/product_template.py (módulo zambudio_permisos)
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Ejemplo ILUSTRATIVO. Ver AVISO FUERTE abajo: NO recomendado para name/uom_id.
    x_flag_config_interno = fields.Boolean(
        groups='zambudio_permisos.group_master_data_custodian')
```

> ⚠️ **AVISO FUERTE:** poner `groups=` en `name`, `uom_id` o `type` de `product.template` es **muy agresivo** — si un campo tan central se oculta a los no-custodios, se **rompen listados, informes, PDFs, facturas y búsquedas** para todo el mundo (el campo desaparece del ORM para ellos). **NO se recomienda para campos centrales.** Para proteger el producto *Horas* usa la **record rule por registro de §1.D** (bloquea solo ese producto, sin ocultar el campo a nadie).
>
> Uso legítimo de `groups=` en field: campos que **tú** creas en módulos custom y que solo el custodio debe tocar (flags de configuración, cuentas por defecto internas), nunca campos nativos usados por informes.

---

## 7. Protección de periodos contables (lock dates) — complemento

No blinda **nombres** del plan, blinda **asientos por fecha**. En v18/19 las lock dates se refactorizaron; **verificar nombres/ubicación exactos en PRE** (pueden estar en `res.company` o en un modelo dedicado de bloqueo):

| Campo | Qué bloquea | Reversible |
|---|---|---|
| `fiscalyear_lock_date` | Crear/editar asientos con fecha ≤ esa (todos los usuarios) | Sí (por asesor) |
| `tax_lock_date` | Declaración de impuestos | Sí |
| `hard_lock_date` | **Bloqueo duro/irreversible** (v18+): ni asesores ni superusuario desbloquean | **NO** |
| `sale_lock_date` / `purchase_lock_date` | Por tipo de diario (v18+, verificar en PRE) | Sí |

Excepciones puntuales: modelo `account.lock_exception` (v18+, verificar en PRE). Las lock dates **no protegen** el renombrado del plan de cuentas ni la config de diarios → para eso, §1.

---

## 8. Cómo VERIFICAR los xmlids y ACL reales en PRE (antes de escribir nada definitivo)

Queries de **solo lectura** (seguras) para confirmar lo marcado "verificar en PRE". Ejecutar contra `grupo_zambudio_prod_pruebas`.

**ACL nativas que conceden write/unlink sobre un maestro** (para §2.A):
```sql
SELECT a.id, d.module || '.' || d.name AS xmlid, a.name,
       a.perm_read, a.perm_write, a.perm_create, a.perm_unlink,
       g.name AS grupo
FROM ir_model_access a
JOIN ir_model m ON m.id = a.model_id
LEFT JOIN res_groups g ON g.id = a.group_id
LEFT JOIN ir_model_data d ON d.model='ir.model.access' AND d.res_id=a.id
WHERE m.model IN ('uom.uom','product.template','product.product',
                  'account.account','account.journal','ir.sequence','res.currency')
  AND (a.perm_write OR a.perm_unlink)
ORDER BY m.model;
```

**Record rules existentes sobre un modelo** (para comprobar qué grupos re-permiten antes de aplicar §1.B/§1.D):
```sql
SELECT r.id, m.model, r.name, r.domain_force, r.global, g.name AS grupo
FROM ir_rule r
JOIN ir_model m ON m.id=r.model_id
LEFT JOIN rule_group_rel rg ON rg.rule_group_id = r.id
LEFT JOIN res_groups g ON g.id = rg.group_id
WHERE m.model IN ('uom.uom','product.template','product.product')
ORDER BY m.model;
```
> **(verificar en PRE)** el nombre de la tabla puente regla↔grupo (`rule_group_rel` en versiones recientes); confírmalo en el esquema si la query falla.

**Record rules que mencionan compañía** (inventario multiempresa, §04):
```sql
SELECT r.id, m.model, r.name, r.domain_force, r.global
FROM ir_rule r JOIN ir_model m ON m.id=r.model_id
WHERE r.domain_force ILIKE '%company_id%'
ORDER BY m.model;
```

**xmlid real de un modelo** (para los `model_id ref=` dudosos: analítica, categoría UdM):
```sql
SELECT d.module || '.' || d.name AS xmlid, m.model
FROM ir_model m JOIN ir_model_data d ON d.model='ir.model' AND d.res_id=m.id
WHERE m.model IN ('account.analytic.account','account.analytic.plan',
                  'account.analytic.distribution.model','uom.category','uom.uom');
```

**xmlid real de un menú** (para §3):
```sql
SELECT d.module || '.' || d.name AS xmlid, mnu.name
FROM ir_ui_menu mnu JOIN ir_model_data d ON d.model='ir.ui.menu' AND d.res_id=mnu.id
WHERE mnu.name::text ILIKE '%unit%' OR mnu.name::text ILIKE '%medida%'
   OR mnu.name::text ILIKE '%secuencia%' OR mnu.name::text ILIKE '%sequence%';
```

**Usuarios con `base.group_system` / `base.group_erp_manager`** (revisión periódica de gobernanza):
```sql
SELECT u.login, g_ext.name AS grupo
FROM res_users u
JOIN res_groups_users_rel rel ON rel.uid = u.id           -- (verificar nombre tabla/columnas en PRE)
JOIN res_groups grp ON grp.id = rel.gid
JOIN ir_model_data g_ext ON g_ext.model='res.groups' AND g_ext.res_id=grp.id
WHERE g_ext.module='base' AND g_ext.name IN ('group_system','group_erp_manager')
ORDER BY u.login;
```
> **(verificar en PRE)** el nombre de la tabla/columnas de la relación usuario↔grupo. En v19 el campo en `res.users` se renombró a **`group_ids`** (`all_group_ids` para el efectivo con implicados); el clásico `groups_id` de v17/18 ya no aplica, y la tabla relacional puede tener otro nombre. En **dominios/código** prefiere `user.has_group('xmlid')` antes que referenciar la tabla directamente.

---

## 9. UI (Ajustes técnicos) vs módulo de refuerzo: cuándo cada uno

| Vía | Ventajas | Inconvenientes | Cuándo usarla |
|---|---|---|---|
| **UI / Ajustes técnicos** | Inmediato, reversible, no requiere despliegue | **No viaja con código**, se puede perder en upgrades, sin control de versiones, cualquiera con `group_system` lo revierte | Pruebas rápidas en PRE, medidas temporales, ajustes finos que aún no consolidas |
| **Módulo de refuerzo** (`zambudio_permisos`) | Versionado en git, revisable, reproducible PRE→PRO, resistente a upgrades, auditable | Requiere despliegue, más lento de iterar | **Estado final** de todo lo de este documento |

**Recomendación de gobernanza:** iterar y validar en PRE por UI, y **consolidar el resultado en un módulo de refuerzo**. Nunca dejar el blindaje solo en la UI de PRO: un `group_system` lo desharía sin rastro (salvo que `auditlog` lo capture).

---

## 10. Consolidación a medio plazo: módulo `zambudio_permisos` (solo mención)

Todo lo anterior debería vivir, a medio plazo, en un **módulo de refuerzo llamado `zambudio_permisos`** (autor "Zambudio", según convención de naming del proyecto). **No se crea en este documento** — aquí solo se deja fijada su estructura objetivo:

```
zambudio_permisos/
├── __manifest__.py                     # depends: base, uom, product, account, analytic, hr_timesheet
├── security/
│   ├── security_groups.xml             # define group_master_data_custodian (§1.B, §2.B)
│   ├── ir_rule_master_data.xml         # reglas §1 (global y block/allow)
│   ├── ir.model.access.csv             # ACL del custodio §2.B
│   └── override_native_acl.xml         # sobrescritura ACL nativas §2.A (opcional, frágil)
├── data/
│   └── product_horas_external_id.xml   # xmlid para el producto Horas §1.D
├── views/
│   └── menu_restrictions.xml           # ocultar menús técnicos §3
└── models/
    └── product_template.py             # groups= en campos custom §6 (con cautela)
```

Definición del grupo custodio (referencia, va en `security_groups.xml`):
```xml
<record id="privilege_zambudio_security" model="res.groups.privilege">
    <field name="name">Zambudio · Seguridad</field>
</record>
<record id="group_master_data_custodian" model="res.groups">
    <field name="name">Custodio de Datos Maestros</field>
    <field name="privilege_id" ref="privilege_zambudio_security"/>
    <field name="implied_ids" eval="[Command.link(ref('base.group_user'))]"/>
</record>
```
> En v19 el grupo cuelga de un **`res.groups.privilege`** (campo `privilege_id`), NO del antiguo `category_id` directo de v17/18. El `res.groups.privilege` a su vez enlaza con la `ir.module.category` vía su propio `category_id`. Ver [[01-modelo-seguridad-odoo19]].
>
> ⚠️ El custodio hereda `base.group_user` (`implied_ids`), por eso las reglas block/allow de §1.B y §1.D funcionan (le aplican ambas y el OR lo desbloquea). Si además debe ver la contabilidad/analítica para arreglarla, añade también los grupos funcionales que necesite (`account.group_account_manager`, `analytic.group_analytic_accounting` — verificar en PRE).

---

## 11. Checklist de despliegue (PRE → PRO)

1. [ ] Confirmar en PRE **todos** los xmlids marcados "(verificar en PRE)" con las queries de §8 (analítica `analytic.*`, categoría UdM, ACL nativas, menús, tabla usuario↔grupo).
2. [ ] Crear el grupo `group_master_data_custodian` (con su `res.groups.privilege`) y asignarlo a 1-2 personas; añadirle los grupos funcionales que necesite para operar.
3. [ ] Aplicar reglas §1 empezando por lo **crítico y de bajo impacto**, usando el patrón **block/allow §1.B** para lo que el custodio deba mantener (UdM, categoría UdM) y **global §1.A** solo para lo que nadie deba tocar (moneda). **`ir.sequence`: no bloquear `write` sin probar numeración (ver aviso §1.A).** Probar: renombrar la UdM *Horas* como usuario normal → debe fallar; como custodio → debe funcionar.
4. [ ] Aplicar **§1.D** al producto *Horas* (par block+allow por registro, no todo `product.template`) y, si aplica, a la UdM *Horas* por registro con `uom.product_uom_hour`.
5. [ ] **Ejecutar los flujos reales en PRE:** crear un parte de horas, facturar un proyecto WIP, **postear una factura y validar su número**, alta de un producto normal (no *Horas*) por un comercial → nada debe romperse.
6. [ ] Comprobar el **aislamiento multiempresa** (AUNNA/CITRIC) sobre los maestros con compañía y sobre `account.analytic.distribution.model` (que no filtre mal la 90/271). Ver [[05-record-rules-multiempresa]].
7. [ ] Quitar `base.group_system` a los usuarios funcionales (§4); verificar que conservan su trabajo diario.
8. [ ] Forzar 2FA a custodios (§4.C).
9. [ ] Instalar `auditlog` (OCA 19) sobre maestros + modelos de seguridad/automatización (§5.C, [[07-auditoria-trazabilidad-hardening]]).
10. [ ] Ocultar menús técnicos de maestros (§3) — cosmético, al final.
11. [ ] **Doble control:** todo lo anterior revisado por dos personas antes de replicar en PRO.
12. [ ] Consolidar el resultado validado en el módulo `zambudio_permisos` (§10) y desplegar desde git, no a mano.

> **Recordatorio final:** el blindaje técnico (§1–§6) es necesario pero **no suficiente**. El eje de la solución es doble: (a) **regla global / block-allow** que frena incluso a `base.group_system`, y (b) **gobernanza** — pocas personas con `base.group_system`, custodio dedicado, cambios primero en PRE, y auditoría con `auditlog`. Ver [[02-catalogo-de-roles]] y [[00-principios-y-gobernanza]].