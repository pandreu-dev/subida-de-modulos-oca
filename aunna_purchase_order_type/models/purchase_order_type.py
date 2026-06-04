from odoo import fields, models


class AunnaPurchaseOrderType(models.Model):
    _name = "aunna.purchase.order.type"
    _description = "Tipo pedido de compra"
    _order = "name"

    name = fields.Char(
        string="Nombre",
        required=True,
    )
