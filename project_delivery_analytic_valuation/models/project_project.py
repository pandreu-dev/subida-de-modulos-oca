import json

from odoo import _, models
from odoo.tools import formatLang


class ProjectProject(models.Model):
    _inherit = "project.project"

    def _get_project_delivery_stock_moves_domain(self):
        self.ensure_one()
        if "project_id" not in self.env["stock.picking"]._fields:
            return [("id", "=", 0)]
        return [
            ("state", "=", "done"),
            ("picking_id.picking_type_code", "=", "outgoing"),
            ("picking_id.project_id", "=", self.id),
            ("product_id.is_storable", "=", True),
            ("value", "!=", 0),
        ]

    def _get_project_delivery_stock_moves(self):
        self.ensure_one()
        moves = self.env["stock.move"].sudo().search(self._get_project_delivery_stock_moves_domain())
        return moves.filtered(lambda move: move._is_manual_project_delivery_move())

    def _get_project_delivery_stock_move_totals(self):
        self.ensure_one()
        moves = self._get_project_delivery_stock_moves()
        return moves, -sum(abs(move.value) for move in moves)

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

    def action_profitability_items(self, section_name, domain=None, res_id=False):
        if section_name == "delivery_stock_moves":
            action = self.action_view_delivery_stock_moves()
            if domain is not None:
                action["domain"] = domain
            if res_id:
                action.update({"views": [(False, "form")], "view_mode": "form", "res_id": res_id})
            return action
        return super().action_profitability_items(section_name, domain, res_id)

    def _get_profitability_labels(self):
        return {
            **super()._get_profitability_labels(),
            "delivery_stock_moves": _("Inventory Deliveries"),
        }

    def _get_profitability_sequence_per_invoice_type(self):
        return {
            **super()._get_profitability_sequence_per_invoice_type(),
            "delivery_stock_moves": 12,
        }

    def _get_profitability_items(self, with_action=True):
        profitability_items = super()._get_profitability_items(with_action)
        moves, billed_amount = self._get_project_delivery_stock_move_totals()
        if not moves or not billed_amount:
            return profitability_items

        section_id = "delivery_stock_moves"
        cost_item = {
            "id": section_id,
            "sequence": self._get_profitability_sequence_per_invoice_type()[section_id],
            "billed": billed_amount,
            "to_bill": 0.0,
        }
        if with_action and self.env.user.has_group("stock.group_stock_user"):
            args = [section_id, [("id", "in", moves.ids)]]
            if len(moves) == 1:
                args.append(moves.id)
            cost_item["action"] = {
                "name": "action_profitability_items",
                "type": "object",
                "args": json.dumps(args),
            }

        costs = profitability_items["costs"]
        costs["data"].append(cost_item)
        costs["total"]["billed"] += billed_amount
        return profitability_items

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
