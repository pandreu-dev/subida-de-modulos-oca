from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        result = super().button_validate()
        self._aunna_sync_stock_delivery_cost_moves()
        return result

    def write(self, vals):
        result = super().write(vals)
        # cambiar proyecto o distribución de un traslado hecho rehace sus apuntes: el
        # asiento técnico tiene que seguirles (o revertirse si ya no hay coste)
        if {"project_id", "analytic_distribution"} & set(vals):
            self.filtered(lambda picking: picking.state == "done")._aunna_sync_stock_delivery_cost_moves()
        return result

    def _aunna_sync_stock_delivery_cost_moves(self):
        for picking in self:
            picking.move_ids.filtered(
                lambda move: move.state == "done"
            ).sudo()._aunna_sync_stock_delivery_cost_move()

    def action_aunna_generate_stock_delivery_cost_moves(self):
        self._aunna_sync_stock_delivery_cost_moves()
        return True
