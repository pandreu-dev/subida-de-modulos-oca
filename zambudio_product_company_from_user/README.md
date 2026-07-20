# Zambudio - Producto en la compañía del usuario

Cuando un usuario que pertenece a **una sola compañía** crea un producto, el producto se
crea **en esa compañía automáticamente**, sin preguntar.

## Qué resuelve

En multi-compañía, los productos se crean por defecto **sin compañía** (compartidos,
visibles en todas). Este módulo hace que un usuario de una sola compañía cree el producto
directamente en la suya, para evitar productos compartidos por error.

## Cómo funciona

- Hereda `product.template`:
  - `default_get`: propone la compañía del usuario en el formulario (si es de una sola).
  - `create`: si el usuario es de una sola compañía y no viene compañía en los valores,
    la fija a la del usuario → se cumple aunque el producto se cree por **importación o
    API**, no solo desde el formulario.
- `product.product.company_id` es un campo relacionado con la plantilla, por lo que basta
  con actuar en `product.template`.
- Un usuario **multi-compañía** (o el superusuario / procesos de sistema) **no se ve
  forzado**: elige compañía o deja el producto compartido.

## Configuración

No requiere configuración. Depende solo de a cuántas compañías tiene acceso el usuario
(`res.users.company_ids`).

## Cómo probar

1. Con un usuario que esté SOLO en una compañía: crea un producto → la **Compañía** debe
   salir puesta con esa compañía, sin tocarla.
2. Con un usuario multi-compañía: al crear un producto **no** te fuerza (eliges o lo
   dejas compartido).

## Notas

- Un producto ya creado en una compañía se puede pasar a compartido (o a otra) quitando
  el campo Compañía, si el usuario tiene acceso a varias.

**Depende de:** `product`.
