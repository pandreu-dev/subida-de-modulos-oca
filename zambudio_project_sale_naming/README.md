# Zambudio - Nombre de proyecto desde pedido de venta

Cuando se confirma un pedido de venta con un producto configurado para **crear
proyecto**, el proyecto (y su **cuenta analitica**) se nombran:

    <numero de pedido de venta> - <descripcion de la linea que crea el proyecto>

Ejemplo: pedido `S00048`, linea "Implementacion Odoo Nodo" -> proyecto y cuenta
analitica `S00048 - Implementacion Odoo Nodo`.

## Detalles

- Hereda `sale.order.line._timesheet_create_project`: tras la creacion nativa, fuerza
  el nombre y renombra la cuenta analitica con el mismo nombre.
- Usa la **primera linea** de la descripcion (evita saltos de linea/notas); si no hay
  descripcion, usa el nombre del producto.

## Avisos

- **Cuenta analitica compartida por pedido:** Odoo crea UNA cuenta analitica por pedido
  de venta. Si un mismo pedido tuviera VARIAS lineas que crean proyecto, todas
  comparten esa cuenta y el ultimo proyecto le pone su nombre. En el flujo habitual
  (1 proyecto por pedido) no aplica.
- Si dos lineas del mismo pedido tuvieran la misma descripcion, generarian el mismo
  nombre de proyecto. Si `zambudio_project_unique_name` esta instalado, el segundo
  choca; en ese caso **no se bloquea la confirmacion del pedido**: ese proyecto
  conserva su nombre nativo (se captura el error). Recomendacion: descripciones
  distintas por linea.
