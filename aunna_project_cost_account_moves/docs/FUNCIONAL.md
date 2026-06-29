# Funcional

El modulo genera asientos tecnicos compensados para que costes analiticos de proyecto aparezcan en PyG filtrado por analitica.

## Horas

Usa el importe `amount` del parte de horas. Si es negativo, se toma valor absoluto y se crea:

- Debe en cuenta de coste de horas con analitica.
- Haber en cuenta de contrapartida sin analitica.

## Entregas

Usa primero el coste almacenado por `project_delivery_analytic_valuation` en el movimiento de stock. Si no existe, recurre a las lineas analiticas de entrega y, como ultimo recurso, a valoracion/coste del producto.

## Resultado

- PyG analitico ve el coste.
- PyG general queda neteado.
