from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    aunna_department_in_id = fields.Many2one(
        "aunna.stock.department",
        string="Departamento de entrada",
        tracking=True,
    )
    aunna_department_out_id = fields.Many2one(
        "aunna.stock.department",
        string="Departamento de salida",
        tracking=True,
    )
    aunna_department_id = fields.Many2one(
        "aunna.stock.department",
        string="Departamento",
        compute="_compute_aunna_department_id",
        search="_search_aunna_department_id",
    )
    aunna_department_display = fields.Char(
        string="Departamento",
        compute="_compute_aunna_department_display",
        store=True,
    )
    aunna_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    aunna_goods_value = fields.Monetary(
        string="Valor",
        currency_field="aunna_currency_id",
        compute="_compute_aunna_goods_value",
        store=True,
    )

    @api.depends(
        "picking_type_id.code",
        "aunna_department_in_id",
        "aunna_department_out_id",
    )
    def _compute_aunna_department_id(self):
        for picking in self:
            if picking.picking_type_id.code == "incoming":
                picking.aunna_department_id = picking.aunna_department_in_id
            elif picking.picking_type_id.code == "outgoing":
                picking.aunna_department_id = picking.aunna_department_out_id
            else:
                picking.aunna_department_id = (
                    picking.aunna_department_out_id or picking.aunna_department_in_id
                )

    def _search_aunna_department_id(self, operator, value):
        negative_operators = ("!=", "not in")
        join_operator = "&" if operator in negative_operators else "|"
        return [
            join_operator,
            ("aunna_department_in_id", operator, value),
            ("aunna_department_out_id", operator, value),
        ]

    @api.depends(
        "picking_type_id.code",
        "aunna_department_in_id.name",
        "aunna_department_out_id.name",
    )
    def _compute_aunna_department_display(self):
        for picking in self:
            department_in = picking.aunna_department_in_id.display_name
            department_out = picking.aunna_department_out_id.display_name
            if picking.picking_type_id.code == "incoming":
                picking.aunna_department_display = department_in
            elif picking.picking_type_id.code == "outgoing":
                picking.aunna_department_display = department_out
            elif department_in and department_out:
                picking.aunna_department_display = "%s -> %s" % (
                    department_out,
                    department_in,
                )
            else:
                picking.aunna_department_display = department_out or department_in

    @api.depends(
        "move_ids.state",
        "move_ids.quantity",
        "move_ids.product_uom_qty",
        "move_ids.product_uom",
        "move_ids.product_id",
        "move_ids.product_id.standard_price",
    )
    def _compute_aunna_goods_value(self):
        for picking in self:
            total = 0.0
            for move in picking.move_ids:
                if move.state == "cancel" or not move.product_id:
                    continue
                total += picking._aunna_move_goods_value(move)
            picking.aunna_goods_value = total

    def _aunna_move_goods_value(self, move):
        self.ensure_one()
        if "stock_valuation_layer_ids" in move._fields and move.stock_valuation_layer_ids:
            return abs(sum(move.stock_valuation_layer_ids.mapped("value")))
        quantity = move.quantity if move.state == "done" else move.product_uom_qty
        quantity = move.product_uom._compute_quantity(quantity, move.product_id.uom_id)
        company = move.company_id or self.company_id or self.env.company
        standard_price = move.product_id.with_company(company).standard_price
        return abs(quantity * standard_price)
