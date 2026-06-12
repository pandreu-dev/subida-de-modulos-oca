from odoo import models
from odoo.tools import float_is_zero


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, *args, **kwargs):
        done_moves = super()._action_done(*args, **kwargs)
        done_moves._aunna_update_dynamic_standard_cost_from_receipts()
        return done_moves

    def _aunna_update_dynamic_standard_cost_from_receipts(self):
        moves_to_update = self.env["stock.move"]
        valued_qty_by_move = {}
        value_by_move = {}
        remaining_incoming_qty = {}
        for move in self.sudo().sorted(lambda m: (m.date, m.id)):
            product = move.product_id
            company = move.company_id
            if (
                not product
                or move.location_id.usage != "supplier"
                or move.location_dest_id.usage not in ("internal", "transit")
                or not product.with_company(company)._aunna_dynamic_standard_cost_enabled(company)
            ):
                continue

            valued_qty = 0.0
            if hasattr(move, "_get_valued_qty"):
                valued_qty = move._get_valued_qty()
            if float_is_zero(valued_qty, precision_rounding=product.uom_id.rounding):
                valued_qty = move.product_uom._compute_quantity(move.quantity, product.uom_id)
            if float_is_zero(valued_qty, precision_rounding=product.uom_id.rounding):
                continue

            move_value = abs(move.value)
            if company.currency_id.is_zero(move_value):
                continue

            key = (company.id, product.id)
            valued_qty_by_move[move.id] = abs(valued_qty)
            value_by_move[move.id] = move_value
            remaining_incoming_qty[key] = remaining_incoming_qty.get(key, 0.0) + abs(valued_qty)
            moves_to_update |= move

        for move in moves_to_update.sorted(lambda m: (m.date, m.id)):
            product = move.product_id
            company = move.company_id
            key = (company.id, product.id)
            valued_qty = valued_qty_by_move[move.id]
            move_value = value_by_move[move.id]
            new_cost = move_value / abs(valued_qty)
            qty_available = product.with_company(company)._aunna_get_revaluation_qty(company)
            revaluation_qty = max(qty_available - remaining_incoming_qty.get(key, 0.0), 0.0)
            product.with_user(self.env.user)._aunna_apply_dynamic_standard_cost(
                new_cost=new_cost,
                company=company,
                source="receipt",
                valuation_date=move.date,
                purchase_line=move.purchase_line_id,
                stock_move=move,
                revaluation_qty=revaluation_qty,
                note="Coste calculado desde la valoracion del movimiento de recepcion.",
            )
            remaining_incoming_qty[key] = max(
                remaining_incoming_qty.get(key, 0.0) - valued_qty,
                0.0,
            )
