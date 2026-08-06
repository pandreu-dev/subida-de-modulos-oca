from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    tcv_sale_order_ids = fields.One2many(
        comodel_name="sale.order",
        inverse_name="project_id",
        string="Pedidos incluidos en el TCV",
        readonly=True,
    )
    tcv_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda TCV",
        compute="_compute_tcv",
        store=True,
        readonly=True,
    )
    tcv_amount = fields.Monetary(
        string="TCV",
        currency_field="tcv_currency_id",
        compute="_compute_tcv",
        store=True,
        readonly=True,
        help="Suma del TCV de los pedidos confirmados vinculados al proyecto.",
    )
    tcv_order_count = fields.Integer(
        string="Pedidos TCV",
        compute="_compute_tcv",
        store=True,
        readonly=True,
    )
    tcv_incomplete_order_count = fields.Integer(
        string="Pedidos con TCV incompleto",
        compute="_compute_tcv",
        store=True,
        readonly=True,
    )

    @api.depends(
        "company_id",
        "tcv_sale_order_ids",
        "tcv_sale_order_ids.state",
        "tcv_sale_order_ids.company_id",
        "tcv_sale_order_ids.currency_id",
        "tcv_sale_order_ids.date_order",
        "tcv_sale_order_ids.tcv_amount",
        "tcv_sale_order_ids.tcv_missing_end_date",
    )
    def _compute_tcv(self):
        today = fields.Date.context_today(self)

        for project in self:
            orders = project.tcv_sale_order_ids.filtered(
                lambda order: order.state == "sale"
            )
            company = (
                project.company_id
                or orders[:1].company_id
                or self.env.company
            )
            currency = company.currency_id
            total = 0.0

            for order in orders:
                conversion_date = (
                    fields.Date.to_date(order.date_order)
                    if order.date_order
                    else today
                )
                total += order.currency_id._convert(
                    order.tcv_amount,
                    currency,
                    company,
                    conversion_date,
                )

            project.tcv_currency_id = currency
            project.tcv_amount = total
            project.tcv_order_count = len(orders)
            project.tcv_incomplete_order_count = len(
                orders.filtered("tcv_missing_end_date")
            )

    def action_view_tcv_sale_orders(self):
        self.ensure_one()
        orders = self.tcv_sale_order_ids.filtered(
            lambda order: order.state == "sale"
        )
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale.action_orders"
        )
        action["domain"] = [("id", "in", orders.ids)]
        action["context"] = {
            "create": False,
            "default_project_id": self.id,
        }
        return action
