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
- Preparar distribucion analitica al 100 por ciento sobre la cuenta del proyecto.
- Calcular el importe de coste a imputar.
- Preparar lineas analiticas con referencia a la entrega y producto.

### `stock.picking`

El modulo hereda traslados.

Responsabilidades:

- Sincronizar lineas analiticas al validar una entrega.
- Detectar si una entrega o traspaso interno es candidato a imputacion de proyecto.
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

El coste analitico se genera con signo negativo:

```text
importe = -abs(valor del movimiento)
```

Si el movimiento no tiene valor pero si cantidad, se calcula un fallback usando:

- `purchase_price` de la linea de venta, si existe.
- Precio estandar del producto en la compania, si no hay precio de compra en la linea.

La cantidad se obtiene de la cantidad valorada o de la cantidad del movimiento convertida a la unidad base del producto.

## Distribucion analitica

Si se encuentra cuenta analitica del proyecto, la distribucion es:

```text
cuenta analitica del proyecto: 100%
```

Si no se encuentra cuenta del proyecto, puede usar la distribucion analitica de la linea de venta si esta disponible.

## Vistas

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

## Flujo funcional

1. Configurar proyecto con cuenta analitica.
2. Crear o tener una venta/proyecto que genere entrega.
3. Validar la entrega saliente o el traspaso interno.
4. El modulo detecta movimientos candidatos.
5. Se crean o sincronizan lineas analiticas de coste.
6. Entrar en el proyecto.
7. Revisar el boton `Inventory Deliveries`.
8. Abrir el detalle para ver movimientos y coste.

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

- `models/stock_move.py`: logica de imputacion analitica por movimiento.
- `models/stock_picking.py`: deteccion y sincronizacion desde entregas.
- `models/project_project.py`: boton y consulta desde proyecto.
- `views/project_delivery_stock_move_views.xml`: vistas de movimientos de coste.
- `views/stock_picking_views.xml`: campo tecnico invisible usado por la vista.
- `data/project_delivery_analytic_sync.xml`: sincronizacion inicial.
