# Project Delivery Analytic Valuation

## Objetivo

Este modulo imputa costes de inventario de entregas manuales y traspasos internos a proyectos mediante analitica.

El objetivo es que, cuando una entrega saliente o un traspaso interno relacionado con un proyecto consume productos almacenables, el coste de esos productos se refleje en la cuenta analitica del proyecto y pueda verse desde el propio proyecto.

## Para que se usa

Se usa para controlar el coste real de entregas de inventario asociadas a proyectos.

Caso funcional:

1. Existe un proyecto con cuenta analitica.
2. Se valida una entrega saliente o un traspaso interno relacionado con ese proyecto.
3. Los movimientos de stock terminados generan o sincronizan lineas analiticas con el coste del producto.
4. El proyecto muestra un boton de entregas de inventario con recuento e importe.
5. Desde el proyecto se pueden revisar los movimientos de stock que han generado coste.

## Dependencias

El modulo depende de:

- `stock_account`
- `sale_stock`
- `sale_project`
- `project`
- `project_account`
- `project_stock_account`
- `analytic`

Estas dependencias son necesarias porque el modulo cruza stock, ventas, proyectos, valoracion de inventario y analitica.

## Modelos afectados

### `stock.move`

El modulo hereda los movimientos de stock.

Responsabilidades principales:

- Sincronizar lineas analiticas cuando el movimiento queda hecho.
- Detectar si el movimiento pertenece a una entrega manual o traspaso interno de proyecto.
- Obtener la cuenta analitica del proyecto.
- Usar la distribucion analitica indicada en el movimiento o en el albaran.
- Preparar distribucion analitica al 100 por ciento sobre la cuenta del proyecto cuando no se indique una distribucion manual.
- Calcular el importe de coste a imputar.
- Preparar lineas analiticas con referencia a la entrega y producto.

### `stock.picking`

El modulo hereda traslados.

Responsabilidades:

- Sincronizar lineas analiticas al validar una entrega.
- Detectar si una entrega o traspaso interno es candidato a imputacion de proyecto.
- Permitir informar distribucion analitica en el albaran.
- Propagar la distribucion analitica del albaran a sus movimientos.
- Excluir origenes de compra.
- Buscar proyecto desde distintos origenes disponibles.

### `project.project`

El modulo hereda proyectos.

Responsabilidades:

- Buscar movimientos de stock asociados al proyecto.
- Calcular recuento e importe de coste de entregas.
- Mostrar un boton estadistico en el proyecto.
- Abrir la vista de movimientos de entrega.

## Como detecta el proyecto

El modulo intenta encontrar el proyecto desde varias fuentes:

- Campo `project_id` en `stock.move`, si existe.
- Campo `project_id` en `stock.picking`, si existe.
- Proyecto de la venta relacionada.
- Proyecto de la linea de venta relacionada.
- Distribucion analitica de la linea de venta.

Solo se usa un proyecto si tiene cuenta analitica y si la cuenta pertenece a la compania correcta.

## Que operaciones procesa

Procesa movimientos de entregas y traspasos internos:

- Con estado `done`.
- De tipo saliente o interno.
- De productos almacenables.
- Con valor de stock o con coste estandar disponible como respaldo.
- Relacionados con un proyecto o cuenta analitica.
- Que no proceden de compras.

No procesa operaciones que el modulo identifica como originadas por compra.

## Calculo del importe

La salida al proyecto genera coste (importe negativo) y su devolucion lo descuenta (importe positivo y cantidad negativa, asi que sigue contando como coste y no como ingreso):

```text
salida:      importe = -abs(valor del movimiento)   cantidad = +cantidad
devolucion:  importe = +abs(valor del movimiento)   cantidad = -cantidad
```

Una devolucion es un movimiento creado con el boton «Devolver» (`origin_returned_move_id`). La devolucion de una devolucion vuelve a cargar. Desde 19.0.1.3.0 (Laura, 11/11/2026); antes las devoluciones sumaban coste. Al actualizar, la migracion regenera los apuntes de las devoluciones ya hechas, con la fecha del movimiento.

Si el movimiento no tiene valor pero si cantidad, se calcula un fallback usando:

- En una devolucion, el coste unitario con el que se cargo su salida, para descontar exactamente lo cargado aunque el coste del producto haya cambiado.
- `purchase_price` de la linea de venta, si existe.
- Precio estandar del producto en la compania, si no hay precio de compra en la linea.

