# Zambudio - Producto en la compania del usuario

Cuando un usuario que pertenece a **una sola compania** crea un producto, el producto
se crea **en esa compania automaticamente**, sin preguntar.

- Usuarios **multi-compania**: no se les fuerza nada. Pueden crear el producto en la
  compania que quieran o dejarlo **sin compania** (compartido, visible en todas).
- Un producto ya creado en una compania se puede pasar a compartido (o a otra) quitando
  el campo Compania, si el usuario tiene acceso a varias companias.

## Detalle tecnico

- Hereda `product.template`:
  - `default_get`: propone la compania del usuario en el formulario (si es de una sola).
  - `create`: si el usuario es de una sola compania y no viene compania en los valores,
    la fija a la del usuario (asi se cumple aunque se cree por importacion/API).
- `product.product.company_id` es un campo relacionado con la plantilla, por lo que
  basta con actuar en `product.template`.
- No afecta a superusuario ni a procesos de sistema (tienen acceso a varias companias).
