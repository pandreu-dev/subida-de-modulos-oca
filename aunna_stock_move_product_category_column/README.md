# AUNNA Stock Move Product Category Column

Modulo ligero para mostrar la categoria del producto en las lineas de operaciones
de los albaranes de inventario.

## Funcionamiento

- Anade en `stock.move` el campo relacionado `Categoria de producto`.
- El campo toma el valor de `product_id.categ_id`.
- Se muestra como columna en la pestana `Operaciones` de los albaranes.
- La columna es solo lectura y opcional desde el selector de columnas de Odoo.

## Alcance

El modulo no modifica cantidades, valoracion, validaciones ni flujo de stock. Solo
anade una columna informativa para facilitar la revision visual de los productos
en recepciones, entregas y traslados internos.

## Prueba rapida

1. Instalar o actualizar el modulo.
2. Ir a `Inventario > Operaciones > Traslados internos`.
3. Abrir un traslado con lineas de producto.
4. Revisar la pestana `Operaciones`.
5. La columna `Categoria de producto` debe aparecer junto al producto.
