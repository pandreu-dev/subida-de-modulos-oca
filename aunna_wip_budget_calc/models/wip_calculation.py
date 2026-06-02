from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
    )
    calculated_theoretical_amount = fields.Monetary(
        string="Teorico calculado",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        readonly=True,
    )
    theoretical_amount = fields.Monetary(
        string="Teorico validado",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        readonly=True,
    )
    achieved_amount = fields.Monetary(
        string="Alcanzado",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        readonly=True,
    )
    calculated_wip_amount = fields.Monetary(
        string="WIP calculado",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        readonly=True,
    )
    wip_amount = fields.Monetary(
        string="WIP a contabilizar",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
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

    @api.depends(
        "line_ids.calculated_theoretical_amount",
        "line_ids.theoretical_amount",
        "line_ids.achieved_amount",
        "line_ids.calculated_wip_amount",
        "line_ids.wip_amount",
    )
    def _compute_amounts(self):
        for record in self:
            record.calculated_theoretical_amount = sum(
                record.line_ids.mapped("calculated_theoretical_amount")
            )
            record.theoretical_amount = sum(record.line_ids.mapped("theoretical_amount"))
            record.achieved_amount = sum(record.line_ids.mapped("achieved_amount"))
            record.calculated_wip_amount = sum(
                record.line_ids.mapped("calculated_wip_amount")
            )
            record.wip_amount = sum(record.line_ids.mapped("wip_amount"))

    def action_cancel(self):
        for calculation in self:
            if "move_id" in calculation._fields and calculation.move_id:
                raise UserError(
                    _("No se puede cancelar un calculo WIP que ya tiene un asiento contable.")
                )
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
        string="Teorico validado",
        currency_field="currency_id",
    )
    calculated_theoretical_amount = fields.Monetary(
        string="Teorico calculado",
        currency_field="currency_id",
        readonly=True,
    )
    achieved_amount = fields.Monetary(
        string="Alcanzado",
        currency_field="currency_id",
        readonly=True,
    )
    calculated_wip_amount = fields.Monetary(
        string="WIP calculado",
        currency_field="currency_id",
        readonly=True,
    )
    wip_amount = fields.Monetary(
        string="WIP a contabilizar",
        currency_field="currency_id",
    )
    adjustment_note = fields.Char(string="Motivo del ajuste")
    manually_adjusted = fields.Boolean(
        string="Ajustado manualmente",
        compute="_compute_manually_adjusted",
        store=True,
    )
    calculation_note = fields.Char(string="Nota de calculo", readonly=True)

    @api.depends(
        "calculated_theoretical_amount",
        "theoretical_amount",
        "calculated_wip_amount",
        "wip_amount",
    )
    def _compute_manually_adjusted(self):
        for line in self:
            line.manually_adjusted = (
                line.theoretical_amount != line.calculated_theoretical_amount
                or line.wip_amount != line.calculated_wip_amount
            )

    @api.onchange("theoretical_amount")
    def _onchange_theoretical_amount(self):
        for line in self:
            line.wip_amount = line.theoretical_amount - line.achieved_amount

    def _check_manual_adjustment_allowed(self):
        if not self.env.su and not self.env.user.has_group("project.group_project_manager"):
            raise UserError(
                _("Solo un jefe de proyecto puede modificar el importe WIP a contabilizar.")
            )
        for line in self:
            calculation = line.calculation_id
            if calculation.state == "cancelled":
                raise UserError(_("No se puede modificar un calculo WIP cancelado."))
            if "move_id" in calculation._fields and calculation.move_id:
                raise UserError(
                    _("No se puede modificar el WIP despues de crear el asiento contable.")
                )

    def write(self, vals):
        editable_fields = {"theoretical_amount", "wip_amount", "adjustment_note"}
        if editable_fields.intersection(vals):
            self._check_manual_adjustment_allowed()
        if "theoretical_amount" in vals and "wip_amount" not in vals and len(self) > 1:
            for line in self:
                line_vals = dict(
                    vals,
                    wip_amount=vals["theoretical_amount"] - line.achieved_amount,
                )
                super(AunnaWipCalculationLine, line).write(line_vals)
            return True
        if "theoretical_amount" in vals and "wip_amount" not in vals:
            vals = dict(
                vals,
                wip_amount=vals["theoretical_amount"] - self.achieved_amount,
            )
        return super().write(vals)
