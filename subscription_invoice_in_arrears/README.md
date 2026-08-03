# Subscription Invoice In Arrears

Modulo Odoo 19 Enterprise para facturar suscripciones a periodo vencido por plan recurrente.

## Inspeccion realizada

- La documentacion oficial de Odoo 19 indica que Suscripciones usa planes recurrentes en `Subscriptions > Configuration > Recurring Plans`, con `Billing Period` configurado en semanas, meses o annos, y que `Days` no se usa para suscripciones.
- La misma documentacion describe `Align to Period Start`: las suscripciones alineadas facturan el primer dia del siguiente periodo y aplican prorrateo en el primer ciclo.
- La accion programada "Sale Subscription: generate recurring invoices and payments" factura cuando la fecha actual coincide con `Date of Next Invoice`, y Odoo actualiza esa fecha usando el plan recurrente.
- En el codigo publico de Odoo 19 Community, `sale.order` mantiene `_get_invoiceable_lines`, `_prepare_invoice`, `_create_invoices`; `sale.order.line` mantiene `_prepare_invoice_lines_vals_list` y `_prepare_invoice_line`; las lineas de factura se enlazan con `sale_line_ids`.
- No se ha podido inspeccionar `odoo/enterprise/19.0/sale_subscription` desde este equipo: el repositorio Enterprise devuelve 404 sin credenciales. La vista del plan se hereda desde `sale_subscription.sale_subscription_plan_view_form`, confirmada en preproduccion por el usuario.

## Punto de intervencion

- `sale.subscription.plan`: anade el booleano `invoice_in_arrears` como checkbox debajo de `Periodo de facturacion`.
- `sale.order`: inicializa la facturacion vencida, desplaza `next_invoice_date` una sola vez, evita facturas recurrentes antes de la fecha debida, calcula el factor de prorrateo del primer periodo vencido parcial y guarda el ultimo periodo procesado para no duplicarlo.
- `sale.order.line`: solo para lineas recurrentes (`recurring_invoice` si existe), sustituye la descripcion del periodo por el periodo inmediatamente anterior, prorratea el precio cuando el periodo vencido real es parcial y rellena campos estandar de diferimiento si existen (`deferred_start_date` / `deferred_end_date`, o equivalentes detectados).

## Compatibilidad y limites

- Los planes sin `Facturar a periodo vencido` no se modifican.
- `Align to Period Start` se respeta en fechas: con facturacion vencida, la primera `next_invoice_date` se lleva al siguiente inicio de periodo. Por ejemplo, inicio `22/07/2026` en plan mensual alineado => primera factura `01/08/2026` por `22/07/2026 - 31/07/2026`.
- En periodos vencidos parciales, el modulo aplica prorrateo economico sobre el precio de la linea recurrente. Por ejemplo, inicio `29/07/2026` en plan mensual alineado => factura `01/08/2026` por `29/07/2026 - 31/07/2026` con factor `3/31`.
- Para suscripciones existentes con facturas recurrentes previas, al inicializar se considera consumido el periodo inmediatamente anterior a la `next_invoice_date` actual y se mueve la siguiente fecha un periodo mas para evitar refacturar lo ya facturado.
- Al actualizar a `19.0.1.0.1`, se corrigen las suscripciones vencidas alineadas que estuvieran inicializadas sin periodo facturado previo, para que la primera fecha sea el siguiente inicio de periodo.

## Instalacion

Copiar este directorio en el `addons_path` personalizado y ejecutar:

```bash
python odoo-bin -d <base_preproduccion> --addons-path=<odoo_addons>,<enterprise_addons>,<custom_addons> -i subscription_invoice_in_arrears --stop-after-init
```

Actualizar:

```bash
python odoo-bin -d <base_preproduccion> --addons-path=<odoo_addons>,<enterprise_addons>,<custom_addons> -u subscription_invoice_in_arrears --stop-after-init
```

Tests:

```bash
python odoo-bin -d <base_test> --addons-path=<odoo_addons>,<enterprise_addons>,<custom_addons> -u subscription_invoice_in_arrears --test-enable --test-tags subscription_invoice_in_arrears --stop-after-init
```

## Prueba manual recomendada

1. En preproduccion, instalar el modulo y actualizar la lista de aplicaciones.
2. Abrir `Suscripciones > Configuracion > Planes recurrentes`.
3. Activar `Facturar a periodo vencido` en un plan mensual de pruebas.
4. Crear una suscripcion con inicio `01/07/2026`, una linea recurrente y confirmar.
5. Comprobar que `Fecha de proxima factura` queda en `01/08/2026`.
6. Ejecutar la facturacion recurrente con fecha de contexto `01/08/2026` o ajustar la fecha de prueba en la base.
7. Validar que la factura indica `01/07/2026 - 31/07/2026` en la linea recurrente y que la siguiente fecha queda en `01/09/2026`.
8. Repetir con una linea no recurrente en el mismo pedido: antes del `01/08/2026` solo debe poder facturarse la linea no recurrente.
9. Repetir con `Alinear al inicio del periodo` activado e inicio `22/07/2026`: no debe facturar la linea recurrente al confirmar; la proxima factura debe quedar en `01/08/2026`.
10. Al facturar el `01/08/2026`, la linea recurrente debe indicar `22/07/2026 - 31/07/2026`, aplicar prorrateo economico del primer periodo parcial y dejar la siguiente factura en `01/09/2026`.
11. Repetir con inicio `29/07/2026` e importe mensual: la factura del `01/08/2026` debe prorratear `29/07/2026 - 31/07/2026` con factor `3/31`.
12. Repetir con plan trimestral/anual y con febrero de anno bisiesto y no bisiesto.

## Nota de validacion

No se han ejecutado tests en este workspace porque aqui no esta disponible una instancia Odoo 19 Enterprise con `sale_subscription`. Ejecutarlos en preproduccion antes de subir a produccion.
