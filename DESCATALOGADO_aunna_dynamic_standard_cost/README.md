# Coste estandar dinamico basado en ultimo precio de compra

Modulo para Odoo 19 que permite mantener el metodo de coste estandar, pero actualizando automaticamente el coste del producto con el ultimo precio de compra valido.

## Objetivo funcional

El objetivo es que determinados productos sigan usando coste estandar de Odoo, pero que ese coste se vaya actualizando automaticamente cuando se recibe mercancia o se publica una factura de proveedor.

Con esto, el producto sigue configurado con metodo de coste `standard`, pero el campo `standard_price` se ajusta al ultimo coste real de compra detectado por el sistema.

## Que problema resuelve

En Odoo, el coste estandar no cambia por si solo con cada compra. Si se quiere que el stock quede valorado al ultimo coste de compra, normalmente hay que actualizar el coste manualmente o cambiar a otro metodo de coste como FIFO/AVCO.

Este modulo cubre un escenario intermedio:

- Mantener coste estandar.
- Tomar automaticamente el ultimo coste de compra.
- Actualizar `standard_price`.
- Revalorizar el stock existente cuando proceda.
- Dejar trazabilidad completa.

## Dependencias

El modulo depende de:

- `purchase_stock`
- `stock_account`
- `account`

Estas dependencias son necesarias porque el modulo trabaja con compras, recepciones, valoracion de stock y asientos contables.

## Cuando aplica

Solo aplica si se cumplen todas estas condiciones:

- El producto es almacenable.
- El metodo de coste del producto es `standard`.
- El producto o su categoria tienen activado `Usar ultimo coste de compra`.

No aplica a:

- Productos consumibles.
- Servicios.
- Productos FIFO.
- Productos AVCO.

El modulo no modifica la logica nativa de FIFO ni AVCO.

## Activacion por categoria

En la categoria de producto se anaden campos:

- `Usar ultimo coste de compra`.
- `Cuenta contrapartida revalorizacion`.

Si se activa en una categoria, los productos de esa categoria que sean almacenables y tengan coste estandar quedan incluidos.

La cuenta de contrapartida se usa para los asientos de revalorizacion cuando cambia el coste estandar y existe stock disponible.

## Activacion por producto

En la ficha del producto se anade:

- `Usar ultimo coste de compra`.

Esto permite activar el comportamiento solo en productos concretos, aunque la categoria no lo tenga marcado.

## Prioridad de configuracion

El modulo considera activo el coste dinamico si se cumple al menos una de estas dos condiciones:

- El producto tiene marcado `Usar ultimo coste de compra`.
- La categoria del producto tiene marcado `Usar ultimo coste de compra`.

## Flujo desde recepciones

El modulo se engancha en `stock.move._action_done()`.

Cuando se valida una recepcion de proveedor:

1. Odoo valida el movimiento de stock.
2. Odoo calcula el valor del movimiento segun su logica nativa.
3. El modulo revisa si el movimiento viene de proveedor hacia una ubicacion interna o de transito.
4. Si el producto aplica, toma el valor real del movimiento.
5. Calcula el nuevo coste unitario:

   `valor del movimiento / cantidad valorada`

6. Revaloriza solo el stock previo disponible, para no duplicar la valoracion de la entrada que se acaba de recibir.
7. Actualiza `standard_price`.
8. Crea una linea de historico.

## Por que en recepciones se revaloriza solo stock previo

La mercancia recien recibida ya entra valorada por el propio movimiento de stock de Odoo.

Si el modulo revalorizara tambien esa misma cantidad, podria duplicar contablemente parte del efecto.

Por eso, en recepciones calcula el stock disponible y descuenta la cantidad de las entradas que se estan validando en ese mismo lote de movimientos.

## Flujo desde facturas de proveedor

El modulo tambien se engancha en `account.move.action_post()`.

Cuando se publica una factura de proveedor:

1. Revisa las lineas de factura con producto.
2. Ignora lineas de seccion, nota o sin producto.
3. Comprueba que el producto aplica al coste estandar dinamico.
4. Toma el subtotal de la linea sin impuestos.
5. Usa el descuento ya aplicado por Odoo en `price_subtotal`.
6. Convierte el importe a moneda de compania si hace falta.
7. Convierte la cantidad a la unidad de medida del producto.
8. Calcula el nuevo coste unitario.
9. Revaloriza el stock disponible si procede.
10. Actualiza `standard_price`.
11. Crea una linea de historico.

## Moneda, descuentos e impuestos

En facturas:

- El calculo usa `price_subtotal`, por lo que no incluye impuestos.
- El descuento ya esta incluido en el subtotal calculado por Odoo.
- Si la moneda de la factura no es la moneda de la compania, se convierte el importe.
- La cantidad se convierte a la unidad de medida base del producto.

En recepciones:

- El calculo parte del valor del movimiento de stock.
- Ese valor aprovecha la logica nativa de Odoo para valoracion de compra.

## Revalorizacion contable

Si el producto tiene valoracion automatica y hay stock disponible, el modulo genera un asiento contable por la diferencia:

`(coste nuevo - coste anterior) x stock revalorizado`

Si el coste sube:

- Debe: cuenta de valoracion de stock.
- Haber: cuenta de contrapartida.

Si el coste baja:

