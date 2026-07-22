# Cómo funciona la seguridad en Odoo 19

> Referencia didáctica y operativa del modelo de seguridad de Odoo 19, aplicada al proyecto Grupo Zambudio / Aunna IT (BD `grupo_zambudio_prod`, entorno PRE `grupo_zambudio_prod_pruebas`). Es el documento base: aquí se explica *cómo* funciona cada pieza; el diseño concreto de roles y el blindaje de datos maestros van en documentos aparte ([[02-catalogo-de-roles]], [[04-blindaje-datos-maestros]], [[05-record-rules-multiempresa]], [[07-auditoria-trazabilidad-hardening]], [[00-principios-y-gobernanza]] — nombres orientativos, ajustar a los ficheros reales de `new/permisos`).

Regla transversal de todo el proyecto: **cualquier cambio de seguridad se prueba SIEMPRE primero en PRE** (`erp-pre.zambudio.es`) y solo después se lleva a PRO (`erp.zambudio.es`). Los xmlids del núcleo que no he podido confirmar contra fuente van marcados **(verificar en PRE)**.

> ⚠️ **Aviso v19 (renombrado masivo de campos).** Odoo 19 es la mayor reestructuración interna de los últimos años. Además de `privilege_id` (ver §2), se renombraron campos de grupos en varios modelos: `res.users.groups_id → group_ids`, `res.groups.users → user_ids`, y **el mismo renombrado se propaga** a `ir.ui.menu`, `ir.ui.view`, `ir.actions.act_window`, `ir.actions.server` y `ir.actions.report` (su antiguo `groups_id → group_ids`). Todo dominio, record rule o vista custom que use `groups_id` debe migrarse a `group_ids`/`all_group_ids`, o mejor a `user.has_group(...)`. Revisar TODOS los módulos `aunna_*`/`zambudio_*` antes de portar.

---

## 0. El modelo mental: tres capas que TODAS deben pasar

Odoo compone la seguridad en tres capas independientes. Una petición de un usuario (leer, escribir, crear, borrar un registro) solo se permite si **las tres** la dejan pasar:

| # | Capa | Objeto técnico | Qué decide | Granularidad |
|---|---|---|---|---|
| 1 | **Grupos / roles** | `res.groups` (+ `res.groups.privilege` en v19) | A qué *menús*, *acciones* y *vistas* llegas, y a qué grupos perteneces | Usuario → grupo |
| 2 | **Access Rights (ACL)** | `ir.model.access` (CSV) | El *verbo* CRUD por MODELO: ¿puedes read/write/create/unlink este modelo? | Grupo × modelo |
| 3 | **Record Rules** | `ir.rule` | El *alcance*: ¿qué FILAS concretas dentro del modelo? (multiempresa, "solo mis documentos") | Grupo × modelo × dominio |

Frase para recordarlo:

> **El grupo da el menú. El `ir.model.access` da el verbo. El `ir.rule` da el alcance.**

Consecuencias que hay que tener grabadas:

- Si un modelo **no tiene ninguna línea ACL** para ningún grupo del usuario → **sin acceso** (salvo superusuario).
- Los permisos de la capa 2 son **aditivos (OR/unión)**: si CUALQUIER grupo del usuario concede `write`, el usuario puede escribir. **Añadir un ACL con `perm_write=0` NO resta nada.**
- Para *quitar* un permiso peligroso NO existe "otro grupo que lo tape": hay que usar una **record rule restrictiva** (idealmente global) o `groups=` en el campo, o **retirar el `write` de la ACL del grupo amplio**. Esto es la raíz de casi todo el diseño de blindaje.
- El **superusuario real** (`base.user_root`, uid 1, `env.su`) **ignora las record rules Y las ACL**. Un usuario "Administrador" con `base.group_system` **NO es** el superusuario: las record rules SÍ le aplican. Esta distinción es la que permite blindar los datos maestros del incidente.

> ⚠️ **Cuarta vía que se salta las rules: `sudo()` y las automatizaciones.** El código en `sudo()`, las **acciones de servidor** (`ir.actions.server`) y las **automatizaciones** (`base.automation` / Studio) se ejecutan con privilegios elevados y **NO pasan por record rules ni ACL**. Como en este proyecto muchas automatizaciones son de Studio, una automatización mal hecha puede modificar un dato maestro aunque las rules lo protejan. La gobernanza de quién crea automatizaciones es parte del blindaje (ver [[00-principios-y-gobernanza]]).

---

## 1. Grupos: `res.groups` y herencia `implied_ids`

Un **grupo** (`res.groups`) es lo que coloquialmente llamamos "rol". Un usuario pertenece a varios grupos y acumula (suma) sus permisos.

### 1.1 Campos clave de `res.groups` (v19)

- `_order = 'privilege_id, sequence, name, id'`
- `name` — nombre del grupo. **En v19 solo es único DENTRO de su privilege** (constraint `UNIQUE (privilege_id, name)`). Por eso hay muchos grupos llamados "User", "Administrator", "Create"… distinguidos por su privilege.
- `full_name` = `"privilege_id.name / name"` → así aparece "Timesheets / User: own timesheets only".
- `privilege_id` — M2one a `res.groups.privilege` (ver §2). **Novedad v19**, sustituye al `category_id` directo.
- `implied_ids` — M2m a sí mismo: "los usuarios de este grupo pertenecen **implícitamente** también a esos grupos". Es la **herencia** (superconjuntos).
- `implied_by_ids` — inversa: grupos que implican a éste.
- `all_implied_ids` / `all_implied_by_ids` — **cierre transitivo** (recursivo).
- `disjoint_ids` — grupos mutuamente excluyentes (interno vs portal vs público). Hay `@api.constrains` que valida la disjunción **(verificar nombre exacto del método en PRE)**.
- `user_ids` (explícitos) / `all_user_ids` (explícitos + implícitos). **(En v19 el campo se llama `user_ids`, antes `users`.)**
- `model_access` (O2m a `ir.model.access`), `rule_groups` (M2m a `ir.rule` no globales), `menu_access` (M2m `ir.ui.menu`), `view_access` (M2m `ir.ui.view`).

