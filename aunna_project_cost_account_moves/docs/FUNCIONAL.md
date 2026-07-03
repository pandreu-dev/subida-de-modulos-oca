# Funcional

El modulo genera asientos tecnicos compensados para que costes analiticos de proyecto aparezcan en PyG filtrado por analitica.

## Horas

Usa partes de horas con coste de proyecto. Si la linea ya trae `amount` negativo, se toma su valor absoluto. Si no lo trae, intenta calcular el coste con las horas y el coste horario del empleado. Se crea:

- Debe en cuenta de coste de horas con analitica.
- Haber en cuenta de contrapartida sin analitica.

Las cuentas analiticas con porcentaje `0%` se ignoran para evitar asientos tecnicos sin imputacion real.
Si el modulo anade un valor de P&L por defecto, lo fusiona con la cuenta analitica del proyecto en la misma distribucion para mantener el formato esperado por Odoo 19. Si no hay valor de P&L por defecto, genera el asiento con la distribucion analitica disponible.

## Entregas

Usa primero el coste almacenado por `project_delivery_analytic_valuation` en el movimiento de stock. Si no existe, recurre a las lineas analiticas de entrega y, como ultimo recurso, a valoracion/coste del producto.

## Resultado

- PyG analitico ve el coste.
- PyG general queda neteado.
