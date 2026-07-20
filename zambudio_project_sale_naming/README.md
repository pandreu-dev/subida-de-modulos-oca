# Zambudio - Nombre de proyecto desde pedido de venta

Cuando se confirma un pedido de venta con un producto que **crea proyecto**, el proyecto
(y su **cuenta analítica**) se nombran:

    <número de pedido> - <descripción de la línea que crea el proyecto>

Ejemplo: pedido `S00048`, línea "Implementación Odoo Nodo" → proyecto y cuenta analítica
`S00048 - Implementación Odoo Nodo`.

## Qué resuelve

De serie, Odoo nombra el proyecto como `pedido - <producto>` y la cuenta analítica como
`pedido`: nombres distintos entre sí y sin usar la descripción de la línea. Este módulo
unifica el nombre y lo hace más reconocible (el del pedido + lo que describe la línea).

## Cómo funciona

- **Gancho principal — `project.project.create`:** en cuanto se crea el proyecto desde
  una línea de pedido (`sale_line_id` relleno), se le pone el nombre y se renombra su
  cuenta analítica (`account_id`) con el mismo nombre. Se engancha en la **creación** (no
  en el método interno de `sale_project`) para que funcione sea cual sea la ruta por la
  que Odoo cree el proyecto.
- **Respaldo — `sale.order.line._timesheet_create_project`:** aplica lo mismo tras la
  creación nativa (idempotente).
- **Descripción de la línea:** Odoo antepone el nombre del producto (a veces con la
  referencia interna `[COD]`). Se descarta en dos pasos: (1) se quita como prefijo si el
  usuario escribió detrás en la misma línea; (2) se coge la **primera línea que no sea el
  nombre del producto**, que es el caso habitual (el usuario escribe debajo). El paso 2
  es el que evita quedarse con el nombre del producto si el prefijo no casa exactamente.
  Se compara en el **idioma del cliente y en el del usuario**. Si la línea no tiene
  descripción propia, se cae al nombre del producto.

## Configuración

No requiere configuración propia. Solo que el producto esté configurado para **crear
proyecto** (servicio con "crear proyecto/tarea"), que es config estándar de Odoo.

## Cómo probar

1. Pedido de venta → línea con un producto que crea proyecto, con una descripción clara
   (p.ej. "Implementación Odoo Nodo").
2. Confirma el pedido.
3. El proyecto creado debe llamarse `<pedido> - Implementación Odoo Nodo`.
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
- Si dos líneas del mismo pedido tienen la misma descripción, generarían el mismo nombre;
  con `zambudio_project_unique_name` instalado, el segundo chocaría → se **captura el
  error para no bloquear la confirmación** del pedido (ese proyecto conserva el nombre
  nativo). Recomendación: descripciones distintas por línea.

**Depende de:** `sale_project`.
