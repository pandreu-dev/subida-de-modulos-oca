# AUNNA Project Cost Account Moves

## Objetivo

Este modulo crea asientos contables tecnicos y compensados para que costes que ya existen en analitica tambien aparezcan en el informe de Perdidas y Ganancias filtrado por proyecto.

Flujos incluidos:

- Partes de horas.
- Entregas de almacen con distribucion analitica, apoyandose en `project_delivery_analytic_valuation`.

Flujos excluidos:

- Facturas de proveedor.
- Facturas de cliente.
- Dropshipping.
- Compras facturadas.

## Funcionamiento contable

Por cada coste se crea un asiento equilibrado:

- Linea de coste con analitica: Debe en cuenta 640x/600x.
- Linea de compensacion sin analitica: Haber en cuenta configurada.

El PyG general queda neteado. El PyG filtrado por proyecto ve solo la linea con analitica.

## Configuracion

Ruta:

`Contabilidad > Configuracion > Ajustes tecnicos de costes de proyecto`

Campos principales:

- Diario tecnico.
- Cuenta coste horas.
- Cuenta contrapartida horas.
- Cuenta coste stock.
- Cuenta contrapartida stock.
- Activar horas.
- Activar entregas.
- Publicar automaticamente.
- P&L por defecto para horas.
- P&L por defecto para stock.

Si no hay diario o cuentas configuradas, no se generan asientos.

Las distribuciones analiticas con porcentaje `0%` se descartan y no se consideran validas para generar el asiento tecnico.

## Trazabilidad

Cada asiento queda vinculado a `aunna.project.cost.move.link`, con origen, importe, fecha, hash y estado. El modulo no edita asientos publicados: si el origen cambia, revierte y genera un asiento nuevo.

## Pruebas manuales

1. Configurar diario tecnico y cuentas.
2. Activar horas o entregas.
3. Validar un parte con coste negativo en un proyecto.
4. Confirmar que se crea asiento tecnico 640x/640x o 640x/puente.
5. Validar una entrega con analitica de proyecto.
6. Confirmar asiento tecnico 600x/600x o 600x/puente.
7. Revisar que PyG general no cambia y PyG analitico muestra el coste.
