# Zambudio - Delegaciones de proyecto

Crea un maestro de **Delegaciones** para poder clasificar los proyectos desde el
formulario de proyecto.

## Que hace

- Crea el modelo `zambudio.project.delegation`.
- Anade el campo `zambudio_delegation_id` en `project.project`.
- Muestra el campo **Delegacion** en el formulario del proyecto, justo despues de
  **Cliente**.
- Muestra **Delegacion** en la vista lista de proyectos.
- Permite buscar y agrupar proyectos por **Delegacion**.
- Permite buscar y agrupar proyectos por **Unidad de negocio** (`x_plan5_id`).
- Asegura la delegacion **Murcia** y la usa por defecto en proyectos nuevos.
- Anade el menu **Proyecto > Configuracion > Delegaciones** para mantener el maestro.

## Permisos

- Los usuarios internos pueden leer las delegaciones para verlas y seleccionarlas.
- Los administradores de Proyecto (`project.group_project_manager`) pueden crear,
  modificar y borrar delegaciones.
- Si una delegacion esta usada por un proyecto, Odoo no permite borrarla por el
  `ondelete="restrict"` del campo.

## Como probar

1. Instala o actualiza el modulo `zambudio_project_delegation`.
2. Entra en **Proyecto > Configuracion > Delegaciones**.
3. Crea una delegacion.
4. Abre un proyecto y comprueba que aparece el campo **Delegacion** despues de
   **Cliente**.
5. Selecciona la delegacion y guarda el proyecto.
6. Crea un proyecto nuevo y comprueba que **Delegacion** se rellena con **Murcia**.
7. En la lista de proyectos, comprueba que puedes buscar y agrupar por **Delegacion** y
   por **Unidad de negocio**.

## Notas tecnicas

Es un modulo independiente a proposito: aunque existen otros modulos pequenos sobre
`project.project`, este crea un modelo nuevo, permisos y un menu propio de
configuracion. Mantenerlo separado facilita instalarlo, actualizarlo o retirarlo sin
mezclarlo con reglas de negocio distintas.

El filtro y agrupador **Unidad de negocio** usa el campo `x_plan5_id` existente en la
base de datos. Si se instala en una base donde ese campo de proyecto no exista, habra
que crearlo antes de actualizar este modulo.

**Depende de:** `project`.
