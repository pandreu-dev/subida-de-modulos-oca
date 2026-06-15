from collections import defaultdict

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

    def _get_items_from_aal_picking(self, with_action=True):
        self.ensure_one()
        analytic_lines = self._get_project_delivery_material_analytic_lines()
        if not analytic_lines:
            return super()._get_items_from_aal_picking(with_action)
        return self._prepare_project_delivery_material_costs(analytic_lines, with_action)

    def _get_project_delivery_material_analytic_lines(self):
        self.ensure_one()
        if not self.account_id:
            return self.env["account.analytic.line"]

        standard_domain = Domain.AND(
            [
                self._get_domain_aal_with_no_move_line(),
                Domain("category", "=", "picking_entry"),
            ]
        )
        analytic_lines = self.env["account.analytic.line"].sudo().search(standard_domain)
        delivery_lines = self._get_project_delivery_stock_moves().mapped("analytic_account_line_ids")
        delivery_lines = delivery_lines.sudo().filtered(
            lambda line: line.account_id == self.account_id
            and line.category == "picking_entry"
            and (not line.move_line_id if "move_line_id" in line._fields else True)
        )
        return analytic_lines | delivery_lines

    def _prepare_project_delivery_material_costs(self, analytic_lines, with_action=True):
        self.ensure_one()
        amounts_by_currency = defaultdict(float)
        cost_ids = []
        for line in analytic_lines:
            currency = line.currency_id or line.company_id.currency_id or self.currency_id
            amounts_by_currency[currency.id] += line.amount
            cost_ids.append(line.id)

        total_costs = 0.0
        for currency_id, amount in amounts_by_currency.items():
            currency = self.env["res.currency"].browse(currency_id).with_prefetch(amounts_by_currency)
            total_costs += currency._convert(amount, self.currency_id, self.company_id)

        sequence_by_section = self._get_profitability_sequence_per_invoice_type()
        costs = [
            {
                "id": "other_costs",
                "sequence": sequence_by_section.get(
                    "other_costs",
                    sequence_by_section.get("other_costs_aal", 12),
                ),
                "billed": total_costs,
                "to_bill": 0.0,
            }
        ]
        if with_action and self.env.user.has_group("account.group_account_readonly"):
            costs[0]["action"] = self._get_action_for_profitability_section(cost_ids, "other_costs")
        return costs

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
