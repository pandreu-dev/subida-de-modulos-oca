# Aunnna Public Holiday Timesheet Bridge

## Objetivo

Este modulo crea un puente funcional entre los festivos publicos gestionados por modulos OCA y los partes de horas de Odoo.

El caso que resuelve es el siguiente: los festivos OCA pueden verse correctamente en Ausencias segun pais, provincia, ciudad o direccion del empleado, pero no siempre existen como `resource.calendar.leaves`. La generacion estandar de partes de horas de Odoo se apoya en el flujo estandar de ausencias y no toma directamente esos festivos OCA. Por eso, aunque el festivo se vea en el calendario de ausencias, no se crea automaticamente una linea en `account.analytic.line`.

Este modulo lee los festivos OCA aplicables a cada empleado, calcula cuantas horas deberia trabajar ese empleado ese dia segun su calendario activo, y crea o actualiza el parte de horas correspondiente en el proyecto y tarea de ausencias configurados en la compania.

## Para que se usa

Se usa para que los festivos publicos computen como partes de horas de ausencia, normalmente contra:

- Proyecto interno configurado en Timesheets.
- Tarea de ausencia configurada como Time Off.
- Empleado y usuario correctos.
- Horas reales segun el horario activo del empleado en esa fecha.

Ejemplos funcionales:

- Si Pablo tiene Horario Murcia y el 25/12/2026 es festivo aplicable, se genera un parte de 8 horas.
- Si Pablo tiene Horario Murcia verano y el 15/08/2026 es festivo aplicable, se genera un parte de 7 horas si ese horario define 7 horas para ese dia.

## Dependencias

El modulo depende de:

- `hr_timesheet`
- `project_timesheet_holidays`
- `hr_holidays_public`
- `hr_employee_calendar_planning`

La razon de estas dependencias es que el modulo necesita partes de horas, configuracion de ausencias en timesheets, festivos publicos OCA y planificacion de calendarios por intervalos en el empleado.

## Modelos principales

### `aunna.public.holiday.timesheet.bridge`

Modelo tecnico que ejecuta la logica principal de generacion y sincronizacion.

Responsabilidades:

- Buscar empleados a procesar.
- Buscar festivos OCA aplicables por rango de fechas.
- Calcular horas del empleado en cada festivo.
- Crear partes de horas si no existen.
- Actualizar partes generados por el modulo si cambian horas, festivo, horario, ubicacion o configuracion.
- Eliminar partes generados que ya no corresponden cuando un festivo deja de aplicar.
- Evitar duplicados.
- No tocar partes manuales.
- No modificar partes bloqueados, validados o ya ligados a contabilidad/facturacion.

### `account.analytic.line`

El modulo anade campos tecnicos para identificar las lineas generadas:

- `x_is_public_holiday_timesheet`
- `x_generated_by_public_holiday_bridge`
- `x_public_holiday_line_id`
- `x_public_holiday_source`
- `x_public_holiday_hash`

Estos campos permiten distinguir claramente entre partes manuales y partes creados por este puente.

### Wizard `aunna.public.holiday.timesheet.wizard`

Asistente funcional para lanzar el proceso manualmente desde Odoo.

Campos principales:

- Fecha desde.
- Fecha hasta.
- Empleados.
- Modo de ejecucion: manual o automatico.
- Forzar actualizacion.
- Lineas de resultado.

Botones:

- Simular.
- Generar/actualizar.

### Hooks de sincronizacion

El modulo hereda varios modelos para mantener los partes alineados cuando cambia la informacion de origen:

- `calendar.public.holiday.line`
- `calendar.public.holiday`
- `hr.employee`
- `res.partner`
- `hr.employee.calendar`
- `resource.calendar`
- `resource.calendar.attendance`

Cuando se crea, modifica o elimina un festivo, una ubicacion de empleado o un horario, el modulo recalcula los partes generados que dependan de esa informacion.

## Logica funcional

1. Se selecciona un rango de fechas.
2. Se seleccionan empleados o se procesan todos los empleados activos desde el cron.
3. Para cada empleado se comprueba que tenga usuario vinculado.
4. Se obtiene el proyecto interno y la tarea Time Off desde la configuracion de la compania.
5. Se buscan los festivos OCA aplicables al empleado.
6. Para cada festivo se calcula la jornada teorica del empleado ese dia.
7. Si las horas son mayores que cero, se prepara una linea de parte de horas.
8. Si ya existe una linea generada por el modulo para ese empleado, fecha y festivo, se actualiza si procede.
9. Si existe una linea manual en el mismo proyecto, tarea, empleado y fecha, se respeta y no se duplica.
10. Si ya no corresponde una linea generada anteriormente, se elimina si esta editable.

