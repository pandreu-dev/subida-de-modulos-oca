# Zambudio · Cierre mensual WIP (ingreso reconocido)

Da al **responsable de contabilidad** un botón **"Cerrar mes (WIP)"** que, con un
**selector de mes**, genera de golpe **un asiento de ingreso reconocido por cada
proyecto** con avance confirmado ese mes — sin entrar proyecto a proyecto y **sin
pasar por el presupuesto analítico**.

## Qué hace exactamente
Por cada proyecto con avance **confirmado** en el mes elegido:
1. Lee el importe de **`produccion.avance.mes.importe_confirmado`** (la app de Verónica;
   es el mismo dato que valida Laura en "Seguimiento económico").
2. Crea el **asiento WIP** — idéntico al de hoy: **Debe** *ingresos anticipados* /
   **Haber** *cuenta de ingreso (705)* con la **analítica del proyecto** — con fecha el
   **último día del mes**.
3. Crea la **reversión** el **día 1 del mes siguiente**.

Reutiliza el motor y la configuración contable de **`aunna_wip_accounting`** (diario,
cuentas, auto-post, reversión), así que cuadra con lo que ya se hacía.

## Dónde está
**Contabilidad → Asientos → "Cerrar mes (WIP)"** (grupo *Responsable de contabilidad*).
Elegir compañía + mes + año → *Cerrar mes y generar asientos* → abre la lista de los
asientos creados (con su reversión).

## Seguridad / idempotencia
- Solo el grupo `account.group_account_manager` (y `account_user` para pruebas).
- **No duplica**: marca los asientos (`x_zambudio_wip_close_*`); si se relanza el mismo
  mes, esos proyectos se **omiten**.
- Solo importes **positivos** (ingreso). Los costes de ese modelo van en negativo y se ignoran.

## Configuración previa (ya existe para el WIP actual)
En la compañía: diario WIP, cuenta de ingreso (705) y cuenta de ingresos anticipados
(Contabilidad → Ajustes → Avance).

## ⚠️ Pendiente de confirmar (1 cosa)
Los nombres de los campos de la app de Verónica están como **constantes** al principio de
`wizard/wip_month_close_wizard.py`:

```python
AVANCE_MODEL = "produccion.avance.mes"
F_PERIOD = "fecha_mes"            # día 1 del mes
F_AMOUNT = "importe_confirmado"
F_STATE = "estado"
STATE_CONFIRMED = "confirmado"
F_PROJECT = "project_id"
```
Confírmalos contra el código real en PRE (`find / -type d -name zambudio_produccion_real`
+ grep). Si alguno difiere, se cambia **en esa línea** y listo.

## Avisos operativos (de Verónica)
- Si un proyecto con producción **no aparece confirmado** ese mes → ejecutar antes
  *"Recalcular datos reales"* (o esperar al cron diario) y volver a cerrar.
- **LA TORRE** ene–abr están congelados a 0 (por cuándo se crearon los avances). Si deben
  ser otra cifra, corregir con el *asistente de carga inicial* **antes** del primer cierre real.

## Dependencias
`zambudio_produccion_real`, `aunna_wip_accounting`, `account`, `project`.
