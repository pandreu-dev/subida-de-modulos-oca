# RUNBOOK — Migrar los 5 maestros de Studio a código en PRODUCCIÓN

> Módulo: **`zambudio_master_data`** · Probado y validado en PRE el 2026-08-17
> (los 5 modelos quedaron `state=base` + propiedad del módulo, **huella de datos
> idéntica antes/después = cero pérdida**). Este runbook es la receta EXACTA para
> repetirlo en PRO sin fallos, con todas las trampas que ya nos comimos en PRE.

---

## 0. Qué hace (y qué NO hace)

- **Adopta** como código propio los 5 maestros que creó Odoo Studio:
  `x_tipo_empleado`, `x_subtipo_empleado`, `x_tipo_de_personal`, `x_sector`, `x_crm_practica`.
- Es **cirugía de METADATOS**: solo cambia `ir_model.state` a `base` y añade un
  `ir_model_data` propio (propiedad). **NO toca ni una columna de datos** (mismos ids,
  mismo jsonb de `x_name`, mismo selection). Por eso la huella de datos no cambia.
- **NO** migra los campos que REFERENCIAN estos maestros (los de `hr.employee` y
  `crm.lead`): esos siguen siendo de Studio y van en un bloque posterior.

### ⛔ Regla de oro
**NO desinstalar `studio_customization` después de esto.** Adoptar los maestros NO
protege los campos `x_studio_tipo_empleado_1` / `x_studio_subtipo_empleado` /
`x_studio_tipo_de_personal_1` (hr.employee) ni sector/práctica (crm.lead). Si se
desinstala Studio ahora, esas columnas y su contenido se borran. Studio se retira solo
al final, cuando TODO esté migrado.

---

## 1. Por qué funciona (breve)

Redefinir el modelo en código con el mismo `_name` **preserva los datos pero NO adopta
el modelo**: mientras `ir_model.state='manual'`, en cada arranque Odoo re-inyecta el
modelo como "custom" y la reflexión vuelve a escribir `manual`; además la propiedad
(`ir_model_data`) sigue siendo de `studio_customization`. La adopción rompe eso:

1. `UPDATE ir_model/ir_model_fields SET state='base'` (antes de la reflexión) → deja de
   re-inyectarse como manual → la reflexión lo reclama como código.
2. `INSERT` de un `ir_model_data` propio de `zambudio_master_data` por cada modelo/campo
   (sin borrar el de Studio) → por *reference-count*, sobrevive a un futuro uninstall de
   Studio.

El módulo lo hace **solo**:
- **Instalación nueva** (PRO) → `pre_init_hook` (corre antes de reflejar).
- **Actualización** (fue el caso de PRE) → `migrations/19.0.1.1.0/pre-migration.py`.

---

## 2. Trampas que YA nos comimos en PRE (evítalas en PRO)

| # | Síntoma | Causa | Solución (ya aplicada / a tener en cuenta) |
|---|---------|-------|---------------------------------------------|
| 1 | Instala pero los modelos siguen `manual` | Redefinir el `_name` no adopta | Hay que forzar `state=base` + propiedad (lo hace el hook/migración). |
| 2 | `-i` peta: *No matching record found for external id 'model_x_...'* | Permisos por `ir.model.access.csv` no resuelven en modelo adoptado | Permisos por `post_init_hook`, NO por CSV. **Ya hecho.** |
| 3 | `-u` peta: *Vista no disponible x_crm_practica.search* | `<group>` group_by en la search sobre el selection | Search mínima (field + filter). **Ya hecho.** |
| 4 | Al probar en copia: *relation "orm_signaling_registry"/"..._default" already exists* | El `pg_restore` con **`--no-owner`** deja las tablas de `postgres`; Odoo (rol limitado) no las "ve" e intenta recrearlas | Restaurar la copia **SIN `--no-owner`**. |
| 5 | El `-u` "no hace nada" / no corre la migración | El backup de prueba era ANTERIOR a instalar el módulo → en la copia no estaba instalado, y `-u` solo actualiza lo instalado | En PRO **es instalación nueva** → va con `-i` (y el `pre_init_hook` adopta). |
| 6 | Warning `aunna_portal_iframe_example` no cargado | Módulo de ejemplo sin deps (marcado NO PASAR) | **Inofensivo**, ignorar. |

---

## 3. Precondición en PRO (comprobar antes)