## Calculo de horas

Las horas se calculan desde `employee.resource_calendar_id` usando:

```python
get_work_hours_count(start_dt, end_dt, compute_leaves=False)
```

Se usa `compute_leaves=False` porque se quiere saber cuantas horas habria trabajado el empleado segun su horario, sin restar el propio festivo.

La zona horaria se toma del usuario del empleado, del usuario actual o de `Europe/Madrid`.

## Idempotencia

El modulo esta preparado para ejecutarse varias veces sobre el mismo rango sin crear duplicados.

La busqueda de duplicados se hace por:

- Empleado.
- Fecha.
- Proyecto.
- Tarea.
- Festivo OCA.
- Indicador de linea generada por el puente.

Ademas guarda un hash tecnico con los valores relevantes. Si el hash no cambia y no se fuerza la actualizacion, la linea queda como esta.

## Partes manuales

Si ya existe una linea manual de partes de horas en el proyecto y tarea de ausencias para el mismo empleado y fecha, el modulo no crea otra linea y devuelve accion `Omitir manual`.

Esto evita duplicar horas si un usuario ya habia introducido manualmente el parte.

## Lineas bloqueadas

Si una linea generada por el modulo ya esta validada, bloqueada, facturada o vinculada a un apunte contable, no se modifica ni se elimina automaticamente.

En ese caso el resultado indica que la linea esta bloqueada.

## Cron

El modulo incluye una accion planificada:

- Nombre funcional: generacion automatica de partes de horas por festivos publicos.
- Frecuencia: diaria.
- Rango por defecto: desde el 1 de enero del anio actual hasta el 31 de diciembre del anio siguiente.

El cron queda instalado inactivo por defecto para evitar revisiones masivas de empleados en bases con mucha plantilla. La generacion debe lanzarse desde el asistente o por los hooks acotados a cambios de festivos, ubicacion u horarios.

## Uso manual

Ruta:

`Partes de horas > Configuracion > Generar partes de festivos`

Pasos:

1. Abrir el asistente.
2. Seleccionar fecha desde y fecha hasta.
3. Seleccionar uno o varios empleados.
4. Elegir modo manual o automatico.
5. Marcar Forzar actualizacion si se quiere reescribir lineas generadas aunque parezcan actualizadas.
6. Pulsar Simular para revisar lo que haria.
7. Pulsar Generar/actualizar para crear, actualizar o eliminar lineas.
8. Revisar la pestana Resultado.

## Resultados posibles

El asistente puede devolver acciones como:

- Crear.
- Actualizar.
- Sin cambios.
- Eliminar obsoleta.
- Omitir manual.
- Omitir bloqueada.
- Obsoleta bloqueada.
- Sin usuario.
- Sin festivos.
- Sin horas.
- Sin configuracion.
- Error.

## Configuracion necesaria

Antes de usarlo debe existir:

- Proyecto interno configurado en la compania.
- Tarea Time Off configurada en la compania.
- Empleado con usuario vinculado.
- Direccion o datos de ubicacion del empleado para aplicar festivos por pais, provincia o ciudad.
- Horario activo del empleado en la fecha del festivo.
- Festivos OCA configurados en `calendar.public.holiday` y `calendar.public.holiday.line`.

## Permisos

El asistente y sus lineas estan disponibles para el grupo:

- `hr_timesheet.group_hr_timesheet_approver`

Las lineas de partes de horas se crean con permisos elevados para asegurar que el proceso automatico pueda registrar correctamente los partes generados.

## Archivos relevantes

- `models/public_holiday_timesheet_bridge.py`: logica principal.
- `models/account_analytic_line.py`: campos tecnicos en partes de horas.
- `models/source_sync_hooks.py`: sincronizacion al cambiar festivos, empleados, direcciones u horarios.
- `wizard/public_holiday_timesheet_wizard.py`: asistente manual.
- `wizard/public_holiday_timesheet_wizard_views.xml`: vista y menu del asistente.
- `data/ir_cron.xml`: accion planificada.
- `security/ir.model.access.csv`: permisos del asistente.
