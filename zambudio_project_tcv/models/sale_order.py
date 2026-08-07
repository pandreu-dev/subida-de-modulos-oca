from calendar import monthrange

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    tcv_amount = fields.Monetary(
        string="TCV",
        currency_field="currency_id",
        compute="_compute_tcv_amount",
        store=True,
        readonly=True,
        help="Valor total del contrato sin impuestos.",
    )
    tcv_months = fields.Float(
        string="Meses TCV",
        compute="_compute_tcv_amount",
        store=True,
        readonly=True,
        digits=(16, 4),
        help="Meses enteros del contrato (la fecha fin cuenta como ultimo dia "
        "cubierto: de 1-abr a 31-mar son 12 meses).",
    )
    tcv_missing_end_date = fields.Boolean(
        string="Falta fecha final para TCV",
        compute="_compute_tcv_amount",
        store=True,
        readonly=True,
    )
    tcv_confirmation_date = fields.Datetime(
        string="Fecha de confirmación (TCV)",
        readonly=True,
        copy=False,
        help="Momento en que se confirmó el pedido; es la base del cálculo del "
        "TCV (no la fecha del pedido/presupuesto).",
    )

    def action_confirm(self):
        res = super().action_confirm()
        now = fields.Datetime.now()
        for order in self:
            if not order.tcv_confirmation_date:
                order.tcv_confirmation_date = now
        return res

    @api.depends(
        "amount_untaxed",
        "is_subscription",
        "start_date",
        "tcv_confirmation_date",
        "date_order",
        "end_date",
        "recurring_monthly",
        "order_line.price_subtotal",
        "order_line.display_type",
        "order_line.product_id.recurring_invoice",
    )
    def _compute_tcv_amount(self):
        for order in self:
            order.tcv_months = 0.0
            order.tcv_missing_end_date = False

            # Pedido normal: total sin impuestos, descuentos incluidos.
            if not order.is_subscription:
                order.tcv_amount = order.amount_untaxed
                continue

            # En pedidos mixtos, los conceptos puntuales se suman una sola vez.
            non_recurring_amount = sum(
                line.price_subtotal
                for line in order.order_line
                if not line.display_type
                and not line.product_id.recurring_invoice
            )

            # Referencia de inicio del periodo recurrente: la FECHA DE INICIO de la
            # suscripción (start_date), que es cuando arranca el plan recurrente. Si
            # no estuviera informada, se usa la fecha real de confirmación como
            # respaldo (y date_order para pedidos anteriores al módulo).
            ref_start = (
                order.start_date
                or order.tcv_confirmation_date
                or order.date_order
            )
            period_start = (
                fields.Date.to_date(ref_start) if ref_start else False
            )

            # Una suscripción sin fecha de inicio o de fin no tiene un TCV recurrente
            # finito: se conserva solo el importe no recurrente y se muestra aviso.
            if not period_start or not order.end_date:
                order.tcv_missing_end_date = True
                order.tcv_amount = non_recurring_amount
                continue

            # Una suscripcion se factura por MESES ENTEROS, no por dias: febrero y
            # agosto valen lo mismo aunque tengan 28 o 31 dias. Ademas la fecha fin
            # de Odoo es el ULTIMO dia cubierto (inclusive): de 1-abr a 31-mar hay
            # 12 meses enteros. Por eso medimos hasta el dia SIGUIENTE al fin.
            end_inclusive = order.end_date + relativedelta(days=1)
            if end_inclusive <= period_start:
                months = 0.0
            else:
                delta = relativedelta(end_inclusive, period_start)
                months = delta.years * 12 + delta.months
                # Resto de dias de un periodo incompleto (no ocurre en
                # suscripciones normales, cuya fecha fin cae al final del periodo).
                if delta.days:
                    anchor = period_start + relativedelta(months=months)
                    days_in_month = monthrange(anchor.year, anchor.month)[1]
                    months += delta.days / days_in_month

            order.tcv_months = months
            order.tcv_amount = non_recurring_amount + (
                order.recurring_monthly * months
            )