- Debe: cuenta de contrapartida.
- Haber: cuenta de valoracion de stock.

## Cuenta de contrapartida

El modulo intenta usar la cuenta en este orden:

1. Cuenta de contrapartida configurada en la categoria.
2. Cuenta de diferencia de precio del producto/categoria, si existe.
3. Cuenta de variacion de stock, si existe.
4. Cuenta de gasto del producto.

Si no encuentra las cuentas necesarias, muestra un error para evitar generar asientos incorrectos.

## Cuando no se genera asiento

No se genera asiento de revalorizacion si:

- No hay stock disponible para revalorizar.
- La diferencia de valor es cero.
- El producto no tiene valoracion automatica.
- El producto no aplica al coste dinamico.

En esos casos puede actualizarse `standard_price`, pero no hay asiento contable porque no existe stock que ajustar o no corresponde contablemente.

## Historico y trazabilidad

El modulo crea el modelo:

`aunna.dynamic.standard.cost.log`

Menu:

`Inventario > Configuracion > Historico coste estandar dinamico`

Cada registro guarda:

- Fecha.
- Origen: recepcion o factura proveedor.
- Producto.
- Plantilla de producto.
- Categoria.
- Compania.
- Coste anterior.
- Coste nuevo.
- Diferencia unitaria.
- Stock revalorizado.
- Diferencia de valoracion.
- Pedido de compra, si existe.
- Linea de compra, si existe.
- Recepcion, si existe.
- Movimiento de stock, si existe.
- Factura de proveedor, si existe.
- Linea de factura, si existe.
- Asiento de revalorizacion, si se genero.
- Usuario.
- Notas tecnicas del calculo.

## Seguridad

El historico es de solo lectura para usuarios internos.

No se permite crear, modificar ni borrar registros del historico manualmente desde la interfaz.

## Archivos del modulo

- `__manifest__.py`: dependencias y archivos cargados.
- `models/product.py`: campos de configuracion y logica principal de coste/revalorizacion.
- `models/stock_move.py`: actualizacion desde recepciones.
- `models/account_move.py`: actualizacion desde facturas de proveedor.
- `models/dynamic_standard_cost_log.py`: modelo de trazabilidad.
- `views/product_category_views.xml`: campos en categoria.
- `views/product_template_views.xml`: campo en producto.
- `views/dynamic_standard_cost_log_views.xml`: vistas y menu del historico.
- `security/ir.model.access.csv`: permisos.

## Pruebas recomendadas

### Prueba 1: producto no configurado

1. Crear o usar un producto almacenable con coste estandar.
2. No marcar `Usar ultimo coste de compra`.
3. Validar una compra o factura.
4. Confirmar que `standard_price` no cambia.

### Prueba 2: actualizacion por categoria

1. Marcar `Usar ultimo coste de compra` en la categoria.
2. Configurar producto con coste estandar.
3. Validar recepcion con precio nuevo.
4. Confirmar que `standard_price` cambia.
5. Confirmar que se crea registro en el historico.

### Prueba 3: actualizacion por producto

1. Marcar `Usar ultimo coste de compra` en el producto.
2. Dejar la categoria sin marcar.
3. Validar recepcion o factura.
4. Confirmar que el coste cambia solo para ese producto.

### Prueba 4: factura con descuento

1. Crear factura de proveedor con descuento en linea.
2. Publicar factura.
3. Confirmar que el coste se calcula con subtotal sin impuestos y descuento aplicado.

### Prueba 5: moneda extranjera

1. Crear factura en moneda distinta a la compania.
2. Publicar factura.
3. Confirmar que el coste se calcula en moneda de compania.

### Prueba 6: revalorizacion con stock

1. Tener stock disponible del producto.
2. Cambiar el coste mediante compra o factura.
3. Confirmar que se genera asiento de revalorizacion si el producto tiene valoracion automatica.

### Prueba 7: sin stock disponible

1. Dejar stock a cero.
2. Publicar factura o validar recepcion.
3. Confirmar que cambia `standard_price`.
4. Confirmar que no se genera asiento de revalorizacion por stock existente.

### Prueba 8: FIFO o AVCO

1. Usar producto FIFO o AVCO.
2. Validar compra/factura.
3. Confirmar que el modulo no cambia el coste ni genera historico.

## Consideraciones contables

Este modulo toca valoracion de stock y asientos contables. Antes de usarlo en produccion conviene validar:

- Cuentas de valoracion de stock.
- Diario de stock.
- Cuenta de diferencia de precio o contrapartida.
- Productos con valoracion automatica.
- Comportamiento esperado con facturas posteriores a recepciones.
- Politica contable exacta del cliente.

## Limitaciones conocidas

- No recalcula historico antiguo.
- No cambia el metodo de coste del producto.
- No aplica a FIFO ni AVCO.
- No sustituye una revision contable de las cuentas de stock.
- Si una factura se publica mucho despues de la recepcion, el nuevo coste se aplica en la fecha de factura.

## Criterio de aceptacion

El modulo se considera correcto si:

- Solo actua en productos configurados.
- Solo actua en coste estandar.
- Actualiza `standard_price` al ultimo coste de compra.
- Revaloriza stock existente cuando procede.
- Genera asiento contable si corresponde.
- Guarda trazabilidad completa.
- No modifica FIFO ni AVCO.
