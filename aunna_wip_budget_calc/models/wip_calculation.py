from odoo import _, api, fields, models


class AunnaWipCalculation(models.Model):
    _name = "aunna.wip.calculation"
    _description = "Calculo WIP"
    _order = "cutoff_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    budget_id = fields.Many2one(
        "budget.analytic",
        string="Presupuesto analitico",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    cutoff_date = fields.Date(string="Fecha de calculo", required=True, readonly=True)
    source = fields.Selection(
        [
            ("manual", "Manual"),
            ("auto", "Automatico"),
        ],
        string="Origen",
        default="manual",
        required=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("calculated", "Calculado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        default="calculated",
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        "aunna.wip.calculation.line",
        "calculation_id",
        string="Lineas",
        readonly=True,
    )
    theoretical_amount = fields.Monetary(
        string="Teorico",
        currency_field="currency_id",
        readonly=True,
    )
    achieved_amount = fields.Monetary(
        string="Alcanzado",
        currency_field="currency_id",
        readonly=True,
    )
    wip_amount = fields.Monetary(
        string="WIP",
        currency_field="currency_id",
        readonly=True,
    )
    note = fields.Text(string="Notas", readonly=True)

    @api.depends("budget_id", "cutoff_date")
    def _compute_name(self):
        for record in self:
            record.name = _("%s - WIP %s") % (
                record.budget_id.display_name or _("Presupuesto"),
                record.cutoff_date or "",
            )

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_open_budget(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Presupuesto analitico"),
            "res_model": "budget.analytic",
            "view_mode": "form",
            "res_id": self.budget_id.id,
        }


class AunnaWipCalculationLine(models.Model):
    _name = "aunna.wip.calculation.line"
    _description = "Linea de calculo WIP"
    _order = "id"

    calculation_id = fields.Many2one(
        "aunna.wip.calculation",
        string="Calculo",
        required=True,
        ondelete="cascade",
        readonly=True,
    )
    company_id = fields.Many2one(
        related="calculation_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="calculation_id.currency_id",
        store=True,
        readonly=True,
    )
    budget_line_model = fields.Char(string="Modelo linea presupuesto", readonly=True)
    budget_line_res_id = fields.Integer(string="ID linea presupuesto", readonly=True)
    budget_line_name = fields.Char(string="Linea presupuesto", readonly=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analitica",
        readonly=True,
    )
    project_id = fields.Many2one("project.project", string="Proyecto", readonly=True)
    date_from = fields.Date(string="Desde", readonly=True)
    date_to = fields.Date(string="Hasta", readonly=True)
    budgeted_amount = fields.Monetary(
        string="Presupuestado",
        currency_field="currency_id",
        readonly=True,
    )
    theoretical_amount = fields.Monetary(
        string="Teorico",
        currency_field="currency_id",
        readonly=True,
    )
    achieved_amount = fields.Monetary(
        string="Alcanzado",
        currency_field="currency_id",
        readonly=True,
    )
    wip_amount = fields.Monetary(
        string="WIP",
        currency_field="currency_id",
        readonly=True,
    )
    calculation_note = fields.Char(string="Nota de calculo", readonly=True)
