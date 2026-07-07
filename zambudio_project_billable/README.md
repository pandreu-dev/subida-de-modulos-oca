# Zambudio - Proyecto Facturable por defecto

Pequenas reglas de negocio sobre el formulario de **Proyecto** (`project.project`).

## Que hace

1. **Facturable por defecto.** Los proyectos nuevos se crean con el check
   **Facturable** (`allow_billable`) ya marcado.

2. **Sincronizacion con Productividad (solo desmarcar).** Al guardar, si el campo
   **Productividad** tiene un valor informado y **distinto de "Actividad facturable"**
   (es decir: *Actividad No facturable*, *Inactividad* o *Ausencias*), se **quita**
   automaticamente el check Facturable.
   - No se vuelve a marcar de forma automatica: si un proyecto debe volver a ser
     facturable, se marca a mano.
   - Un proyecto **sin** Productividad conserva el check por defecto (solo se desmarca
     al asignarle una actividad no facturable).

3. **Cliente obligatorio si es facturable (en la vista).** Cuando el proyecto es
   Facturable, el campo **Cliente** (`partner_id`) es obligatorio en el formulario.

4. **Productividad por defecto = "Actividad facturable".** Un proyecto nuevo se crea
   con ese valor de Productividad (por **codigo**, con `default_get`), coherente con
   que se cree Facturable por defecto. Esto **no** genera el cuadro "Informacion
   guardada" del desplegable (ese cuadro es un `ir.default` guardado en la BD; la
   migracion `19.0.1.1.0` lo elimina).

## Detalles tecnicos

- El check Facturable es el campo estandar `allow_billable` (modulo `sale_project`).
- El campo Productividad es un campo de **Studio**:
  `x_studio_selection_field_3ib_1j1am422d` (seleccion). El valor facturable es la
  cadena `"Actividad facturable"`.
- Si Studio recrea ese campo con otro nombre o cambia el valor, se ajustan las dos
  constantes al principio de
  [models/project_project.py](models/project_project.py):
  `PRODUCTIVITY_FIELD` y `BILLABLE_ACTIVITY`.

## Dependencias

- `project`
- `sale_project` (aporta el campo/label Facturable `allow_billable`).

## Pruebas

Ver [docs/MANUAL_PRUEBAS.md](docs/MANUAL_PRUEBAS.md).
