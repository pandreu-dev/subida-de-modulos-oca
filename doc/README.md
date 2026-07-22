# Documentación operativa — Odoo 19 · Grupo Zambudio / Aunna IT

Contexto completo del proyecto para retomar el trabajo (o para otra persona/sesión):
entornos, servidores, módulos, despliegue, backups y desarrollos.

> ⚠️ **Interno.** Aquí **NO** se guardan contraseñas ni credenciales (van en un gestor de
> contraseñas). Solo hosts, rutas y procedimientos operativos.

**Última actualización:** 2026-07-22 · Consultor: Pablo Andreu Romera

---

## 📌 Estado actual (resumen rápido)

- **PRO se restauró el 2026-07-21** al backup `grupo_zambudio_prod_2026-07-20_070434.zip`
  (estado del 20/07 a las 07:04), usando el script corregido. El **despliegue que se hizo
  el 20/07 se perdió** con la restauración → hay que **rehacerlo** (ver
  [05-inventario-modulos.md](05-inventario-modulos.md) y
  [03-despliegue-y-actualizacion.md](03-despliegue-y-actualizacion.md)).
- La copia de seguridad previa a la restauración está en
  `/var/backups/odoo19_full/pre_restore/grupo_zambudio_prod_ANTES_DE_RESTAURAR_2026-07-21_075707.zip`
  (marcha atrás; **no borrar** unos días).
- **Módulos arreglados en local, pendientes de subir:**
  - `zambudio_project_sale_naming` → **v19.0.2.1.0** (arreglo del nombre de proyecto)
  - `zambudio_project_unique_name` → **v19.0.1.1.0** (deja pasar plantillas de proyecto)
  - `zambudio_project_billable` → **v19.0.1.4.0** (se **retiró** el "facturable por defecto")
- **Decisiones de negocio:**
  - `zambudio_project_billable`: **ya NO fuerza facturable por defecto** (Laura). Solo
    sincroniza y exige cliente si es facturable.
  - `aunna_project_cost_account_moves` (COSTE TH): **se deja SIN instalar** (Manuel).
  - `aunna_dynamic_standard_cost` (valorar inventario a último precio de compra):
    **descatalogado**, pendiente de decisión de administración.

---

## 🗂️ Índice

| Doc | Contenido |
|-----|-----------|
| [01-entornos-servidores.md](01-entornos-servidores.md) | PRO, PRE y Odoo 18: hosts, puertos, servicios, rutas, addons path, config |
| [02-operativa-comandos.md](02-operativa-comandos.md) | Comandos del día a día: estado, logs, reinicio, psql, websocket |
| [03-despliegue-y-actualizacion.md](03-despliegue-y-actualizacion.md) | `git pull` + `-u`, la diferencia código/BD, ejemplos |
| [04-backups-y-restauracion.md](04-backups-y-restauracion.md) | Backup y restauración, el bug del script y su arreglo |
| [05-inventario-modulos.md](05-inventario-modulos.md) | Lista de módulos, estado y qué hace cada uno + plan de re-despliegue |
| [06-contexto-wip-informe.md](06-contexto-wip-informe.md) | WIP, informe operativo financiero, P&L analítico |
| [07-multiempresa-citric.md](07-multiempresa-citric.md) | Multiempresa CITRIC, distribución analítica, partes de horas |
| [08-incidencias-conocidas.md](08-incidencias-conocidas.md) | ReportLab, festivos, SMTP, websocket, Odoo 18 |
| [09-desarrollos-y-peticiones.md](09-desarrollos-y-peticiones.md) | Desarrollos pedidos y su estado, app externa de horas, secuencias |

---

## 🛡️ Reglas de oro (leer antes de tocar PRO)

1. **En producción, ser conservador.** Ante la duda, no ejecutar.
2. **Antes de tocar módulos o restaurar → backup** (ver 04).
3. `git pull` **solo baja código**; NO actualiza los módulos en la BD. Para aplicar
   cambios reales → `-u modulo` (ver 03).
4. **Restaurar sobrescribe la BD actual** y se pierde lo posterior al backup. Avisar
   siempre y confirmar con negocio.
5. **No dar por hecha una restauración** solo porque el script se lanzó: hay que ver
   `=== FIN RESTAURACIÓN ===` en el log.
6. Si `systemctl` dice que Odoo sigue arrancado desde antes, **probablemente no se
   reinició/restauró**.
7. Comandos largos → empezar con `cd /tmp`.
8. En `psql`, usar `PAGER=cat` para que no se quede bloqueado en el paginador.
9. **Nunca** exponer contraseñas ni credenciales en chats, logs ni en estos docs.

## 🗣️ Estilo de trabajo que necesita Pablo

Respuestas en español, directas y operativas, con **comandos copiables**; avisar
claramente cuando algo **toca producción**, **para/reinicia Odoo** o **restaura BD**;
separar **diagnóstico → backup → ejecución → verificación**; no inventar sin datos; si hay
riesgo, decirlo; no meter comandos destructivos sin avisar.
