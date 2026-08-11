# Zambudio - Descripción en pedido de venta

Añade un campo **Descripción** (`zambudio_description`) en el pedido de venta /
presupuesto (`sale.order`).

## Para qué sirve

- **Identificar/localizar** mejor el pedido con un texto propio.
- **Alimentar el nombre del proyecto** que se cree desde ese pedido: el módulo
  `zambudio_project_sale_naming` usa este campo para nombrar el proyecto como
  `<número de pedido> - <Descripción>`.

## Comportamiento

- Es un campo **normal** de texto (una línea). **No se oculta al confirmar**: queda
  como descripción del pedido en presupuesto y en pedido de venta.
- Puede quedar **vacío** sin problema (p. ej. un pedido adicional que se vincula a mano
  a un proyecto ya existente). Si está vacío, el proyecto conserva el nombre nativo de
  Odoo.

## Ubicación

Formulario de pedido de venta, justo debajo del **Cliente**.

## Dependencias

- `sale`

## Relación con otros módulos

`zambudio_project_sale_naming` **depende de este módulo** y lee `zambudio_description`
para nombrar el proyecto y su cuenta analítica. Este módulo por sí solo solo añade el
campo; la parte de naming vive en el otro módulo.
