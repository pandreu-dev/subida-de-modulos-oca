# 03 · Despliegue y actualización de módulos

## Concepto clave: código ≠ base de datos

- **`git pull`** en el servidor **solo baja el código** a la carpeta de addons.
- Para que Odoo aplique cambios de **campos, vistas, seguridad, datos XML o lógica
  instalada** hay que **actualizar el módulo** en la BD con **`-u nombre_modulo`**.
- Módulos **nuevos** (no instalados) → **`-i nombre_modulo`** o instalar desde la interfaz.

## Paso 1 · Bajar el código (git pull)

### PRE
```bash
cd /tmp
sudo systemctl stop odoo19_pruebas
sudo -u odoo19pruebas git -C /opt/odoo19_pruebas/addons/modules/subida-de-modulos-oca pull --ff-only
sudo systemctl start odoo19_pruebas
sudo systemctl status odoo19_pruebas --no-pager -l
```

### PRO
> ⚠️ **Toca producción y para Odoo.** Hacer backup antes (ver 04).
```bash
cd /tmp
REPO="/opt/odoo19/addons/modules/subida-de-modulos-oca"

echo "=== Comprobar repo antes ==="
sudo -u odoo19 git -C "$REPO" remote -v
sudo -u odoo19 git -C "$REPO" status -sb
sudo -u odoo19 git -C "$REPO" log --oneline -5

echo "=== Parar Odoo PRO ==="
sudo systemctl stop odoo19

echo "=== Pull ==="
sudo -u odoo19 git -C "$REPO" pull --ff-only

echo "=== Arrancar ==="
sudo systemctl start odoo19
sudo systemctl status odoo19 --no-pager -l

echo "=== Commit actual ==="
sudo -u odoo19 git -C "$REPO" log --oneline -5
```

## Paso 2 · Actualizar módulos en la BD (`-u`)

> ⚠️ Para Odoo, actualiza y vuelve a arrancar. Producción → avisar + backup previo.

**Ejemplo conservador (WIP):**
```bash
cd /tmp
sudo systemctl stop odoo19
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf \
  -d grupo_zambudio_prod \
  -u aunna_wip_accounting,aunna_wip_budget_calc \
  --stop-after-init
sudo systemctl start odoo19
sudo systemctl status odoo19 --no-pager -l
```

**Para PRE:** cambiar binario/usuario/conf/BD por los de `_pruebas`:
```bash
sudo -u odoo19pruebas /opt/odoo19_pruebas/venv/bin/python3 /opt/odoo19_pruebas/odoo/odoo-bin \
  -c /etc/odoo19_pruebas.conf -d grupo_zambudio_prod_pruebas \
  -u MODULO --stop-after-init
```

> **Alternativa por interfaz** (más simple para instalar/actualizar sueltos):
> `Ajustes > Aplicaciones` (modo desarrollador) → **Actualizar lista de aplicaciones** →
> buscar el módulo → **Instalar** / **Actualizar**. Odoo respeta las dependencias solo.

## Buenas prácticas
- Primero PRE, verificar, y luego PRO.
- Actualizar juntos los módulos que dependen entre sí (Odoo ordena por dependencias).
- Tras un `git pull`, si cambió un módulo **instalado**, casi siempre hace falta `-u`.
- Revisar el log tras arrancar: `sudo tail -n 120 /var/log/odoo19/odoo.log`.
