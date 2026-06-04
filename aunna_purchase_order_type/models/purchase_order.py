from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    aunna_purchase_order_type_id = fields.Many2one(
        "aunna.purchase.order.type",
        string="Tipo pedido",
    )