### 1.2 Herencia `implied_ids` — aditiva y automática

Al asignar un grupo "superior", Odoo asigna automáticamente todos los `implied_ids`. Cadena típica de una app:

```
sale.group_sale_manager
   └─ implied_ids → sales_team.group_sale_salesman
                        └─ implied_ids → base.group_user  (Internal User)
```

Reglas prácticas de la herencia:

- **Todo empleado interno lleva `base.group_user`.** El portal cliente lleva `base.group_portal` y **nunca** `base.group_user` (son disjuntos).
- Es **aditiva**: dar Manager arrastra User + base. **No se puede "restar" con otro grupo.** Si un grupo concede algo peligroso, se niega con `ir.rule` o `groups=` en el campo (nunca con "un grupo que lo tape").
- Si en el formulario de usuario seleccionas "Administrator" en una app, estás asignando el grupo manager de esa app **y** todos sus implicados.

### 1.3 Ejemplo XML real de definición de grupo (patrón v19)

De `product/security/product_security.xml` (grupo "Create" de producto):

```xml
<record id="group_product_manager" model="res.groups">
    <field name="name">Create</field>
    <field name="privilege_id" ref="res_groups_privilege_product"/>  <!-- (verificar xmlid del privilege en PRE) -->
    <field name="implied_by_ids" eval="[Command.link(ref('base.group_system'))]"/>
</record>
```

Nota de sintaxis: en v19 conviven `Command.link(ref(...))` y la tupla clásica `(4, ref(...))`. Ambas válidas. `implied_by_ids` aquí significa: "`base.group_system` implica este grupo" (todo Administrador de sistema puede crear productos).

---

## 2. NOVEDAD v19: `res.groups.privilege` y `privilege_id`

En v17/v18 el grupo colgaba directamente de una `ir.module.category` mediante `category_id`. **En v19 esto cambia**: se interpone un modelo nuevo, `res.groups.privilege`, y el grupo apunta a él con `privilege_id`.

Cadena real v19:

```
res.groups.privilege_id  →  res.groups.privilege  →  category_id  →  ir.module.category
```

### 2.1 Definición del modelo `res.groups.privilege` (v19)

```python
class ResGroupsPrivilege(models.Model):
    _name = 'res.groups.privilege'
    _order = 'sequence, name, id'
    name = fields.Char(required=True, translate=True)
    description = fields.Text()
    placeholder = fields.Char(default="No")   # texto del selector en el form de usuario
    sequence = fields.Integer(default=100)
    category_id = fields.Many2one('ir.module.category', string='Category', index=True)
    group_ids = fields.One2many('res.groups', 'privilege_id', string='Groups')
```

> (Nombres de campos verificados en el repo del proyecto; si portas código, confirma `placeholder`/`description` en PRE por si cambian en un point-release.)

### 2.2 Qué es un *privilege* en la práctica

Un privilege es el **desplegable** que ves en la ficha del usuario: cada app aparece como una fila con un selector `Ninguno / User / Manager / Administrator`. Ese selector agrupa varios `res.groups` que comparten `privilege_id` y se ordenan por `sequence`. El `placeholder` es el texto que se ve cuando no hay nada seleccionado ("No").

### 2.3 Ejemplo de grupo custom nuevo (patrón v19)

En los módulos custom del proyecto, las record rules ya se anclan a grupos por xmlid del núcleo (patrón real usado en `zambudio_timesheet_approval_by_project/security/ir_rule.xml`). Cuando definas el **grupo custodio** (xmlid canónico `zambudio_permisos.group_master_data_custodian`), en v19 debes crear su privilege o reutilizar uno y referenciarlo con `privilege_id`, NO con `category_id`:

```xml
<!-- Privilege propio para agrupar el/los grupos de gobernanza Zambudio -->
<record id="res_groups_privilege_zambudio_gobernanza" model="res.groups.privilege">
    <field name="name">Gobernanza Zambudio</field>
    <field name="sequence">200</field>
    <field name="category_id" ref="base.module_category_hidden"/>  <!-- (verificar xmlid en PRE) -->
</record>

<record id="group_master_data_custodian" model="res.groups">
    <field name="name">Custodio de Datos Maestros</field>
    <field name="privilege_id" ref="res_groups_privilege_zambudio_gobernanza"/>
    <field name="implied_ids" eval="[Command.link(ref('base.group_user'))]"/>
</record>
```

> A lo largo del documento el grupo custodio se referencia con su xmlid **canónico**: `zambudio_permisos.group_master_data_custodian` (rol "Custodio de Datos Maestros"). `zambudio_permisos` es el **módulo de refuerzo de referencia**; puede crearse a futuro, o crearse el grupo por UI (en ese caso su xmlid real se resolverá en PRE — marcar **(verificar en PRE)**). Este grupo es **funcional**: NO implica `base.group_system` ni es el uid 1; son las reglas de blindaje las que lo RE-PERMITEN explícitamente. El custodio hereda `base.group_user` para poder trabajar con normalidad.
>
> **Nombres OBSOLETOS** (usados en borradores previos) que quedan sustituidos por el canónico: `zambudio_custom`, `zambudio_master_data`, `zambudio_master_data_custody`, `zambudio_master_data_lock`, `zambudio_security_hardening`, `group_master_data_custody` y cualquier otra variante. Cualquier otro nombre que aparezca en versiones previas es histórico; **usar siempre el canónico**.

> ⚠️ **Aviso de migración v17/18→v19:** cualquier grupo custom antiguo (`aunna_*`) que use `category_id` directo hay que reescribirlo a `privilege_id` en v19, y cualquier `groups_id` a `group_ids`. Revisar los módulos `aunna_*` antes de portar.

---

## 3. Access Rights: `ir.model.access` (la capa CRUD por modelo)

Es la capa 2: decide **el verbo** (read/write/create/unlink) por **modelo** y por **grupo**. Se declara en un CSV llamado `ir.model.access.csv` dentro de `security/` del módulo.

