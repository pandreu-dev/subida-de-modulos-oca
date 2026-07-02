from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    aunna_product_categ_id = fields.Many2one(
        "product.category",
        string="Categoria de producto",
        related="product_id.categ_id",
        store=True,
        readonly=True,
    )
