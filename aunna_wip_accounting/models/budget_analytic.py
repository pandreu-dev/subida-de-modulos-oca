from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BudgetAnalytic(models.Model):
    _inherit = "budget.analytic"

    wip_auto_accounting = fields.Boolean(
        string="Contabilizacion WIP automatica",
        copy=False,
        help="Si esta marcado, el proceso diario calculara y contabilizara el WIP cuando corresponda.",
    )
    wip_account_move_count = fields.Integer(
        string="Asientos WIP",
        compute="_compute_wip_account_move_count",
    )

    def _compute_wip_account_move_count(self):
        for budget in self:
            moves = budget._aunna_wip_get_account_moves()
            budget.wip_account_move_count = len(moves)

    def _aunna_wip_get_account_moves(self):
        self.ensure_one()
        calculations = self.env["aunna.wip.calculation"].search(
            [("budget_id", "=", self.id)]
        )
        moves = calculations.mapped("move_id") | calculations.mapped("reversal_move_id")
        return moves.exists()

    def action_create_wip_account_move(self):
        self.ensure_one()
        calculation = self.wip_last_calculation_id
        if not calculation:
            if not self.wip_recalculation_date:
                raise UserError(_("Calcula primero el WIP o indica una fecha de recalculo."))
            calculation = self._aunna_wip_calculate_to_date(
                self.wip_recalculation_date,
                source="manual",
            )
        return calculation.action_create_wip_move()

    def action_view_wip_account_moves(self):
        self.ensure_one()
        moves = self._aunna_wip_get_account_moves()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asientos WIP"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }
