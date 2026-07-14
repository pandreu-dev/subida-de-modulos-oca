from odoo import _, fields, models
from odoo.exceptions import UserError


class AunnaWipCalculateWizard(models.TransientModel):
    _name = "aunna.wip.calculate.wizard"
    _description = "Asistente calculo Avance"

    budget_id = fields.Many2one(
        "budget.analytic",
        string="Presupuesto analitico",
        required=True,
    )
    cutoff_date = fields.Date(
        string="Fecha de calculo",
        required=True,
        default=fields.Date.context_today,
    )

    def action_calculate(self):
        self.ensure_one()
        if not self.cutoff_date:
            raise UserError(_("Debes indicar una fecha de calculo."))
        calculation = self.budget_id._aunna_wip_calculate_to_date(
            self.cutoff_date,
            source="manual",
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Calculo Avance"),
            "res_model": "aunna.wip.calculation",
            "view_mode": "form",
            "res_id": calculation.id,
        }
