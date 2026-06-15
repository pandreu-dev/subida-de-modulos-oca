from odoo import _, models
from odoo.fields import Domain
from odoo.tools import formatLang


class ProjectProject(models.Model):
    _inherit = "project.project"

    def _get_project_delivery_stock_moves_domain(self):
        self.ensure_one()
        project_domains = self._get_project_delivery_source_domains()
        if not project_domains:
            return [("id", "=", 0)]
        return [
            ("state", "=", "done"),
            ("picking_id.picking_type_code", "in", self._get_project_delivery_picking_type_codes()),
            ("product_id.is_storable", "=", True),
            *Domain.OR(project_domains),
        ]

    def _get_project_delivery_source_domains(self):
        self.ensure_one()
        domains = []
        stock_move = self.env["stock.move"]
        stock_picking = self.env["stock.picking"]
        if "project_id" in stock_move._fields:
            domains.append([("project_id", "=", self.id)])
        if "project_id" in stock_picking._fields:
            domains.append([("picking_id.project_id", "=", self.id)])
        if "sale_id" in stock_picking._fields and self._model_has_field("sale.order", "project_id"):
            domains.append([("picking_id.sale_id.project_id", "=", self.id)])
        if "sale_line_id" in stock_move._fields:
            if self.account_id and self._model_has_field("sale.order.line", "analytic_distribution"):
                domains.append([("sale_line_id.analytic_distribution", "in", self.account_id.ids)])
            if self._model_has_field("sale.order.line", "project_id"):
                domains.append([("sale_line_id.project_id", "=", self.id)])
            if self._model_has_field("sale.order", "project_id"):
                domains.append([("sale_line_id.order_id.project_id", "=", self.id)])
        return domains

    def _get_project_delivery_stock_moves(self):
        self.ensure_one()
        moves = self.env["stock.move"].sudo().search(self._get_project_delivery_stock_moves_domain())
        return moves.filtered(lambda move: move._is_manual_project_delivery_move())

    def _get_project_delivery_stock_move_totals(self):
        self.ensure_one()
        moves = self._get_project_delivery_stock_moves()
        return moves, sum(moves.mapped("project_delivery_analytic_cost"))

    def action_view_delivery_stock_moves(self):
        self.ensure_one()
        moves = self._get_project_delivery_stock_moves()
        view = self.env.ref(
            "project_delivery_analytic_valuation.view_stock_move_project_delivery_cost_list",
            raise_if_not_found=False,
        )
        search_view = self.env.ref(
            "project_delivery_analytic_valuation.view_stock_move_project_delivery_cost_search",
            raise_if_not_found=False,
        )
        action = {
            "type": "ir.actions.act_window",
            "name": _("Delivery Inventory Costs"),
            "res_model": "stock.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
            "context": {
                "create": False,
                "default_picking_type_code": "outgoing",
                "search_default_group_by_picking": 1,
            },
        }
        if view:
            action["views"] = [(view.id, "list"), (False, "form")]
        if search_view:
            action["search_view_id"] = search_view.id
        return action

    def _get_stat_buttons(self):
        self.ensure_one()
        buttons = super()._get_stat_buttons()
        moves, cost_amount = self._get_project_delivery_stock_move_totals()
        if not moves:
            return buttons
        amount = formatLang(self.env, abs(cost_amount), currency_obj=self.currency_id)
        buttons.append(
            {
                "icon": "truck",
                "text": _("Inventory Deliveries"),
                "number": _("%(count)s / %(amount)s", count=len(moves), amount=amount),
                "action_type": "object",
                "action": "action_view_delivery_stock_moves",
                "show": True,
                "sequence": 45,
            }
        )
        return buttons

    def _model_has_field(self, model_name, field_name):
        try:
            model = self.env[model_name]
        except KeyError:
            return False
        return field_name in model._fields

    def _get_project_delivery_picking_type_codes(self):
        return ("outgoing", "internal")
