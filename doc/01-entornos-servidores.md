# 01 · Entornos y servidores

> No se incluyen contraseñas. Solo hosts, rutas, puertos y parámetros.

## 🟥 PRODUCCIÓN (PRO)

| Dato | Valor |
|------|-------|
| Dominio | https://erp.zambudio.es/ |
| IP | 51.91.126.132 |
| SO | Ubuntu 24.04 |
| Odoo | 19 Enterprise |
| Servicio systemd | `odoo19` |
| Usuario sistema | `odoo19` |
| Base de datos | `grupo_zambudio_prod` |
| Config | `/etc/odoo19.conf` |
| Ruta base | `/opt/odoo19` |
| Community | `/opt/odoo19/odoo` |
| Enterprise | `/opt/odoo19/enterprise` |
| Venv | `/opt/odoo19/venv` |
| Log | `/var/log/odoo19/odoo.log` |
| Puerto HTTP interno | **8071** |
| Puerto gevent/websocket | **8072** |

**Addons path (PRO):**
```
/opt/odoo19/enterprise,
/opt/odoo19/odoo/addons,
/opt/odoo19/addons/modules/subida-de-modulos-oca,
/opt/odoo19/addons/oca
```

**Parámetros de rendimiento (PRO):**
```
workers=4
limit_memory_soft=2147483648
limit_memory_hard=2684354560
limit_time_cpu=300
limit_time_real=600
proxy_mode=True      (esperado; ver 08 websocket)
gevent_port=8072     (esperado)
```

**Comprobar web local (PRO):**
```bash
curl -I --max-time 20 http://127.0.0.1:8071/ || true
```

---

## 🟩 PRE / PRUEBAS

| Dato | Valor |
|------|-------|
| Dominio | https://erp-pre.zambudio.es |
| Servicio systemd | `odoo19_pruebas` |
| Usuario sistema | `odoo19pruebas` |
| Base de datos | `grupo_zambudio_prod_pruebas` |
| Config | `/etc/odoo19_pruebas.conf` |
| Ruta base | `/opt/odoo19_pruebas` |
| Community | `/opt/odoo19_pruebas/odoo` |
| Enterprise | `/opt/odoo19_pruebas/enterprise` |
| Venv | `/opt/odoo19_pruebas/venv` |
| Log | `/var/log/odoo19_pruebas/odoo.log` |
| Puerto HTTP interno | **8074** |

**Addons path (PRE):**
```
/opt/odoo19_pruebas/enterprise,
/opt/odoo19_pruebas/odoo/addons,
/opt/odoo19_pruebas/addons/modules/subida-de-modulos-oca,
/opt/odoo19_pruebas/addons/oca
```

**Comprobar web local (PRE):**
```bash
curl -I --max-time 20 http://127.0.0.1:8074/ || true
```

---

## 🟦 ODOO 18 COMMUNITY (entorno aparte)

| Dato | Valor |
|------|-------|
| URL | http://odoo.aunnaitapp.es:8069 |
| IP | 176.31.163.180 |
| Usuario acceso | `odoo.aunnaitapp251` |
| Servicio | `odoo18` |
| Usuario sistema | `odoo18` |
| BD | `odoo18` |
| Config | `/etc/odoo18.conf` |
| Ruta | `/opt/odoo18` (código en `/opt/odoo18/odoo`) |
| Venv | `/opt/odoo18/venv` |
| Log | `/var/log/odoo18/odoo.log` |
| Puerto | 8069 |

⚠️ **Cuidado:** no mezclar módulos de Odoo 19 en el `addons_path` de Odoo 18 (rompe
assets / `partner_autocomplete`). Mantener los módulos v19 fuera de su addons path.

---

## Repositorio de módulos custom

Mismo repo Git en ambos entornos:

| Entorno | Ruta del repo |
|---------|---------------|
| PRO | `/opt/odoo19/addons/modules/subida-de-modulos-oca` |
| PRE | `/opt/odoo19_pruebas/addons/modules/subida-de-modulos-oca` |
| Local (dev) | `C:\Users\pandreu\Desktop\modulos_aunnna\new` (esta carpeta) |

El despliegue se hace por **git pull** en el servidor + **`-u`** de los módulos afectados.
Ver [03-despliegue-y-actualizacion.md](03-despliegue-y-actualizacion.md).
