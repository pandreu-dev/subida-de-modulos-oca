# 04 · Backups y restauración (PRO)

| Recurso | Ruta |
|---------|------|
| Carpeta de backups | `/var/backups/odoo19_full` |
| Copias pre-restauración | `/var/backups/odoo19_full/pre_restore` |
| Script de backup | `/root/backup_odoo19_prod.sh` |
| Script de restore (original) | `/root/restore_odoo19_prod.sh` |
| Script de restore **corregido** | `/root/restore_odoo19_prod_FIXED2.sh` ✅ (el que funcionó) |
| Log de restore | `/var/log/odoo19/restore_odoo19_prod.log` |

El backup es un **zip nativo de Odoo**: `dump.sql` en la raíz + carpeta `filestore/`.

## Ver / crear / limpiar backups
```bash
# Listar
sudo find /var/backups/odoo19_full -maxdepth 1 -type f -name "grupo_zambudio_prod_*.zip" \
  -printf "%TY-%Tm-%Td %TH:%TM  %s bytes  %p\n" | sort
sudo ls -lh /var/backups/odoo19_full/pre_restore 2>/dev/null || true

# Crear backup nuevo
sudo /root/backup_odoo19_prod.sh
sudo tail -n 120 /var/log/odoo19/backup_odoo19_prod.log

# Borrar backups antiguos (¡destructivo, revisar antes!)
sudo find /var/backups/odoo19_full -maxdepth 1 -type f \
  \( -name "grupo_zambudio_prod_*.zip" -o -name "grupo_zambudio_prod_*.sha256" \) -print -delete
```

## 🔴 Restauración (SOBRESCRIBE la BD de producción)

> ⚠️ Restaurar **borra todo lo posterior al backup** y **para Odoo**. Confirmar con
> negocio. El script hace una **copia previa de emergencia** antes de sobrescribir.

### El bug del script original (resuelto)
El script original abortaba en la validación del ZIP por `set -o pipefail`:
```bash
unzip -l "$BACKUP_FILE" | grep -q "dump.sql"     # <- grep -q cierra el pipe;
unzip -l "$BACKUP_FILE" | grep -q "filestore/"   #    unzip recibe SIGPIPE (141);
```
Con miles de líneas de `filestore/`, `grep -q` corta la tubería, `unzip` sale **141** y
`pipefail` + `set -e` **abortan** el script (el trap solo levantaba Odoo). Por eso el log
moría en *"Comprobando dump.sql y filestore..."* y **no restauraba nada**.

### El arreglo (en `restore_odoo19_prod_FIXED2.sh`)
Volcar el listado a fichero y hacer `grep` **sin tubería**:
```bash
log "Comprobando dump.sql y filestore..."
ZIP_LIST="$(mktemp)"
unzip -Z1 "$BACKUP_FILE" > "$ZIP_LIST"
if ! grep -qx "dump.sql" "$ZIP_LIST"; then log "ERROR: falta dump.sql"; rm -f "$ZIP_LIST"; exit 1; fi
if ! grep -q "^filestore/" "$ZIP_LIST"; then log "ERROR: falta filestore/"; rm -f "$ZIP_LIST"; exit 1; fi
rm -f "$ZIP_LIST"
```
> Pendiente (opcional): incorporar este arreglo al `restore_odoo19_prod.sh` principal.

### Ejecutar restauración
```bash
cd /tmp
sudo /root/restore_odoo19_prod_FIXED2.sh /var/backups/odoo19_full/<backup>.zip
# Cuando pida confirmación, escribir EXACTAMENTE:
#   RESTORE grupo_zambudio_prod
```

### Verificar (no dar por hecho sin esto)
```bash
sudo tail -n 200 /var/log/odoo19/restore_odoo19_prod.log
sudo systemctl status odoo19 --no-pager -l
curl -I --max-time 20 http://127.0.0.1:8071/ || true
```
El log **debe** mostrar:
```
Parando odoo19...
Creando copia previa de emergencia antes de restaurar...
Restaurando backup sobre grupo_zambudio_prod...
OK: odoo19 esta activo.
Restauracion completada correctamente.
=== FIN RESTAURACION PRODUCCION ODOO 19 ===
```

## Historial
- **2026-07-21 07:58** — Restauración de `grupo_zambudio_prod_2026-07-20_070434.zip`
  ejecutada con éxito (script FIXED2). Copia previa:
  `pre_restore/grupo_zambudio_prod_ANTES_DE_RESTAURAR_2026-07-21_075707.zip`.
  Consecuencia: el despliegue del 20/07 se perdió → rehacer (ver 05).

## Inspeccionar un backup sin restaurar (BD temporal)
Útil para ver qué módulos/config tenía un backup:
```bash
cd /tmp
sudo rm -rf /tmp/inspect_gz && sudo mkdir -p /tmp/inspect_gz
sudo unzip -o /var/backups/odoo19_full/<backup>.zip -d /tmp/inspect_gz
sudo -u postgres dropdb --if-exists gz_inspect
sudo -u postgres createdb gz_inspect
sudo -u postgres psql -q gz_inspect < /tmp/inspect_gz/dump.sql
sudo -u postgres psql -d gz_inspect -c "SELECT name, latest_version FROM ir_module_module WHERE state='installed' AND (name LIKE 'zambudio_%' OR name LIKE 'aunna_%') ORDER BY name;"
sudo -u postgres dropdb gz_inspect   # limpiar al terminar
```