Una devolucion descuenta con el mismo porcentaje que cargo su salida: una herramienta entregada al 100 % antes de la regla se descuenta entera.

Los movimientos del modulo crean sus apuntes aunque el tipo de operacion no tenga «Costes analiticos». Odoo 19 los filtra desde el 17/07/2026 (commit `adbfd40bf6` de `project_stock_account`), y sin la sobrescritura de `_create_analytic_move` los traslados dejarian de imputar coste al actualizar Odoo.

Las devoluciones de entregas a cliente (recepciones) siguen sin generar apunte: solo se tratan los traslados internos y las entregas.

La cantidad se obtiene de la cantidad valorada o de la cantidad del movimiento convertida a la unidad base del producto.

## Distribucion analitica

El usuario puede informar una distribucion analitica en el albaran.

Esa distribucion se copia a los movimientos de stock del albaran. Tambien puede ajustarse en cada movimiento si una linea necesita una distribucion distinta.

Al generar la linea analitica de coste, la prioridad es:

1. Distribucion analitica del movimiento.
2. Distribucion analitica del albaran.
3. Cuenta analitica del proyecto al 100 por ciento.
4. Distribucion analitica de la linea de venta, si existe.

Si se encuentra cuenta analitica del proyecto y no se ha informado distribucion manual, la distribucion es:

```text
cuenta analitica del proyecto: 100%
```

Esto permite que el coste de una entrega directa desde stock interno pueda ir al presupuesto analitico correcto, por ejemplo combinando proyecto y linea de coste de materiales o subcontrata.

## Herramientas y EPI al 0 por ciento

Peticion de Laura (05/11/2026): cuando un traslado interno tiene proyecto, cada linea lleva la distribucion analitica al 100 por ciento sobre la cuenta del proyecto, salvo los productos de herramientas y EPI, que van al 0 por ciento y no imputan coste al proyecto.

- Cada categoria de producto tiene la casilla `Al 0 % en traslados con proyecto` (`project_delivery_analytic_exclude`). Afecta tambien a sus subcategorias.
- Al actualizar a 19.0.1.2.0 se marcan solas las categorias llamadas `HERRAMIENTA(S)` o `EPI(S)` (en PRO: las cuatro de herramienta y las cuatro de EPI, una por area). Despues manda la casilla: se puede marcar o desmarcar cualquier categoria sin desarrollo.
- La distribucion de la linea se calcula al crearla y se recalcula al cambiar el producto o el proyecto del traslado. Un cambio a mano en una linea se respeta hasta entonces, tambien si se guarda junto con el cambio de proyecto y al pasar la linea a un pedido pendiente (backorder).
- Si el albaran tiene distribucion en la cabecera, las lineas normales la copian y las de herramientas y EPI la llevan al 0 por ciento. Al cambiar la cabecera se reescriben todas las lineas; al anadir o editar lineas solo se rellenan las que estan vacias.
- Si el traslado deja de ser interno (cambio de tipo de operacion), las lineas que la regla dejo al 0 por ciento vuelven a la distribucion de la cabecera (sin ella, la entrega imputa al 100 por ciento, como siempre).
- El calculo automatico no toca movimientos ya validados. Al cambiar el proyecto de un traslado hecho, la regla se aplica explicitamente y se rehacen sus apuntes (y el asiento tecnico, si `aunna_project_cost_account_moves` esta instalado).
- Al actualizar a 19.0.1.2.1, las lineas pendientes que venian vacias de antes de la regla se rellenan con ella. Al instalar desde cero se recalculan las pendientes despues de marcar las categorias.
- En el Seguimiento economico, una devolucion resta el mismo porcentaje que cargo su salida: devolver una herramienta entregada antes de la regla (cargada al 100 por ciento) la descuenta entera.
- Sin proyecto, el traslado interno no imputa nada, como antes. Si se quita el proyecto de un traslado ya hecho, se borran sus apuntes. Si se cambia, se rehacen sobre el nuevo proyecto.
- Solo aplica a traslados internos (`_get_project_delivery_rule_picking_type_codes`). Las entregas siguen como antes.
- Lo ya hecho no cambia: los movimientos validados sin distribucion siguen imputados al 100 por ciento, igual que sus apuntes.
- Una linea al 0 por ciento no genera apunte analitico ni cuenta en el boton del proyecto. Tampoco cuenta en el Seguimiento economico (`zambudio_produccion_real_new_version` 19.0.3.1.0) ni genera asiento tecnico (`aunna_project_cost_account_moves` 19.0.1.7.3).

