# Zambudio - Nombre de proyecto único

Impide **crear** o **renombrar** un proyecto con un nombre **idéntico** al de otro.

## Qué resuelve

Evita proyectos duplicados por nombre, que generan confusión (dos "Mantenimiento X",
imputaciones al proyecto equivocado, etc.).

## Cómo funciona

- Hereda `project.project` y valida `name` con `@api.constrains("name", "company_id")`
  → salta tanto al **crear** como al **renombrar**.
- La comparación **ignora mayúsculas/minúsculas y espacios** al principio/final: detecta
  duplicados reales: `Proyecto A`, `proyecto a` o `PROYECTO A` con espacios sobrantes se
  consideran el mismo nombre.
- **Ámbito por compañía**: dos compañías distintas SÍ pueden repetir nombre.
- **Las plantillas de proyecto quedan fuera del control** (`is_template`). Odoo crea una
  plantilla **copiando** un proyecto existente (con el mismo nombre); si se exigiera
  nombre único, se rompería la función estándar "Crear plantilla desde proyecto". Por eso
  ni una plantilla se valida ni una plantilla bloquea a un proyecto real con ese nombre.
- La búsqueda usa `sudo()` para que el control no dependa de lo que el usuario vea por
  reglas de acceso (si no, podría duplicar un proyecto que no ve).

## Configuración

No requiere configuración.

## Cómo probar

1. Crea un proyecto "Prueba".
2. Intenta crear otro "prueba" (o "PRUEBA ") → debe **impedirlo** con un mensaje.
3. Con otra compañía activa, el mismo nombre SÍ se permite.
4. Sobre "Prueba", ⋮ → **Crear plantilla** (convertirlo en plantilla) → debe **permitirlo**
   (aunque la plantilla se llame igual).

## Notas y límites

- Al instalar **NO falla** aunque ya existan duplicados previos; la validación actúa a
  partir de ese momento. Si hay duplicados antiguos, conviene renombrarlos.
- Para unicidad **global** (toda la base, no por compañía): quitar el filtro `company_id`
  del dominio.
- Interacción con `zambudio_project_sale_naming`: si dos líneas del mismo pedido crean
  proyecto con la misma descripción, chocarían; ese módulo captura el error para no
  bloquear la confirmación del pedido.

**Depende de:** `project`.
