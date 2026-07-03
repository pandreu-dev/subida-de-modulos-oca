# Limitaciones

- Si falta diario o cuentas, no se genera asiento.
- Si la distribucion analitica no contiene ninguna cuenta analitica con porcentaje positivo, no se genera asiento.
- El P&L por defecto es opcional, pero recomendable si se quiere explotar el PyG por esa dimension.
- El cron queda desactivado por defecto.
- El modulo no intenta corregir facturas de proveedor/cliente ni dropshipping.
- Para asientos publicados se usa reversion, no edicion directa.
- Las devoluciones de stock no generan automaticamente el asiento contrario en esta version. Conviene revisarlas funcionalmente antes de automatizarlas para no revertir costes de forma incorrecta.