## Vistas

En el formulario de albaran, el campo `Proyecto` se muestra junto a los datos principales
del traslado, justo debajo de `Documento de origen`. Antes quedaba dentro de la pestana
`Info adicional`, pero se recoloca aqui porque es un dato operativo necesario al crear o
revisar entregas vinculadas a proyectos.

La recolocacion se hace moviendo el campo existente `project_id` que aporta el modulo de
proyectos/stock, sin crear un campo nuevo ni cambiar su logica.

El modulo crea una vista lista de movimientos de stock:

- Fecha.
- Entrega.
- Referencia.
- Producto.
- Cantidad.
- Unidad.
- Coste.
- Compania.

Tambien crea una vista de busqueda con filtros y agrupaciones por entrega y producto.

## Boton en proyecto

En el proyecto se anade un boton estadistico:

- Texto: `Inventory Deliveries`.
- Muestra numero de movimientos y coste total.
- Abre la lista de movimientos de stock de entrega relacionados con el proyecto.

## Rentabilidad del proyecto

Los costes analiticos generados por entregas y traspasos internos se integran en la rentabilidad estandar del proyecto dentro de la linea `Materiales`.

El modulo reutiliza las lineas analiticas de categoria `picking_entry`, que son las que `project_stock_account` muestra como materiales, y anade las lineas vinculadas a los movimientos controlados por este modulo sin duplicarlas.

## Sincronizacion inicial

Al instalar el modulo se ejecuta una funcion de datos:

```text
stock.picking._sync_existing_project_delivery_analytic_lines()
```

Esto intenta sincronizar entregas existentes que ya estaban hechas antes de instalar el modulo.

Desde 19.0.1.2.0 la funcion va en un bloque `noupdate` y solo se ejecuta al instalar. Antes se ejecutaba en cada actualizacion y regeneraba todos los apuntes con la fecha de ese dia: por eso los traslados de julio tienen apuntes del 03/08/2026. Ademas, los apuntes regenerados conservan ahora la fecha del movimiento.

Pendiente (no se corrige en este cambio porque mueve cifras ya publicadas y necesita el OK de Laura):

- Los apuntes ya re-fechados siguen con la fecha de la actualizacion (03/08). Se corregirian ejecutando una vez `stock.picking._sync_existing_project_delivery_analytic_lines()` con 19.0.1.2.1: regenera con la fecha del movimiento y no cambia el porcentaje de lo ya hecho.

Corregido en 19.0.1.3.0: las devoluciones restan (ver «Calculo del importe»).

## Flujo funcional

1. Configurar proyecto con cuenta analitica.
2. Crear una entrega saliente o un traspaso interno relacionado con el proyecto.
3. Informar la distribucion analitica en el albaran o en sus movimientos si debe impactar en un presupuesto analitico concreto.
4. Validar la entrega saliente o el traspaso interno.
5. El modulo detecta movimientos candidatos.
6. Se crean o sincronizan lineas analiticas de coste.
7. Entrar en el proyecto.
8. Revisar el boton `Inventory Deliveries`.
9. Abrir el detalle para ver movimientos y coste.

## Alcance

El modulo no cambia:

- Reglas de stock.
- Reservas.
- Rutas.
- Picking types.
- Facturacion.
- Valoracion contable nativa de stock.

Su alcance es la imputacion analitica y la visibilidad del coste de entregas en proyectos.

## Archivos relevantes

- `models/stock_move.py`: distribucion e imputacion analitica por movimiento.
- `models/stock_picking.py`: distribucion, deteccion y sincronizacion desde entregas.
- `models/project_project.py`: boton y consulta desde proyecto.
- `models/product_category.py`: casilla de categoria al 0 por ciento y marcado inicial.
- `views/product_category_views.xml`: casilla en el formulario de categoria.
- `migrations/19.0.1.2.0/post-migrate.py` y `hooks.py`: marcado inicial de herramientas y EPI.
- `tests/test_category_rule.py`: pruebas de la regla.
- `views/project_delivery_stock_move_views.xml`: vistas de movimientos de coste.
- `views/stock_picking_views.xml`: distribucion analitica en albaran y movimientos, y
  posicion del campo `Proyecto` bajo `Documento de origen`.
- `data/project_delivery_analytic_sync.xml`: sincronizacion inicial.
