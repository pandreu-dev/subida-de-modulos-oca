# Zambudio - Aprobacion de partes por responsable de proyecto

Permite que el **responsable del proyecto** (`project.project.user_id`) valide los
partes de horas imputados a **sus** proyectos, en lugar del aprobador fijo por empleado
que usa Odoo de serie.

## Como funciona

- **No cambia el campo de validacion** (`account.analytic.line.validated`). Anade una
  **via propia**: menu **Proyecto > A validar (mis proyectos)**, donde el responsable ve
  sus partes sin validar y pulsa **Validar**.
- **Desde `19.0.2.0.0` RESTRINGE ademas la validacion nativa** (`timesheet_grid`): un
  usuario -incluido un **Administrador de partes de horas**- solo puede **validar** (y
  **des-validar**) partes de proyectos de los que es **responsable**
  (`project.user_id`), o de empleados de los que es el **aprobador** designado
  (`hr.employee.timesheet_manager_id`, "si alguien se pone como validador es otra
  historia"). Se implementa con un override de `action_validate_timesheet` /
  `action_invalidate_timesheet` (filtra antes del write) y una `constrains` de refuerzo.
- **Valvula de escape** solo para datos huerfanos: si un proyecto no tiene responsable Y
  el empleado no tiene aprobador, para no bloquear del todo la validacion la puede hacer
  un **administrador de sistema** (`base.group_system`) — no el administrador de partes.
- Una **regla de acceso aditiva** (solo lectura) deja que el responsable **vea** los
  partes de sus proyectos. Es aditiva (OR con la regla nativa): no quita acceso a nadie.

## Configuracion recomendada

- Dejar **vacio** el aprobador "Parte de horas" de cada empleado
  (`hr.employee.timesheet_manager_id`): asi no se usa el flujo por-empleado y validan los
  jefes de proyecto (los administradores siguen pudiendo con todo).
- Asegurarse de que cada proyecto tiene su **Responsable** (`user_id`) informado.

## Notas / limites (v1)

- La validacion es **por linea** (cada parte tiene su proyecto): una semana de un
  empleado con varios proyectos la validan sus respectivos responsables.
- Partes **sin proyecto**: no aparecen aqui; los valida el administrador.
- No incluye "des-validar" para el jefe de proyecto (lo hace el administrador con el
  flujo nativo).
