# Zambudio - Nombre de proyecto unico

Impide **crear** o **renombrar** un proyecto con un nombre **identico** al de otro.

## Detalles

- Valida sobre `project.project.name` con un `@api.constrains` (salta al crear y al
  renombrar).
- La comparacion **ignora mayusculas/minusculas y espacios** al principio/final: asi
  pilla duplicados reales (`Proyecto A`, `proyecto a`, `PROYECTO A `... se consideran el
  mismo).
- **Ambito por compania**: dos companias distintas si pueden tener un proyecto con el
  mismo nombre. Si se quisiera unicidad **global** (en toda la base), es quitar del
  dominio el filtro por `company_id`.
- El control usa `sudo()` en la busqueda, para que no dependa de lo que el usuario vea
  por reglas de acceso.

## Nota

Al instalar NO falla aunque ya existan proyectos duplicados; la validacion actua a
partir de ese momento (al crear uno nuevo o al editar uno existente). Si hay duplicados
previos, conviene renombrarlos.
