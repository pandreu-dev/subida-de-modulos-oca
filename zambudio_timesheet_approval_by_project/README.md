# Zambudio - Aprobación de partes por responsable de proyecto

Hace que la validación de partes de horas funcione **como Odoo de serie** y **añade una
sola condición**: el **responsable del proyecto** puede validar los partes de **su**
proyecto (aunque no sea aprobador nativo de partes de horas).

> **Cambio ago-2026 (v19.0.5.0.0):** el módulo pasa de *restringir* la validación (antes
> solo el jefe de proyecto podía) a ser **aditivo**: ya **no restringe a nadie** —quien
> Odoo deja validar, valida— y **suma** que el jefe del proyecto también pueda con lo suyo.

## Qué hace

- **No cambia** el campo de validación (`account.analytic.line.validated`) ni añade menús:
  usa el **flujo nativo** de `timesheet_grid`.
- **Validación nativa intacta:** el aprobador del empleado y el Administrador de partes de
  horas validan como siempre (con sus permisos de Odoo de serie).
- **Condición añadida:** si el usuario es el **responsable del proyecto** (`project.user_id`)
  de un parte, puede **validarlo y des-validarlo**, aunque no tenga el rol de aprobador de
  partes. Se implementa con un override de `action_validate_timesheet` /
  `action_invalidate_timesheet` que valida ese subconjunto elevando privilegio solo para
  las líneas de sus proyectos; el resto se delega al flujo nativo.
- **Regla de acceso aditiva (solo lectura):** el responsable **ve** los partes de sus
  proyectos (necesario para poder abrirlos/validarlos). Es aditiva (OR): no quita acceso a
  nadie.
- **Vista "A validar" nativa:** al instalar/actualizar se **revierte** el filtrado por
  proyecto que añadían versiones anteriores, para que esa vista funcione como Odoo (cada
  usuario ve lo que su rol le permite). Idempotente.

## Configuración

- Cada **proyecto** debe tener su **Responsable** (`user_id`) informado (es quien podrá
  validar sus partes por esta condición añadida).
- El **rol de partes de horas** de cada usuario decide el resto, **como en Odoo**:
  - Si un jefe de proyecto tiene además **"Todos los partes de horas"** (aprobador), podrá
    validar **todos** los partes (comportamiento nativo), no solo los suyos.
  - Si **no** tiene ese rol, solo podrá validar los de **sus** proyectos (por la condición
    añadida de este módulo).

## Cómo probar

1. **Administrador de partes** (o aprobador): valida partes de cualquier proyecto → como
   Odoo, sin bloqueos del módulo.
2. **Jefe de proyecto SIN rol de aprobador**, responsable del proyecto X: puede **validar**
   los partes de X, y **no** los de otros proyectos.
3. Des-validar: mismo criterio (nativo + responsable del proyecto).

## Notas y límites

- La validación es **por línea** (cada parte tiene su proyecto): una semana de un empleado
  con varios proyectos la pueden validar sus respectivos responsables y/o los validadores
  nativos.
- Partes **sin proyecto**: los gestiona el flujo nativo, sin cambios.
- **Visibilidad del botón "Validar":** un jefe de proyecto necesita ver la acción de
  validar en su vista de Partes de horas; si en tu configuración el botón está oculto por
  no tener rol de partes, dáselo a nivel *usuario* de partes o usa la vista donde aparezca.
  Verificar en PRE.
- Historial: en `19.0.4.0.0` el módulo **restringía** la validación al responsable del
  proyecto; en `19.0.5.0.0` se invierte a **aditivo** (nativo + responsable del proyecto) y
  se revierte el filtrado de la vista "A validar".

**Depende de:** `timesheet_grid`, `project`.
