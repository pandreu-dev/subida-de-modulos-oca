from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    aunna_analytic_plan_id = fields.Many2one(
        "account.analytic.plan",
        string="Plan analitico",
        copy=False,
    )
