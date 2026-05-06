from odoo import fields, models
from odoo.fields import Domain


class ResCompany(models.Model):
    _inherit = "res.company"

    def action_close_stock_valuation(self, at_date=None, auto_post=False):
        self.ensure_one()
        project_moves = self._get_delivery_project_stock_moves_for_valuation_closing(at_date=at_date)
        action = super().action_close_stock_valuation(at_date=at_date, auto_post=auto_post)
        closing_move = self.env["account.move"]
        if isinstance(action, dict) and action.get("res_id"):
            closing_move = self.env["account.move"].browse(action["res_id"])
        closing_move.filtered(lambda move: move.state == "draft").with_context(
            delivery_project_stock_move_ids=project_moves.ids
        )._apply_delivery_project_analytics()
        return action

    def _get_delivery_project_stock_moves_for_valuation_closing(self, at_date=None):
        self.ensure_one()
        if "project_id" not in self.env["stock.picking"]._fields:
            return self.env["stock.move"]
        last_closing_date = self._get_last_closing_date()
        domain = Domain(
            [
                ("company_id", "=", self.id),
                ("state", "=", "done"),
                ("picking_id.picking_type_code", "=", "outgoing"),
                ("picking_id.project_id", "!=", False),
                ("picking_id.project_id.account_id", "!=", False),
                ("product_id.is_storable", "=", True),
                ("value", "!=", 0),
            ]
        )
        if last_closing_date:
            domain &= Domain([("date", ">", last_closing_date)])
        if at_date:
            domain &= Domain([("date", "<=", fields.Datetime.to_datetime(at_date))])
        return self.env["stock.move"].search(domain).filtered(
            lambda move: move.picking_id._is_manual_project_delivery()
        )