```bash
# ¿Está el módulo en PRO? (esperado: NO instalado, o 'uninstalled')
sudo -u postgres psql -d grupo_zambudio_prod -c "SELECT name,state,latest_version FROM ir_module_module WHERE name='zambudio_master_data';"
# ¿Existen los 5 maestros de Studio en PRO? (esperado: 5 filas, state=manual)
sudo -u postgres psql -d grupo_zambudio_prod -c "SELECT model,state FROM ir_model WHERE model IN ('x_tipo_empleado','x_subtipo_empleado','x_tipo_de_personal','x_sector','x_crm_practica') ORDER BY model;"
```
- Si `zambudio_master_data` sale **uninstalled / sin fila** → PRO es **instalación nueva**: se hace con `-i` (Sección 5).
- Si saliera ya **installed a una versión < 1.2.0** → sería **actualización**: cambia el `-i` por `-u` en la Sección 5 (el resto igual).

---

## 4. Backup fresco de PRO (obligatorio, justo antes)

Es la red de rollback definitiva (los datos no se mueven, así que restaurar el backup
revierte al 100 %).

```bash
cd /tmp
TS=$(date +%Y%m%d_%H%M%S)
sudo -u postgres pg_dump -Fc grupo_zambudio_prod -f /tmp/pro_pre_maestros_${TS}.dump
sudo mkdir -p /var/backups/odoo19_full/pre_restore
sudo mv /tmp/pro_pre_maestros_${TS}.dump /var/backups/odoo19_full/pre_restore/
sudo ls -lh /var/backups/odoo19_full/pre_restore/pro_pre_maestros_${TS}.dump
```
> Guarda ese nombre de fichero: es tu punto de retorno.

### Foto "ANTES" (huella de datos de PRO)
```bash
sudo -u postgres env PAGER=cat psql -d grupo_zambudio_prod -c "
SELECT 'x_tipo_empleado' t,count(*) n,md5(coalesce(string_agg(id||'|'||coalesce(x_name::text,'')||'|'||coalesce(x_active::text,'')||'|'||coalesce(x_studio_sequence::text,''),',' ORDER BY id),'')) h FROM x_tipo_empleado
UNION ALL SELECT 'x_subtipo_empleado',count(*),md5(coalesce(string_agg(id||'|'||coalesce(x_name::text,'')||'|'||coalesce(x_active::text,'')||'|'||coalesce(x_studio_sequence::text,''),',' ORDER BY id),'')) FROM x_subtipo_empleado
UNION ALL SELECT 'x_tipo_de_personal',count(*),md5(coalesce(string_agg(id||'|'||coalesce(x_name::text,'')||'|'||coalesce(x_active::text,'')||'|'||coalesce(x_studio_sequence::text,''),',' ORDER BY id),'')) FROM x_tipo_de_personal
UNION ALL SELECT 'x_sector',count(*),md5(coalesce(string_agg(id||'|'||coalesce(x_name::text,'')||'|'||coalesce(x_active::text,'')||'|'||coalesce(x_studio_sequence::text,''),',' ORDER BY id),'')) FROM x_sector
UNION ALL SELECT 'x_crm_practica',count(*),md5(coalesce(string_agg(id||'|'||coalesce(x_name::text,'')||'|'||coalesce(x_active::text,'')||'|'||coalesce(x_studio_sequence::text,'')||'|'||coalesce(x_studio_divisin,''),',' ORDER BY id),'')) FROM x_crm_practica;"
```
> Guarda esta salida. Al final debe ser **idéntica**. (Los conteos e incluso las huellas
> pueden diferir de PRE si en PRO hay más/menos registros — lo que importa es que
> **ANTES == DESPUÉS** en la propia PRO.)

---

## 5. Instalar en PRO (bajar código + `-i`)

```bash
# 1) Bajar el codigo (con Odoo parado, como en la doc de despliegue)
cd /tmp
sudo systemctl stop odoo19
sudo -u odoo19 git -C /opt/odoo19/addons/modules/subida-de-modulos-oca pull --ff-only
# Confirmar version y hooks desplegados:
grep -m1 version /opt/odoo19/addons/modules/subida-de-modulos-oca/zambudio_master_data/__manifest__.py   # 19.0.1.2.0

# 2) Instalar (el pre_init_hook adopta ANTES de reflejar)
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf -d grupo_zambudio_prod \
  -i zambudio_master_data --stop-after-init --logfile=/tmp/inst_pro.log

# 3) Arrancar y revisar log
sudo systemctl start odoo19
sudo grep -iE "zambudio_master_data|error|traceback|critical" /tmp/inst_pro.log | tail -n 40
```
> Si en la Sección 3 salió que **ya estaba instalado** a una versión anterior, cambia el
> `-i` por `-u` (todo lo demás igual).

