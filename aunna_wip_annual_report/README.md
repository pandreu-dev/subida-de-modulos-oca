# AUNNA WIP - Informe anual

Modulo V1 para crear un informe anual de WIP por proyecto o cuenta analitica desde
Contabilidad > Informes > Informe WIP anual.

## Funcionamiento

- El usuario crea un informe indicando ejercicio, compania y proyecto o cuenta
  analitica.
- El sistema crea cuatro lineas: ER/OE, Facturacion, Ingreso reconocido y WIP real
  acumulado.
- Las columnas `Prev.` son editables por el usuario.
- Las columnas `Real` se recalculan con el boton `Recalcular reales`.
- Las columnas `Dif.` son la diferencia entre real y previsto.
- Los totales anuales suman los importes mensuales de cada bloque.

## Fuentes de datos reales

- ER/OE: lineas de pedidos de venta confirmados (`sale.order.line`) con distribucion
  analitica, por fecha de confirmacion si existe o fecha del pedido.
- Facturacion: apuntes de ingreso publicados de facturas de cliente con distribucion
  analitica.
- Ingreso reconocido: apuntes publicados contra la cuenta ingreso WIP configurada en
  la compania.
- WIP real acumulado: acumulado mensual de `Ingreso reconocido - Facturacion`.

## Notas

El calculo se filtra por la cuenta analitica seleccionada. Si se selecciona un
proyecto, el modulo intenta localizar automaticamente su cuenta analitica.
