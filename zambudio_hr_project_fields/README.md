# Zambudio - Campos de empleado y proyecto (Studio a código)

Adopta como **código** (sin mover datos) los campos que Studio añadió a `hr.employee`
y el campo *Productividad* de `project.project`. Misma técnica validada en
`zambudio_master_data` (state=base + propiedad del módulo vía `pre_init_hook`).

## Campos que adopta
**hr.employee:**
- `x_studio_tipo_empleado_1` → Tipo empleado (many2one `x_tipo_empleado`)
- `x_studio_subtipo_empleado` → Subtipo empleado (many2one `x_subtipo_empleado`)
- `x_studio_tipo_de_personal_1` → Tipo personal (many2one `x_tipo_de_personal`)
- `x_studio_fecha_de_alta_1` → Fecha de alta (date)

**project.project:**
- `x_studio_selection_field_3ib_1j1am422d` → Productividad (selection)

## NO incluye (decisión de negocio — Laura)
- `hr.employee.x_studio_subtipo_de_empleado` (selection ANTIGUO, duplicado del m2o).
- `project.project.x_studio_inactividad_directa` (no se usa).

Estos NO se adoptan → siguen siendo de Studio y se irán cuando se retire Studio.
⚠️ Antes de retirar Studio, confirmar que `x_studio_subtipo_empleado` (m2o) tiene los
datos que hiciera falta conservar del selection antiguo.

## Notas
- Las automatizaciones de horas internas/externas (`zambudio_timesheet_hours_account`)
  y `zambudio_project_billable` siguen funcionando: apuntan a los MISMOS nombres de campo.
- Sin vistas propias: las de Studio siguen mostrándolos hasta que se migren/limpien.

## Dependencias
- `hr`, `project`, `zambudio_master_data`
