# Zambudio - Aprobación de partes por responsable de proyecto

Restringe la validación de partes de horas para que **solo el responsable del proyecto**
(o el aprobador designado del empleado) pueda validarlos — ni siquiera un Administrador
de partes puede validar los de proyectos ajenos.

## Qué resuelve

De serie, la validación de partes (`timesheet_grid`) es **por empleado**: valida el
aprobador del empleado o un Administrador de partes (que puede con TODOS). El negocio
necesita que cada **jefe de proyecto** valide solo lo imputado a **sus** proyectos.

## Cómo funciona

- **No cambia** el campo de validación (`account.analytic.line.validated`) ni añade
  menús: usa el **flujo nativo** de `timesheet_grid`, pero lo **restringe**.
- Un usuario solo puede **validar** y **des-validar** partes de proyectos de los que es
  **responsable** (`project.user_id`), o de empleados de los que es el **aprobador**
  (`hr.employee.timesheet_manager_id`). Se implementa con:
  - Override de `action_validate_timesheet` / `action_invalidate_timesheet`: filtra el
    conjunto a los partes autorizados antes de delegar en el método nativo.
  - `@api.constrains("validated")` de refuerzo para escrituras no-sudo (import/XML-RPC).
- **Vista "A validar" filtrada por proyecto:** en la instalación/actualización se añade
  `('project_id.user_id','=',uid)` al dominio de las acciones "A validar" → cada usuario
  ve ahí solo los partes de sus proyectos. Idempotente.
- **Válvula de escape** para datos huérfanos: si un proyecto no tiene responsable **y** el
  empleado no tiene aprobador, para no bloquear del todo la validación la puede hacer un
  **administrador de sistema** (`base.group_system`) — no el administrador de partes.
- **Regla de acceso aditiva** (solo lectura): deja que el responsable **vea** los partes
  de sus proyectos (necesario para verlos en "A validar"). Es aditiva (OR): no quita
  acceso a nadie.

## Configuración

- Dar a los **jefes de proyecto** el rol de **aprobador de partes de horas** (grupo
  estándar de partes), para que puedan usar la vista "A validar".
- Cada **proyecto** debe tener su **Responsable** (`user_id`) informado.
- Recomendado: dejar **vacío** el aprobador "Parte de horas" de los empleados
  (`timesheet_manager_id`), para usar el flujo por-proyecto.

## Cómo probar

1. Con un jefe de proyecto (responsable de X): **Partes de horas > A validar** → solo
   deben salir partes de **sus** proyectos.
2. Validar uno de X → correcto. Intentar validar uno de otro proyecto → se impide/omite.
3. Un administrador de partes que NO sea responsable de un proyecto → tampoco puede
   validar los de ese proyecto.

## Notas y límites

- La validación es **por línea** (cada parte tiene su proyecto): una semana de un empleado
  con varios proyectos la validan sus respectivos responsables.
- Partes **sin proyecto**: quedan fuera de la restricción (los gestiona el flujo nativo).
- Historial: en `19.0.2.0.0` hubo un menú propio "A validar (mis proyectos)"; se retiró en
  `19.0.3.0.0` (se usa la vista nativa) y en `19.0.4.0.0` se filtró esa vista nativa por
  proyecto.

**Depende de:** `timesheet_grid`, `project`.
