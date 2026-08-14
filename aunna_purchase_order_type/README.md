# Aunnna Purchase Order Type

## Objetivo

Este modulo anade una clasificacion sencilla para solicitudes de presupuesto y pedidos de compra mediante el campo `Tipo pedido`.

El objetivo es permitir que Compras pueda etiquetar cada pedido con un tipo funcional propio de la empresa, sin alterar el flujo estandar de compra de Odoo.

## Para que se usa

Se usa para identificar y filtrar pedidos de compra por un criterio interno.

Ejemplos de uso:

- Diferenciar tipos de solicitud.
- Clasificar compras por proceso interno.
- Facilitar busquedas y revisiones en listados.
- Tener un dato visible tanto en formulario como en vistas lista.
- Filtrar y agrupar pedidos por tipo de pedido.

## Dependencias

El modulo depende de:

- `purchase`
- `purchase_stock` (aporta `picking_type_id`, ancla para recolocar `Condiciones de pago`)
- `project_purchase` (modulo nativo Odoo 19; aporta `project_id`, el campo `Proyecto` que se recoloca)

El foco sigue siendo Compras. Las dependencias de inventario/proyecto se usan solo
para poder recolocar en el formulario campos estandar que ya existen; el modulo no
anade logica de inventario ni de proyecto.

## Modelos principales

### `aunna.purchase.order.type`

Modelo nuevo que almacena los tipos de pedido.

Campos:

- `name`: nombre del tipo de pedido.

El modelo se ordena por nombre.

### `purchase.order`

El modulo hereda `purchase.order` y anade:

- `aunna_purchase_order_type_id`: campo Many2one hacia `aunna.purchase.order.type`.

Este campo se muestra en solicitudes de presupuesto y pedidos de compra.

## Vistas

### Formulario de pedido de compra

Vista heredada:

- `purchase.purchase_order_form`

Ubicacion del campo:

- Justo despues de `Referencia de proveedor`.

El campo usa `no_create_edit` para que los usuarios no creen tipos desde el propio pedido. La gestion de tipos se hace desde configuracion.

### Reordenacion de campos en el formulario

Vista heredada adicional (`purchase.order.form.inherit.aunna.type.layout`) que
recoloca dos campos estandar **sin duplicarlos** (`position="move"`):

- `project_id` (Proyecto) pasa a justo despues de `aunna_purchase_order_type_id` (Tipo pedido).
- `payment_term_id` (Condiciones de pago) pasa a justo despues de `picking_type_id` (Entregar a).

Se mantienen intactos permisos, `readonly`, `required` e `invisible` originales de
cada campo (solo se mueve el nodo, no se redefine).

### Listados de compra

En ambas vistas lista se anaden, **despues del proveedor**, como columnas opcionales
visibles (`optional="show"`, se pueden ocultar desde el selector de columnas):

- `project_id` (**Proyecto**) — peticion de Compras para ver el proyecto en el listado.
- `aunna_purchase_order_type_id` (**Tipo pedido**).

Vistas heredadas:

- `purchase.purchase_order_kpis_tree`
- `purchase.purchase_order_view_tree`

### Busqueda de pedidos de compra

Vista heredada:

- `purchase.view_purchase_order_filter`

El campo queda disponible para buscar por **Tipo pedido** y se anade un agrupador
**Tipo pedido**.

## Menu

Ruta:

`Compra > Configuracion > Tipo pedido`

Desde este menu se crean y mantienen los tipos de pedido.

## Flujo de uso

1. Un responsable de compras entra en `Compra > Configuracion > Tipo pedido`.
2. Crea los tipos necesarios indicando solo el nombre.
3. El usuario abre una solicitud de presupuesto o pedido de compra.
4. Informa el campo `Tipo pedido`.
5. El campo queda visible en el formulario y en las vistas lista de compra.
6. Desde la lista de compras, filtra o agrupa por `Tipo pedido`.

## Permisos

El modulo define permisos separados:

- Usuarios de compra (`purchase.group_purchase_user`): pueden leer los tipos.
- Responsables de compra (`purchase.group_purchase_manager`): pueden crear, editar y eliminar tipos.

Esto permite que los usuarios seleccionen tipos existentes sin modificar la tabla maestra.

## Alcance

El modulo no cambia:

- Confirmacion de pedidos.
- Recepciones.
- Facturas de proveedor.
- Reglas de aprobacion.
- Logica de precios.
- Estados de compra.

Solo anade una clasificacion funcional.

## Archivos relevantes

- `models/purchase_order_type.py`: modelo maestro de tipos.
- `models/purchase_order.py`: campo en `purchase.order`.
- `views/purchase_order_type_views.xml`: menu y vistas del modelo de tipos.
- `views/purchase_order_views.xml`: herencias de formulario y listas de compra.
- `security/ir.model.access.csv`: permisos.
- `tests/test_purchase_order_type.py`: prueba basica de creacion del tipo.
