# Limitaciones

- Si falta diario o cuentas, no se genera asiento.
- Si la distribucion analitica no contiene proyecto y P&L, se requiere P&L por defecto configurado.
- El cron queda desactivado por defecto.
- El modulo no intenta corregir facturas de proveedor/cliente ni dropshipping.
- Para asientos publicados se usa reversion, no edicion directa.
- Las devoluciones de stock no generan automaticamente el asiento contrario en esta version. Conviene revisarlas funcionalmente antes de automatizarlas para no revertir costes de forma incorrecta.
