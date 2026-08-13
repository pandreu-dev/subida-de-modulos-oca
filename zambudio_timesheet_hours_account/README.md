# zambudio_timesheet_hours_account

Sustituye dos automatizaciones de Odoo Studio (`on_create_or_write`) sobre el
modelo `account.analytic.line`, que rellenaban el campo `auto_account_id` con la
cuenta analitica de **Horas internas** o **Horas externas** segun el tipo de
empleado.

## Logica

Para cada apunte analitico, al crear o escribir:

1. Si el apunte **no tiene proyecto** (`project_id` vacio), no se hace nada.
2. Se lee el tipo de empleado en `x_studio_tipo_empleado_1` (many2one a
   `x_tipo_empleado`) y el subtipo en `x_subtipo_empleado` (many2one a
   `x_subtipo_empleado`). El nombre del maestro se toma de `x_name` (o, en su
   defecto, `display_name`).
3. Clasificacion:
   - **Interno** (`x_studio_tipo_empleado_1` == "Interno") -> cuenta
     "Horas internas".
   - **Externo** (`x_studio_tipo_empleado_1` == "Externo") **y** subtipo
     == "Subco GZ" -> cuenta "Horas externas".
   - Cualquier otra combinacion: no se toca `auto_account_id`.
4. La compania es `line.company_id or line.employee_id.company_id`. La cuenta
   se busca por nombre + compania.
5. Solo se escribe `auto_account_id` si el valor cambia realmente.

## Consideraciones

- **Fase transitoria Studio**: los campos `x_studio_tipo_empleado_1`,
  `x_subtipo_empleado` y `auto_account_id` proceden de Odoo Studio. Todo acceso
  a ellos esta protegido comprobando su existencia en `_fields`. Si faltan, la
  logica se salta sin lanzar error.
- **No lanza excepciones**: este modulo alimenta el informe operativo
  financiero. El proceso esta envuelto en guardas y nunca debe romper el
  create/write de un apunte.
- **Sin recursion**: se usa la bandera de contexto `skip_zambudio_hours` al
  reescribir `auto_account_id`.
- **Multi-compania**: la busqueda de la cuenta filtra por compania.

## Constantes a confirmar (nombres, no ids)

- `ACCOUNT_INTERNAL_NAME = "Horas internas"`
- `ACCOUNT_EXTERNAL_NAME = "Horas externas"`
- `EMP_TYPE_INTERNAL_NAME = "Interno"`
- `EMP_TYPE_EXTERNAL_NAME = "Externo"`
- `EMP_SUBTYPE_GZ_NAME = "Subco GZ"`
