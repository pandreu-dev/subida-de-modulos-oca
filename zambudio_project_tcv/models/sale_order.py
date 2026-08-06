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
        help="Duración usada para el TCV: días de contrato divididos entre 30.",
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

            # Fecha REAL de confirmación (no la del pedido/presupuesto). Para
            # pedidos confirmados antes de instalar el modulo, se usa date_order
            # como respaldo (Odoo lo fija al confirmar).
            ref_confirmation = order.tcv_confirmation_date or order.date_order
            confirmation_date = (
                fields.Date.to_date(ref_confirmation)
                if ref_confirmation
                else False
            )

            # Una suscripción abierta no tiene un TCV recurrente finito.
            # Se conserva únicamente el importe no recurrente y se muestra aviso.
            if not confirmation_date or not order.end_date:
                order.tcv_missing_end_date = True
                order.tcv_amount = non_recurring_amount
                continue

            days = max((order.end_date - confirmation_date).days, 0)
            months = days / 30.0

            order.tcv_months = months
            order.tcv_amount = non_recurring_amount + (
                order.recurring_monthly * months
            )
