# Zambudio - Facturas de proveedor: fecha de vencimiento siempre visible

En Odoo 19 estándar, cuando una factura tiene **Términos de pago**, la ficha
oculta el campo «Fecha de vencimiento» y solo muestra los términos
(`account.view_move_form`, bloque `div[@name='due_date']`). La fecha sigue
calculada y guardada (`invoice_date_due`), pero no se ve.

Este módulo la muestra justo debajo de los términos de pago, en las facturas
y rectificativas de proveedor (`in_invoice`, `in_refund`).

- Es de **solo lectura**: la calculan los términos de pago, así que para
  cambiarla hay que cambiar los términos o la fecha de factura.
- Si no hay términos de pago no cambia nada: Odoo ya enseña su propio campo,
  que se puede editar.
- Si los términos tienen varios plazos, se ve el último vencimiento, que es
  lo que Odoo guarda en `invoice_date_due`.

Para enseñarlo también en las facturas de cliente, basta con añadir
`out_invoice` y `out_refund` a la condición `invisible` de la vista.

Solo añade una vista heredada: no tiene modelos, datos ni migraciones.
