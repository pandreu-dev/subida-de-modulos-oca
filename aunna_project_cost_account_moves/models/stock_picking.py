from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        result = super().button_validate()
        self._aunna_sync_stock_delivery_cost_moves()
        return result

    def _aunna_sync_stock_delivery_cost_moves(self):
        for picking in self:
            picking.move_ids.filtered(lambda move: move.state == "done")._aunna_sync_stock_delivery_cost_move()

    def action_aunna_generate_stock_delivery_cost_moves(self):
        self._aunna_sync_stock_delivery_cost_moves()
        return True
