from odoo import api, fields, models


class AunnaDynamicStandardCostLog(models.Model):
    _name = "aunna.dynamic.standard.cost.log"
    _description = "Historico de coste estandar dinamico"
    _order = "date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    source = fields.Selection(
        [
            ("receipt", "Recepcion"),
            ("vendor_bill", "Factura de proveedor"),
        ],
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        readonly=True,
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        related="product_id.product_tmpl_id",
        string="Plantilla",
        store=True,
        readonly=True,
    )
    categ_id = fields.Many2one(
        related="product_id.categ_id",
        string="Categoria",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        string="Moneda",
        readonly=True,
    )
    old_standard_price = fields.Monetary(string="Coste anterior", readonly=True)
    new_standard_price = fields.Monetary(string="Coste nuevo", readonly=True)
    unit_difference = fields.Monetary(string="Diferencia unidad", readonly=True)
    qty_available = fields.Float(string="Stock revalorizado", readonly=True)
    valuation_difference = fields.Monetary(string="Diferencia valoracion", readonly=True)
    purchase_order_id = fields.Many2one("purchase.order", string="Pedido de compra", readonly=True)
    purchase_line_id = fields.Many2one("purchase.order.line", string="Linea de compra", readonly=True)
    picking_id = fields.Many2one("stock.picking", string="Recepcion", readonly=True)
    stock_move_id = fields.Many2one("stock.move", string="Movimiento stock", readonly=True)
    vendor_bill_id = fields.Many2one("account.move", string="Factura proveedor", readonly=True)
    vendor_bill_line_id = fields.Many2one("account.move.line", string="Linea factura", readonly=True)
    revaluation_move_id = fields.Many2one(
        "account.move",
        string="Asiento revalorizacion",
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    note = fields.Text(string="Notas", readonly=True)

    @api.depends("product_id", "old_standard_price", "new_standard_price")
    def _compute_display_name(self):
        for record in self:
            record.display_name = "%s - %s -> %s" % (
                record.product_id.display_name or "",
                record.old_standard_price,
                record.new_standard_price,
            )
