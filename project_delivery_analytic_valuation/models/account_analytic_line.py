from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    category = fields.Selection(
        selection_add=[("picking_entry", "Stock Move")],
        ondelete={"picking_entry": "set default"},
    )