### 3.1 Cabecera exacta del CSV

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

| Columna | Significado |
|---|---|
| `id` | xmlid único de la línea (p. ej. `access_mi_modelo_user`) |
| `name` | Nombre legible |
| `model_id:id` | xmlid del modelo, con formato `model_<modelo_con_guiones_bajos>` (p. ej. `uom.model_uom_uom`, `product.model_product_template`) |
| `group_id:id` | xmlid del grupo (vacío = aplica a **todos los grupos**; con una ACL de grupo vacío el modelo queda accesible incluso a usuarios sin grupo específico — usar con cuidado) |
| `perm_read` | 1/0 — leer |
| `perm_write` | 1/0 — modificar |
| `perm_create` | 1/0 — crear |
| `perm_unlink` | 1/0 — borrar |

### 3.2 Ejemplo copiable

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_uom_uom_user_readonly,uom.uom solo lectura usuarios,uom.model_uom_uom,base.group_user,1,0,0,0
access_uom_uom_custodio_full,uom.uom custodio total,uom.model_uom_uom,zambudio_permisos.group_master_data_custodian,1,1,1,1
```

> ⚠️ **Esto por sí solo NO blinda la UdM.** Añadir estas dos líneas no elimina el `write`/`unlink` que ya conceden **otras ACL nativas** de `uom.uom` (p. ej. las de `uom.group_uom`, product manager o `base.group_system`). Las ACL se SUMAN (§3.3). El blindaje real exige, además: (a) que ningún grupo funcional amplio tenga `write` sobre `uom.uom`, y (b) una record rule (§4.5) como backstop. Verifica en PRE qué ACL nativas conceden `write` sobre `uom.uom` antes de dar nada por cerrado.

### 3.3 Reglas de combinación (CRÍTICO)

- Los ACL de varios grupos **se SUMAN (unión/OR)**. Un usuario puede escribir si **cualquiera** de sus grupos lo concede.
- **Añadir una línea con `perm_write=0` NO resta** el permiso que otro grupo ya concede. Para reducir de verdad hay que **sobrescribir la línea ACL nativa** por su xmlid (frágil entre upgrades, §3.4) o —mejor— usar una **record rule global** (§4.5).
- Si ningún grupo del usuario tiene línea para el modelo → sin acceso.
- El superusuario ignora esta capa.

### 3.4 Sobrescribir un ACL nativo (bajar permisos)

Para quitar `write`/`unlink` que un grupo del núcleo concede, se sobrescribe la línea por su xmlid real (localizarlo antes en PRE):

```xml
<!-- Ejemplo conceptual: neutralizar write/unlink de una ACL nativa. Localizar el xmlid REAL en PRE. -->
<record id="uom.access_uom_uom_manager" model="ir.model.access">  <!-- (verificar xmlid en PRE) -->
    <field name="perm_write" eval="0"/>
    <field name="perm_unlink" eval="0"/>
