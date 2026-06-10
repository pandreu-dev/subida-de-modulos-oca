# Aunnna Stock Picking Analytic Plan

## Objetivo

Este modulo anade un campo de plan analitico en los traslados de inventario (`stock.picking`).

El objetivo es que en las entregas, recepciones o traslados internos se pueda registrar el plan analitico relacionado con la operacion, dejando esa informacion visible en la pestana de informacion adicional.

## Para que se usa

Se usa para guardar una referencia al plan analitico en un traslado.

Caso principal:

- En `Inventario > Entregas`, al abrir una entrega, el usuario entra en `Info adicional` y selecciona el plan analitico correspondiente.

## Dependencias

El modulo depende de:

- `stock`
- `analytic`

`stock` aporta el modelo `stock.picking`.

`analytic` aporta el modelo `account.analytic.plan`.

## Modelo afectado

### `stock.picking`

El modulo hereda `stock.picking` y anade:

- `aunna_analytic_plan_id`: Many2one hacia `account.analytic.plan`.

Nombre funcional del campo:

- `Plan analitico`

El campo no se copia al duplicar el traslado.

## Vista afectada

Vista heredada:

- `stock.view_picking_form`

Ubicacion:

- Pestana `Info adicional`.
- Grupo `Otra informacion`.
- Al final del bloque, bajo los campos existentes de esa zona.

## Uso funcional

1. Entrar en Inventario.
2. Abrir Entregas.
3. Abrir un traslado.
4. Ir a la pestana `Info adicional`.
5. Informar el campo `Plan analitico`.
6. Guardar el traslado.

## Alcance

El modulo solo guarda y muestra el dato.

No cambia:

- Validacion de entregas.
- Movimientos de stock.
- Valoracion de inventario.
- Distribucion analitica.
- Asientos contables.
- Reglas de rutas o picking.

## Seguridad

No se crea ningun modelo nuevo, por lo que no se define un CSV de permisos propio.

El campo se rige por los permisos normales del modelo `stock.picking`.

## Archivos relevantes

- `models/stock_picking.py`: campo nuevo en `stock.picking`.
- `views/stock_picking_views.xml`: herencia de la vista de traslado.
- `__manifest__.py`: dependencias y carga de vista.
