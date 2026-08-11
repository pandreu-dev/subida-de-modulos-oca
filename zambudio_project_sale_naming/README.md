# Zambudio - Nombre de proyecto desde pedido de venta

Cuando se confirma un pedido de venta con un producto que **crea proyecto**, el proyecto
(y su **cuenta analítica**) se nombran:

    <número de pedido> - <Descripción del pedido>

La **Descripción** sale del campo `zambudio_description` del pedido (módulo
`zambudio_sale_order_description`). Ejemplo: pedido `S00048` con Descripción
"Implementación Odoo Nodo" → proyecto y cuenta analítica `S00048 - Implementación Odoo Nodo`.

Si la Descripción del pedido está **vacía**, el proyecto conserva el **nombre nativo de
Odoo** (el módulo no renombra nada).

## Qué resuelve

De serie, Odoo nombra el proyecto como `pedido - <producto>` y la cuenta analítica como
`pedido`: nombres distintos entre sí. Este módulo unifica ambos y los hace más
reconocibles usando el número de pedido + la Descripción que el usuario escribe en el
pedido.

## Cómo funciona

- **Gancho principal — `project.project.create`:** en cuanto se crea el proyecto desde
  una línea de pedido (`sale_line_id` relleno), se le pone el nombre y se renombra su
  cuenta analítica (`account_id`) con el mismo nombre. Se engancha en la **creación** (no
  en el método interno de `sale_project`) para que funcione sea cual sea la ruta por la
  que Odoo cree el proyecto.
- **Respaldo — `sale.order.line._timesheet_create_project`:** aplica lo mismo tras la
  creación nativa (idempotente).
- **Origen del nombre:** el campo **Descripción** (`zambudio_description`) del pedido. Si
  está relleno → `<pedido> - <Descripción>`. Si está vacío → no se renombra (nombre nativo
  de Odoo). Ya **no** se usa la descripción de la línea ni el nombre del producto.
- **El renombrado solo ocurre al crear el proyecto.** Si después cambias el nombre del
  proyecto a mano, se respeta (el módulo no lo revierte). Editar la Descripción del pedido
  más tarde tampoco renombra un proyecto ya creado.

## Configuración

No requiere configuración propia. Solo que el producto esté configurado para **crear
proyecto** (servicio con "crear proyecto/tarea"), que es config estándar de Odoo.

## Cómo probar

1. Pedido de venta con un producto que crea proyecto y con el campo **Descripción**
   relleno (p.ej. "Implementación Odoo Nodo").
2. Confirma el pedido.
3. El proyecto creado debe llamarse `<pedido> - Implementación Odoo Nodo`. Si dejas la
   Descripción vacía, el proyecto se queda con el nombre nativo de Odoo.
4. Su cuenta analítica (Ajustes del proyecto > Analítico, o Contabilidad > Apuntes
   analíticos) debe llamarse **igual**.

## Notas y límites

- **La cuenta analítica SIEMPRE se muestra con el cliente detrás.** Odoo calcula el
  *nombre mostrado* de una cuenta analítica como `nombre - cliente` (es estándar, no
  nuestro). Aunque el módulo le ponga el nombre correcto, en pantalla se leerá
  `S00048 - Implementación Odoo Nodo - NOMBRE DEL CLIENTE`. **Lo que hay que comprobar es
  el campo Nombre de la cuenta, no lo que sale en los desplegables.** No se puede quitar
  sin parchear Odoo.
- **Cuenta analítica compartida por pedido:** Odoo crea UNA cuenta analítica por pedido.
  Si un mismo pedido tuviera VARIAS líneas que crean proyecto, comparten esa cuenta; para
  no pisar nombres, **solo se renombra la cuenta si es dedicada** a un único proyecto. En
  el flujo habitual (1 proyecto por pedido) no aplica.
- Si un pedido crea **varios** proyectos (varias líneas que crean proyecto), todos
  tomarían el mismo nombre `<pedido> - <Descripción>`; con `zambudio_project_unique_name`
  instalado, el segundo chocaría → se **captura el error para no bloquear la confirmación**
  (ese proyecto conserva el nombre nativo). En el flujo habitual (1 proyecto por pedido)
  no aplica.

**Depende de:** `sale_project`, `zambudio_sale_order_description`.