</record>
```

> ⚠️ **Frágil entre upgrades.** Al actualizar el módulo `uom`, su CSV nativo se reimporta y **restaura** `perm_write=1`; tu override solo vuelve a aplicarse al reactualizar TU módulo, y el orden de carga importa. Úsalo como refuerzo, no como mecanismo principal. El blindaje fuerte es la record rule global (§4.5) combinada con no dar `write` a los grupos amplios.

---

## 4. Record Rules: `ir.rule` (la capa de FILAS)

Es la capa 3: filtra **qué registros** ve/edita un usuario dentro de un modelo, mediante un dominio Odoo.

### 4.1 Campos de `ir.rule` (v19)

- `model_id` — modelo afectado.
- `groups` — M2m a `res.groups`. **Una `ir.rule` es GLOBAL si y solo si NO tiene grupos.** El campo `global` es **CALCULADO y de SOLO LECTURA** (`global = not groups_id`); NO es un campo que se escriba.
- `global` — **campo calculado, read-only.** Deriva de `groups`. No se declara a mano.

> 🚫 **PROHIBIDO en todo el corpus: `<field name="global" eval="True"/>`.** Al ser `global` un campo calculado de solo lectura, ese `eval` **se ignora silenciosamente** (no hace absolutamente nada) y la regla, si además tiene grupos, acabaría como **regla de grupo esquivable** (OR) en vez de global (AND) — justo lo contrario de lo que se pretende. **La forma canónica y ÚNICA de crear una regla global es dejar `groups` vacío**: `<field name="groups" eval="[]"/>`. El campo `global` se recalcula solo a `True`. Nunca lo fuerces.
- `domain_force` — texto, evaluado con `safe_eval`. El dominio que deben cumplir los registros.
- `perm_read`, `perm_write`, `perm_create`, `perm_unlink` — a qué operaciones se aplica la regla. **Al menos uno debe estar marcado** (constraint).

### 4.2 Global vs de grupo, y su combinación (lo más importante)

Del método `_compute_domain` (fuente):

- **Reglas GLOBALES (sin grupos) → se combinan con AND.** Todas deben cumplirse; cada una puede tumbar el acceso. **No se pueden esquivar** metiendo al usuario en otro grupo.
- **Reglas de GRUPO → se combinan con OR** entre sí. Basta que **una** de las reglas de los grupos del usuario se cumpla.
- Resultado final:

```
dominio_efectivo = AND(todas_las_globales) AND ( OR(reglas_de_los_grupos_del_usuario) )
```

Docstring literal: *"local rules are OR-ed together, the entire group succeeds or fails, while global rules get AND-ed and can each fail"*.

Una regla solo se aplica a una operación si su `perm_X = True`. Para **bloquear** write/unlink pones `perm_write=True` / `perm_unlink=True` con un dominio que NO se cumpla para los registros protegidos.

> ✅ **`perm_write` cubre CUALQUIER escritura, no solo renombrar.** Un bloqueo de `perm_write` sobre un maestro impide también **archivar** el registro (`active=False`), **cambiar su tipo** (`type`), tocar `sale_ok`/`purchase_ok`, o modificar cualquier otro campo — todo eso son `write`. Es decir: para blindar el producto de servicio "Horas" o la UdM "Horas" no hace falta enumerar campos; con `perm_write=True` + dominio falso queda protegido frente a renombrado, archivado y cambio de tipo/flags de una vez. El `unlink` (borrado físico) se cubre aparte con `perm_unlink`.

> ⚠️ Las record rules filtran **dentro** de lo que la ACL ya permite; no conceden nada por sí solas. Si un grupo no tiene ACL de `write` sobre un modelo, ninguna record rule "permisiva" le dará `write`.

### 4.3 Contexto de evaluación del dominio (`_eval_context`)

Odoo inyecta estas variables en `domain_force`:

| Variable | Valor | Uso típico |
|---|---|---|
| `user` | `res.users` actual (contexto vacío) | `user.has_group('xmlid')`, `user.id` |
| `company_id` | `self.env.company.id` (la compañía **activa**, un entero) | rara vez para seguridad |
| `company_ids` | `self.env.companies.ids` (lista = las compañías **seleccionadas** en el selector) | **patrón multiempresa** |
| `time` | módulo `time` | fechas |

> En dominios usa **`user.has_group('modulo.xmlid')`** en vez de `user.group_ids`; es estable frente al renombrado de campos de v19 y más legible.

> 🚫 **`ref()` NO EXISTE en el contexto de `domain_force`.** El `_eval_context` de `ir.rule` inyecta **solo** `user`, `time`, `company_id`, `company_ids` (y `env` a través de `user.env`). **NO** incluye la función `ref`. Escribir `ref('modulo.xmlid')` dentro de un `domain_force` provoca un **`NameError` EN RUNTIME** cuando la regla se evalúa (no en la instalación). Es un bug silencioso hasta que un usuario toca el modelo.
>
> **Forma correcta** de referenciar un registro por xmlid dentro de `domain_force`:
>
> ```python
> # CORRECTO — resuelve el xmlid en tiempo de evaluación vía el env del usuario:
> [('id', '!=', user.env.ref('modulo.xmlid').id)]
>
> # INCORRECTO — NameError en runtime, ref no está en el contexto:
> [('id', '!=', ref('modulo.xmlid'))]
> ```
>
> Ojo con los registros que existen **por compañía** (p. ej. el producto de servicio "Horas", con ids DISTINTOS en PRE y en PRO): resuelve los ids en cada BD y usa `[('id','not in',[id1,id2,...])]` con **LISTA** (no `!=` contra un solo id), o `user.env.ref(...).id` si tienen external id estable, o un `post_init_hook` que los localice y les cree su external id. **Nunca** un `ref()` suelto en el dominio.

### 4.4 Ejemplo: multiempresa (patrón canónico)

Es el patrón que usan TODAS las reglas nativas de compañía. Aísla AUNNA / CITRIC / MONTOYA / ii. **Se hace global dejando `groups` vacío:**

```xml
<record id="rule_mimodelo_multicompany" model="ir.rule">
    <field name="name">MiModelo multi-company</field>
    <field name="model_id" ref="model_mi_modelo"/>
    <field name="groups" eval="[]"/>   <!-- sin grupos = GLOBAL = AND, no se esquiva -->
    <field name="domain_force">
        ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
    </field>
</record>
```

Lectura: "ve el registro si **no tiene compañía** (dato compartido, p. ej. producto/UdM globales) **o** si su compañía está entre las **seleccionadas**". Detalle real del proyecto: la fuga de la cuenta 90 en CITRIC vino de que el usuario tenía AUNNA activa; el aislamiento fuerte se logra **no dando compañías de más en `company_ids`** (limitar `res.users.company_ids` a lo estrictamente necesario) + este patrón + `base.group_multi_company` solo a quien deba conmutar de empresa. Ver [[05-record-rules-multiempresa]].

### 4.5 Ejemplo: blindar un dato maestro con record rule (anti-incidente)

Hay **dos modelos operativos** distintos. Elige uno a conciencia; no los mezcles sobre el mismo modelo sin entender la combinación AND/OR.

**Modelo A — máximo blindaje (solo el superusuario uid 1 mantiene el dato).**
Una regla **global** con dominio siempre falso sobre `uom.uom`. Al ser global va en AND y **no se esquiva con ningún grupo**; y como el superusuario real (uid 1) ignora las rules, el mantenimiento se hace por un procedimiento controlado (odoo shell / impersonación de root con doble control). **Ojo:** esto también bloquea al grupo custodio si el custodio NO es uid 1. Es el candado más duro.

```xml
<record id="uom_lock_all_rule" model="ir.rule">
    <field name="name">UdM: nadie salvo el superusuario (uid 1) crea/modifica/borra</field>
    <field name="model_id" ref="uom.model_uom_uom"/>
    <field name="domain_force">[(0, '=', 1)]</field>   <!-- dominio SIEMPRE falso -->
    <field name="groups" eval="[]"/>                   <!-- GLOBAL (AND) -->
    <field name="perm_read"   eval="False"/>           <!-- NO restringe lectura: los partes necesitan leer la UdM -->
    <field name="perm_create" eval="True"/>
    <field name="perm_write"  eval="True"/>
    <field name="perm_unlink" eval="True"/>
</record>
```

> ⚠️ **`perm_read` DEBE quedar en `False`.** `hr_timesheet`/`sale_timesheet` necesitan **leer** la UdM "Horas" y el producto de servicio en cada parte. Si pusieras `perm_read=True` con dominio falso, romperías los partes de horas para todos (justo el efecto del incidente, pero por permisos). Bloquea solo create/write/unlink.
> ⚠️ Prueba en PRE que **ninguna** automatización, cron o asistente legítimo necesite `write`/`create` sobre `uom.uom` como usuario normal (los que corren como superusuario no se ven afectados; ver §0).

**Modelo B — custodio funcional edita desde la UI (patrón de grupo, OR).**
Una regla de grupo bloquea a `base.group_user` (todos) y otra re-permite al custodio. Como las reglas de grupo van en OR, el custodio —que tiene ambos grupos— pasa por la permisiva.

```xml
<record id="uom_block_users" model="ir.rule">
    <field name="name">UdM: bloquear escritura/borrado a usuarios internos</field>
    <field name="model_id" ref="uom.model_uom_uom"/>
    <field name="domain_force">[(0, '=', 1)]</field>
    <field name="groups" eval="[(4, ref('base.group_user'))]"/>
    <field name="perm_read" eval="False"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_write" eval="True"/>
    <field name="perm_unlink" eval="True"/>
