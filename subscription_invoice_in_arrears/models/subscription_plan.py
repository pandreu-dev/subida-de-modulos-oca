from odoo import fields, models


class SaleSubscriptionPlan(models.Model):
    _inherit = "sale.subscription.plan"

    invoice_in_arrears = fields.Boolean(
        string="Facturar a periodo vencido",
        help=(
            "Cuando esta activado, la factura recurrente se genera al finalizar "
            "el periodo y representa el periodo inmediatamente anterior."
        ),
        default=False,
    )