---

## 6. Verificación (GO/NO-GO) — todo debe cumplirse

```bash
sudo -u postgres env PAGER=cat psql -d grupo_zambudio_prod <<'SQL'
-- (a) modulo instalado a 19.0.1.2.0
SELECT name,state,latest_version FROM ir_module_module WHERE name='zambudio_master_data';
-- (b) los 5 modelos en 'base'
SELECT model, state FROM ir_model WHERE model IN ('x_tipo_empleado','x_subtipo_empleado','x_tipo_de_personal','x_sector','x_crm_practica') ORDER BY model;
-- (c) supervivencia: protected='t' en TODAS (modelos y campos)
SELECT m.model AS obj, bool_or(d.module='zambudio_master_data') protected FROM ir_model m LEFT JOIN ir_model_data d ON d.model='ir.model' AND d.res_id=m.id WHERE m.model IN ('x_tipo_empleado','x_subtipo_empleado','x_tipo_de_personal','x_sector','x_crm_practica') GROUP BY m.model
UNION ALL
SELECT f.model||'.'||f.name, bool_or(d.module='zambudio_master_data') FROM ir_model_fields f LEFT JOIN ir_model_data d ON d.model='ir.model.fields' AND d.res_id=f.id WHERE f.model IN ('x_tipo_empleado','x_subtipo_empleado','x_tipo_de_personal','x_sector','x_crm_practica') AND f.name IN ('x_name','x_active','x_studio_sequence','x_studio_divisin') GROUP BY f.model,f.name;
SQL
```
Luego re-lanza la **huella** (misma query de la Sección 4) y compárala con la "ANTES".

**GO (todo verde):**
- (a) `installed`, `19.0.1.2.0`
- (b) los 5 en **`base`**
- (c) **`protected = t`** en las 21 filas (5 modelos + 16 campos)
- huella **idéntica** a la "ANTES"

Además, comprobación funcional en la interfaz: abrir un **empleado** (Tipo/Subtipo/Tipo de
personal correctos) y un **lead** (Sector/Práctica correctos); y las listas de los maestros
en **Ajustes → Técnico → Datos maestros configurables**.

**NO-GO:** si algo sale `manual`, `protected=f`, o la huella cambia → **restaurar el backup**
(Sección 7) y avisar. No dejar PRO a medias.

---

## 7. Rollback

Como la migración no mueve datos, el rollback definitivo es restaurar el backup fresco:
```bash
sudo systemctl stop odoo19
sudo -u postgres pg_restore --clean --if-exists -d grupo_zambudio_prod \
  /var/backups/odoo19_full/pre_restore/pro_pre_maestros_<TS>.dump
sudo systemctl start odoo19
```
(Confirmar el nombre exacto del `.dump` del paso 4.)

---

## 8. Cómo se PROBÓ primero en copia desechable (para replicar la garantía)

Antes de PRO, validar en un clon del backup de PRO (riesgo cero):
```bash
sudo -u postgres dropdb --if-exists gz_maestros_test
sudo -u postgres createdb gz_maestros_test
# OJO: SIN --no-owner (si no, Odoo no arranca contra la copia; ver trampa #4)
sudo -u postgres pg_restore -d gz_maestros_test /var/backups/odoo19_full/pre_restore/pro_pre_maestros_<TS>.dump
# instalar contra la copia (--no-http para no chocar con el servicio real)
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf -d gz_maestros_test -i zambudio_master_data --stop-after-init --no-http --logfile=/tmp/inst_copy.log
# verificar (Seccion 6) contra gz_maestros_test; si todo verde -> repetir en PRO real
sudo -u postgres dropdb gz_maestros_test   # limpiar
```

---

## 9. Después de PRO

- Dejar `studio_customization` **instalado** (⛔ regla de oro). NO borrar nada de Studio.
- Actualizar el control de migración (`de studio a cod/CONTROL_MIGRACION_STUDIO.md`) y el
  Excel: maestros = **HECHO en PRO**.
- Siguiente bloque: los **campos** de `hr.employee` y `crm.lead` que apuntan a estos
  maestros (misma técnica: `state=base` + xmlid propio). Ese bloque es imprescindible
  ANTES de poder plantear retirar `studio_customization`.