</record>
<record id="uom_allow_custodio" model="ir.rule">
    <field name="name">UdM: re-permitir al custodio</field>
    <field name="model_id" ref="uom.model_uom_uom"/>
    <field name="domain_force">[(1, '=', 1)]</field>   <!-- siempre verdadero -->
    <field name="groups" eval="[(4, ref('zambudio_permisos.group_master_data_custodian'))]"/>
    <field name="perm_read" eval="False"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_write" eval="True"/>
    <field name="perm_unlink" eval="True"/>
</record>
```

> ⚠️ **El Modelo B exige que el custodio tenga ACL de `write` sobre `uom.uom`** (línea `access_uom_uom_custodio_full` de §3.2); si no, la regla permisiva no sirve porque la ACL ya lo bloquea antes.
> ⚠️ **El Modelo B es más frágil**: si el custodio pertenece a **otro** grupo con una regla permisiva sobre `uom.uom`, el OR también le abriría a ESE otro grupo. Y el bloqueo a `base.group_user` solo muerde si algún grupo del usuario le daba `write` vía ACL; si ya no hay ACL de `write` para grupos amplios (recomendado), estas reglas son un backstop. Para los maestros más críticos (UdM, categoría UdM `uom.category`, producto "Horas") se prefiere el **Modelo A** + custodio actuando como uid 1 en procedimiento controlado. El diseño completo va en [[04-blindaje-datos-maestros]].

### 4.6 Lo que las record rules NO hacen

- **NO filtran escritura cruzada de compañías dentro de un registro** — para eso está `check_company=True` en los campos relacionales (ver [[05-record-rules-multiempresa]]).
- **NO aplican al superusuario** (`env.su`, uid 1) **ni al código en `sudo()`, acciones de servidor o automatizaciones** (§0). De ahí la importancia de la custodia del root y de gobernar quién crea automatizaciones ([[00-principios-y-gobernanza]]).
- `noupdate="1"` en `ir.model.data` solo evita que un **upgrade de módulo** repise el registro; **no** impide que un usuario con permiso lo edite en la UI. `uom.product_uom_hour` ya es `noupdate="1"` y aun así el admin lo rompió.

---

## 5. Seguridad a nivel de CAMPO: `groups=`

Hay dos sitios donde aparece `groups=` y **hacen cosas MUY distintas**:

| Dónde | Qué es | ¿Seguridad real? |
|---|---|---|
| En la **definición del field Python**: `fields.Char(..., groups='modulo.xmlid')` | El ORM **elimina el campo** de lectura/escritura para quien no esté en el grupo. No aparece **ni por RPC/API**. Aplica también a campos calculados. | **SÍ, seguridad real.** |
| En la **vista**: `<field name="x" groups="modulo.xmlid"/>` | Solo oculta el campo en la **UI**. Sigue siendo accesible por RPC/API si el ACL lo permite. | **NO. Solo visibilidad.** La doc lo remarca: *"Visibility != security"*. |

### 5.1 Ejemplo — blindaje real de un campo maestro

`groups=` en el **field** protege de verdad; en la vista solo esconde. Ojo con una limitación importante:

```python
# En un módulo que herede el modelo
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    # Campo NUEVO sensible, visible/editable solo por el custodio: OK
    x_precio_coste_sensible = fields.Float(
        groups='zambudio_permisos.group_master_data_custodian')
