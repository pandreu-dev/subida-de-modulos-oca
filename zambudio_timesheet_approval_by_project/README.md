# Zambudio - Aprobacion de partes por responsable de proyecto

Permite que el **responsable del proyecto** (`project.project.user_id`) valide los
partes de horas imputados a **sus** proyectos, en lugar del aprobador fijo por empleado
que usa Odoo de serie.

## Como funciona

- **No cambia el campo de validacion** (`account.analytic.line.validated`) ni el flujo
  nativo de `timesheet_grid`. Anade una **via paralela**: menu
  **Proyecto > A validar (mis proyectos)**.
- Ese menu muestra los partes de horas **sin validar** de los proyectos que gestiona el
  usuario. Se seleccionan y se pulsa **Validar**.
- Un usuario solo puede validar los partes de **sus** proyectos. Un **Administrador de
  partes de horas** (`hr_timesheet.group_timesheet_manager`) puede validar cualquiera y
  sigue usando el flujo nativo como siempre.
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
