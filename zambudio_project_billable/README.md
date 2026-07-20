# Zambudio - Proyecto Facturable por defecto

Pequenas reglas de negocio sobre el formulario de **Proyecto** (`project.project`).

## Que hace

1. **Facturable por defecto.** Los proyectos nuevos se crean con el check
   **Facturable** (`allow_billable`) ya marcado y con **Productividad = "Actividad
   facturable"** (por codigo, con `default_get`).

2. **Sincronizacion REACTIVA (al cambiar el campo, no al guardar).** La
   sincronizacion se ejecuta con `@api.onchange`, en el formulario, en el momento de
   cambiar Productividad o Facturable:

   - Al **cambiar Productividad**:
     - Si pasa a **"Actividad facturable"** -> se **marca** Facturable (y el cliente
       pasa a ser obligatorio).
     - Si **deja de ser** "Actividad facturable" -> se **desmarca** Facturable y se
       **limpia el cliente**.
   - Al **cambiar Facturable**:
     - Si se **desmarca** -> se **limpia el cliente**.
     - Si se **marca** -> el cliente es **obligatorio**.

3. **Cliente obligatorio si es facturable (en la vista).** Cuando el proyecto es
   Facturable, el campo **Cliente** (`partner_id`) es obligatorio en el formulario.

> El cuadro "Informacion guardada" del desplegable de Productividad era un
> `ir.default` guardado en la BD (no lo genera este modulo); la migracion
> `19.0.1.1.0` lo elimina. El valor por defecto se aporta por codigo.

## Requisito de configuracion

Este modulo **depende de un campo de Studio** que debe existir en la base de datos (no
viaja con el modulo): el campo **Productividad** en `project.project`
(`x_studio_selection_field_3ib_1j1am422d`) con una opcion cuya etiqueta sea exactamente
**"Actividad facturable"**. Si ese campo/opcion no existe (p.ej. en una base nueva), la
sincronizacion no encuentra el valor y no actua. Al desplegar en otra instancia, asegurar
que el campo Studio esta creado igual.

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