```

```xml
<!-- En vista: SOLO oculta en UI, NO protege por RPC -->
<field name="name" groups="zambudio_permisos.group_master_data_custodian"/>
```

> ⚠️ **No abuses de `groups=` sobre campos NATIVOS críticos de uso general.** Poner `groups=` en un field como `product.template.name` o `uom.uom.name` haría que ese campo **desapareciera por completo** (lectura incluida) para todos los que no sean custodios, rompiendo vistas, informes, partes de horas y búsquedas. Para el `name` de un maestro que todos deben **leer** pero nadie debe **renombrar**, la protección correcta es **ACL sin `write` + record rule** (§4.5), NO `groups=` en el field. `groups=` en el field es ideal para **campos nuevos** verdaderamente sensibles, no para ocultar el nombre de un producto de uso diario.

Conclusión operativa: para blindar un dato maestro de uso general, combina **ACL (sin write para grupos amplios) + record rule**; reserva `groups=` en el field para campos nuevos sensibles. La `groups=` en la vista es solo cosmética.

---

## 6. Visibilidad de menús, acciones y vistas

- `ir.ui.menu` tiene el campo de grupos **`group_ids`** (en v19; era `groups_id` — **verificar el nombre exacto en PRE** tras el renombrado). Si el usuario no está en ninguno de esos grupos, **no ve el menú**. Si un menú padre no tiene ningún hijo visible ni acceso al modelo destino, se oculta también.
- Las **acciones** (`ir.actions.*`) y **vistas** (`ir.ui.view`, vía `group_ids` / `view_access`) también se filtran por grupo.
- Esto es **control de UI**, NO seguridad de fondo. La seguridad la dan ACL + record rules. Ocultar un menú no impide el acceso por RPC/import/Studio si el ACL lo permite — exactamente por eso ocultar el menú de UdM **no** habría evitado el incidente.

---

## 7. Grupos base del sistema (`base_groups.xml`) — xmlids verificados

> Los **xmlids** están verificados contra la rama 19.0. Los **nombres visibles** cambiaron en v19 (esquema "Role / …"); los marco como orientativos porque las cadenas exactas conviene confirmarlas en PRE.

| xmlid | Nombre en v19 (orientativo) | Qué da / relaciones |
|---|---|---|
| `base.group_user` | "Role / User" (antes "Internal User") | Empleado interno base. Disjunto con portal/public. Lo llevan TODOS los internos. |
| `base.group_system` | "Role / Administrator" (antes "Settings") | Acceso a **Ajustes**, instalar/activar apps, menús técnicos, editar maestros de sistema, Studio/base_automation. **El "Administrador" del incidente.** `implied_ids` incluye `group_erp_manager` y `group_sanitize_override` **(verificar la lista exacta en PRE)**. |
| `base.group_erp_manager` | "Access Rights" | Crear/editar usuarios y asignar grupos. Implica `group_user`. |
| `base.group_no_one` | "Technical Features" (dev mode) | Asignado implícitamente a todos (implicado por `group_user` y `group_system`); los menús/campos marcados con él **solo se ven en modo desarrollador**. |
| `base.group_multi_company` | "Multi Companies" | Activa el **selector** de compañía. Solo perfiles que deban conmutar (p. ej. AUNNA+CITRIC). |
| `base.group_multi_currency` | "Multi Currencies" | Multimoneda. |
| `base.group_partner_manager` | "Creation" (contactos) | Alta de contactos. `privilege_id = res_groups_privilege_contact` **(verificar en PRE)**. Implicado por `group_system`. |
| `base.group_allow_export` | "Allowed" (exportar) | Permite el botón Exportar. `privilege_id = res_groups_privilege_export` **(verificar en PRE)**. Limitarlo reduce exfiltración masiva de datos. |
| `base.group_sanitize_override` | "Bypass HTML Field Sanitize" | Implicado por `group_system`. |
| `base.group_portal` | "Role / Portal" | Cliente de portal. Disjunto de internos. **Nunca** lleva `base.group_user`. |
| `base.group_public` | "Role / Public" | Usuario web anónimo. Disjunto. |

Jerarquía real de administración:

```
base.group_system  ⊃  base.group_erp_manager  ⊃  base.group_user
```

### 7.1 Los dos "admin" que hay que separar (clave del incidente)

- **`base.group_system` ("Role / Administrator") es CUSTODIA, no un rol de trabajo.** Da Ajustes y, con ello, capacidad de tocar datos maestros de sistema (UdM, producto de servicio, secuencias, monedas) y de crear automatizaciones. El incidente = dar `group_system` (o CRUD amplio sobre `product.template`/`uom.uom`) a un perfil funcional. **Ningún perfil funcional debe llevarlo.** Administración/Contabilidad **no lo necesitan** para su día a día.
- **`base.group_erp_manager` ("Access Rights")** = gestor de usuarios delegado, sin el resto de Ajustes. Opcional. **Ojo:** quien pueda asignar grupos puede auto-concederse `group_system`; trátalo también como rol sensible.
- Detalle v19 a comunicar a los usuarios: los nombres cambiaron ("Role / Administrator", "Role / User"), para no confundir con versiones anteriores.

### 7.2 Developer mode / `base.group_no_one`

- Activar el **modo desarrollador** NO da permisos de datos extra por sí mismo (todos ya tienen `group_no_one` implícito). Lo que hace es **desvelar** menús/campos técnicos en la UI.
- El peligro real: un usuario con `base.group_system` + modo desarrollador **ve y puede tocar** menús técnicos (UdM, secuencias, `ir.rule`, `base.automation`…). Por eso el control efectivo es **no dar `group_system`**, no "esconder el modo dev".

### 7.3 Quitar "Ajustes" sin romper el trabajo diario

- El acceso al menú **Ajustes** lo da `base.group_system`. Quitarlo retira Ajustes y la configuración de apps, **pero conserva el trabajo diario** si el usuario mantiene sus grupos funcionales (`sales_team.group_sale_salesman`, `account.group_account_user`, `stock.group_stock_user`, `hr_timesheet.group_hr_timesheet_user`, etc.).
- **Verificar en PRE** qué menús concretos desaparecen: algunas acciones de configuración puntuales cuelgan de `group_erp_manager` y no de `group_system`.
- Efecto colateral positivo (Enterprise): sin `group_system`, el usuario **no ve Apps ni el store** — no puede instalar/desinstalar módulos.

---

## 8. Tabla de xmlids estándar más usados por app

> xmlids del núcleo referidos a la rama 19.0. Los marcados **(verificar en PRE)** son Enterprise o de menos certeza: confirmar el xmlid y el nombre exacto antes de referenciarlos en código.

### Base / sistema
| xmlid | Nombre |
|---|---|
| `base.group_user` | Role / User |
| `base.group_system` | Role / Administrator (Ajustes) |
| `base.group_erp_manager` | Access Rights |
| `base.group_no_one` | Technical Features (dev mode) |
| `base.group_multi_company` | Multi Companies |
| `base.group_multi_currency` | Multi Currencies |
| `base.group_partner_manager` | Alta de contactos |
| `base.group_allow_export` | Permitir exportar |

### Ventas / CRM (grupos en `sales_team`, privilege de ventas)
| xmlid | Nombre |
|---|---|
| `sales_team.group_sale_salesman` | User: Own Documents Only |
| `sales_team.group_sale_salesman_all_leads` | User: All Documents |
| `sales_team.group_sale_manager` | Administrator (**usar este xmlid**; `sale.group_sale_manager` suele ser alias/heredado — verificar en PRE) |

### Contabilidad (`account`)
| xmlid | Nombre |
|---|---|
| `account.group_account_invoice` | Invoicing |
| `account.group_account_readonly` | Show Accounting Features - Readonly |
| `account.group_account_basic` | Basic **(verificar en PRE)** |
| `account.group_account_user` | Show Full Accounting Features (contable real) |
| `account.group_account_manager` | Administrator (Adviser/Billing) |
| `account.group_account_secured` | Show Inalterability Features **(verificar en PRE)** |
| `account.group_validate_bank_account` | Validar cuenta bancaria **(verificar en PRE)** |

### Analítica
| xmlid | Nombre |
|---|---|
| `analytic.group_analytic_accounting` | Analytic Accounting |

### Inventario (`stock`)
| xmlid | Nombre |
|---|---|
| `stock.group_stock_user` | User |
| `stock.group_stock_manager` | Administrator |
| `stock.group_stock_multi_locations` | Ubicaciones múltiples |
| `stock.group_stock_multi_warehouses` | Almacenes múltiples |
| `stock.group_production_lot` | Lotes/nº de serie |
| `stock.group_adv_location` | Rutas avanzadas |

### Compra (`purchase`)
| xmlid | Nombre |
|---|---|
| `purchase.group_purchase_user` | User |
| `purchase.group_purchase_manager` | Administrator |
| `purchase.group_warning_purchase` | Avisos |

### Fabricación (`mrp`)
| xmlid | Nombre |
|---|---|
| `mrp.group_mrp_user` | User (implica `stock.group_stock_user`) |
| `mrp.group_mrp_manager` | Administrator |
| `mrp.group_mrp_routings` | Rutas/operaciones |

### Empleados (`hr`)
| xmlid | Nombre |
|---|---|
| `hr.group_hr_user` | Officer: Manage all employees |
| `hr.group_hr_manager` | Administrator |

### Partes de horas (`hr_timesheet`)
| xmlid | Nombre |
|---|---|
| `hr_timesheet.group_hr_timesheet_user` | User: own timesheets only (**usado ya en el repo**) |
| `hr_timesheet.group_hr_timesheet_approver` | User: all timesheets |
| `hr_timesheet.group_timesheet_manager` | Administrator |

### Proyecto (`project`)
| xmlid | Nombre |
|---|---|
| `project.group_project_user` | User |
| `project.group_project_manager` | Administrator |
| `project.group_project_stages` | Etapas **(verificar en PRE)** |
| `project.group_project_milestone` | Hitos **(verificar en PRE)** |

### Otras apps (verificar xmlid y nombre exactos en PRE — varias Enterprise)
| xmlid | Nombre |
|---|---|
| `hr_holidays.group_hr_holidays_user` / `_responsible` / `_manager` | Ausencias **(verificar en PRE)** |
| `hr_expense.group_hr_expense_team_approver` / `_user` / `_manager` | Gastos **(verificar en PRE)** |
| `hr_appraisal.*` | Evaluación **(verificar en PRE)** |
| `hr_attendance.*` | Asistencias **(verificar en PRE)** |
| `planning.group_planning_user` / `_manager` | Planificación **(verificar en PRE)** |
| `helpdesk.group_helpdesk_user` / `_manager` | Helpdesk **(verificar en PRE)** |
| `repair.group_repair_user` | Taller **(verificar en PRE)** |
| `documents.group_documents_user` / `_manager` | Documentos **(verificar en PRE)** |
| `website.group_website_restricted_editor` / `group_website_designer` | Sitio web **(verificar en PRE)** |
| `approvals.*`, `im_livechat.*`, `stock_barcode.*` | Aprobaciones / Chat en vivo / Código de barras **(verificar en PRE)** |

### Datos maestros técnicos
| xmlid | Nombre |
|---|---|
| `uom.group_uom` | Manage Multiple Units of Measure (activa la *función* UdM; NO controla el borrado, solo la disponibilidad de la función) |
| `product.group_product_manager` | Create (crear/renombrar productos; implicado por `group_system`) |
| `product.group_product_variant` | Variantes |
| `product.group_product_pricelist` | Tarifas |

> ⚠️ **`uom.group_uom` NO protege la UdM.** Es la función "múltiples unidades de medida"; quitarla no impide renombrar/borrar `uom.uom` a quien tenga `write` por otra vía. El blindaje va por ACL + record rule (§4.5).

---

## 9. Cómo LEER qué grupos tiene un usuario

### 9.1 Desde la UI

1. **Ajustes → Usuarios y compañías → Usuarios** → abrir el usuario. Cada app muestra el privilege con su selector.
2. Para ver TODO (incluidos implicados y técnicos): activar **modo desarrollador** y abrir el usuario; aparecen las pestañas técnicas y la lista completa de grupos.
3. **Ajustes → Usuarios y compañías → Grupos** → abrir un grupo → pestañas **Users / Inherited (Implied) / Menus / Access Rights / Record Rules**: es la forma más rápida de ver qué concede un grupo y quién lo tiene.

### 9.2 Comprobación programática (la fiable)

En v19 el campo en `res.users` es **`group_ids`** y **`all_group_ids`** (el clásico `groups_id` de v17/18 fue **renombrado**). Para dominios y comprobaciones, **usar preferentemente `user.has_group('xmlid')`** en vez de referenciar el campo directamente:

```python
# En un shell odoo (odoo-bin shell) o server action — SOLO LECTURA
u = env['res.users'].browse(52)          # p. ej. uid 52
u.has_group('base.group_system')         # True/False
u.all_group_ids.mapped('full_name')      # lista completa incl. implicados
```

> ⚠️ **Aviso v19 (verificar en PRE):** cualquier record rule, vista o dominio custom que use `user.groups_id` debe migrarse a `group_ids`/`all_group_ids` o, mejor, a `user.has_group(...)`.

### 9.3 Query SQL de auditoría (solo lectura, segura)

Quién tiene los grupos peligrosos (`group_system`, `group_erp_manager`):

```sql
SELECT u.login, g.name, gp.name AS privilege
FROM res_groups_users_rel r
JOIN res_users u  ON u.id = r.uid
JOIN res_groups g ON g.id = r.gid
LEFT JOIN res_groups_privilege gp ON gp.id = g.privilege_id
WHERE g.id IN (
    SELECT res_id FROM ir_model_data
    WHERE module='base' AND name IN ('group_system','group_erp_manager')
)
ORDER BY u.login;
```

Inventario de record rules de compañía (para auditar aislamiento multiempresa):

```sql
SELECT r.id, m.model, r.name, r.domain_force, r."global"
FROM ir_rule r JOIN ir_model m ON m.id = r.model_id
WHERE r.domain_force ILIKE '%company_id%'
ORDER BY m.model;
```

> Nota: la columna se llama `global`, que es palabra reservada en varios contextos SQL; se cita como `r."global"` para evitar sorpresas del parser.

---

## 10. Depurar "¿por qué este usuario VE / NO VE X?"

Procedimiento ordenado (hazlo **en PRE** con una copia del usuario real):

### 10.1 "No VE un menú / una acción"
1. ¿El **menú** (`ir.ui.menu.group_ids` en v19 — verificar nombre) exige un grupo que el usuario no tiene? → mirar el menú en modo dev.
2. ¿Tiene **ACL de lectura** (`perm_read`) sobre el modelo destino? Sin read, aunque vea el menú, la acción falla o el menú se auto-oculta.
3. ¿Alguna **record rule** con dominio le deja 0 filas? (p. ej. multiempresa sin la compañía seleccionada en el selector).

### 10.2 "No PUEDE escribir / borrar X"
1. **Capa ACL:** ¿algún grupo suyo concede `perm_write`/`perm_unlink` sobre el modelo? Recuerda: se suman. Si ninguno lo da → bloqueado aquí.
2. **Capa record rule:** ¿hay una regla **global** (AND) con `perm_write/unlink=True` cuyo dominio NO cumplan esos registros? Una global no se sortea con grupos. (Este es el mecanismo de blindaje de maestros.)
3. **Capa campo:** ¿el campo concreto tiene `groups=` en su definición Python que excluya al usuario? El ORM lo elimina para él.
4. **`check_company`:** ¿el error es "deben pertenecer a la misma compañía"? Entonces NO es permisos, es la constraint `_check_company` sobre campos `check_company=True` (ver [[05-record-rules-multiempresa]]).
5. **Lock dates contables:** si es un asiento por fecha, puede ser `fiscalyear_lock_date` / `hard_lock_date`, no permisos.

### 10.3 "SÍ puede y NO debería" (el caso del incidente)
1. ¿Está en `base.group_system`? → casi siempre la causa. Quitarlo (dejar solo grupos funcionales).
2. ¿Algún grupo funcional concede `write` sobre el maestro (p. ej. `product.group_product_manager`, o grupos de `stock`/`sales` sobre `product.template`)? → retirar ese `write` de la ACL del grupo amplio y/o añadir record rule global restrictiva (§4.5). No confiar solo en ocultar menús.
3. ¿Lo hizo una **automatización / acción de servidor / Studio**? → corre con privilegios y **se salta las rules**; revisar el catálogo de automatizaciones (§0, [[00-principios-y-gobernanza]]).
4. ¿Es el **superusuario** (uid 1)? → las rules no le aplican; esto es esperado. Controlar la custodia del root ([[00-principios-y-gobernanza]]).

### 10.4 Herramientas de apoyo
- **Modo desarrollador → menú "Ver metadatos" / "Ver Access Rights"** en un registro: muestra rules y accesos aplicables.
- **Ajustes → Técnico → Seguridad → Record Rules / Access Rights**: filtrar por modelo para ver todo lo que aplica.
- **`odoo-bin shell`** con `env['ir.rule']._compute_domain(model_name, 'write')` (avanzado) para ver el dominio efectivo — **solo en PRE**.

---

## 11. Resumen operativo (lo que hay que retener)

1. **Tres capas, todas deben pasar:** grupo (menú) → `ir.model.access` (verbo) → `ir.rule` (alcance).
2. **v19:** el grupo cuelga de `privilege_id → res.groups.privilege → category_id`, NO del `category_id` directo. Los campos de grupos se renombraron: `res.users.group_ids`/`all_group_ids`, `res.groups.user_ids`, y el `groups_id → group_ids` de menús/vistas/acciones. Preferir `has_group()`.
3. **Los ACL SUMAN (OR): no restan.** Para quitar un permiso peligroso → **retirar `write` de la ACL del grupo amplio** + record rule **global** (AND, inesquivable). `groups=` en el field solo para campos nuevos sensibles.
4. **`groups=` en el field = seguridad real; en la vista = solo cosmética.** No lo pongas sobre el `name` de un maestro de uso diario (lo haría desaparecer para todos).
5. **`base.group_system` es custodia, no rol de trabajo** — raíz del incidente. Ningún funcional debe llevarlo. `base.group_erp_manager` también es sensible (permite auto-concederse grupos).
6. **El superusuario (uid 1) ignora las record rules; y también las ignora `sudo()`, las acciones de servidor y las automatizaciones/Studio.** De ahí la custodia del root y el control de quién crea automatizaciones.
7. **Multiempresa** con regla global `['|',('company_id','=',False),('company_id','in',company_ids)]` (groups vacío); limita `res.users.company_ids` a lo justo y da `base.group_multi_company` solo a quien deba conmutar; la escritura cruzada se frena con `check_company=True`.
8. **Blindar un maestro de uso general (UdM "Horas", producto de servicio):** las rules deben dejar `perm_read=False` para no romper los partes de horas; bloquea solo create/write/unlink.
9. **Todo cambio de seguridad: PRIMERO EN PRE.** Haz backup antes de tocar maestros en PRO. Confirma los xmlids marcados **(verificar en PRE)** antes de referenciarlos en código.

Continúa en [[02-catalogo-de-roles]] (diseño rol→grupos y SoD), [[04-blindaje-datos-maestros]] (XML copiables del blindaje UdM/producto Horas), [[05-record-rules-multiempresa]] (aislamiento AUNNA/CITRIC y `check_company`), [[07-auditoria-trazabilidad-hardening]] (auditlog, 2FA, sesiones, restricción de exportación) y [[00-principios-y-gobernanza]] (custodia del superadmin, control de automatizaciones, doble control).