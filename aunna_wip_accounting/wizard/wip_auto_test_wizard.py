from odoo import _, fields, models
from odoo.exceptions import UserError


class AunnaWipAutoTestWizard(models.TransientModel):
    _name = "aunna.wip.auto.test.wizard"
    _description = "Prueba de contabilizacion automatica WIP"

    execution_date = fields.Date(
        string="Fecha simulada de ejecucion",
        required=True,
        default=fields.Date.context_today,
        help="Simula un dia de ejecucion del cron. El WIP se calculara al ultimo dia del mes anterior.",
    )
    budget_id = fields.Many2one(
        "budget.analytic",
        string="Presupuesto analitico",
        domain="[('wip_auto_accounting', '=', True)]",
        help="Dejalo vacio para probar todos los presupuestos con WIP automatico.",
    )
    calculate_only = fields.Boolean(
        string="Solo calcular, sin crear asientos",
        default=False,
        help="Crea el snapshot WIP pero no genera asientos contables.",
    )

    def action_run_test(self):
        self.ensure_one()
        execution_date = fields.Date.to_date(self.execution_date)
        result = self.env["aunna.wip.calculation"]._run_monthly_auto_accounting(
            execution_date=execution_date,
            budget=self.budget_id,
            create_moves=not self.calculate_only,
            enforce_schedule=True,
        )
        calculations = result["calculations"]
        if self.budget_id and result["message"] and not self.calculate_only:
            raise UserError(result["message"])
        if not calculations:
            message = result["message"] or _(
                "No se ha generado ningun calculo. Revisa que exista un presupuesto abierto con WIP automatico."
            )
            raise UserError(message)
        return {
            "type": "ir.actions.act_window",
            "name": _("Calculos WIP de prueba"),
            "res_model": "aunna.wip.calculation",
            "view_mode": "list,form",
            "domain": [("id", "in", calculations.ids)],
        }
