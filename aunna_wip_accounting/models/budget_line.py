import logging

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class BudgetLine(models.Model):
    _inherit = "budget.line"

    aunnna_wip_recognized_amount = fields.Monetary(
        string="Reconocido acumulado",
        currency_field="currency_id",
        compute="_compute_aunnna_wip_recognized_amount",
        help="Ingreso reconocido NETO acumulado en la cuenta de reconocimiento WIP "
        "(705), via asientos del diario WIP, para las dimensiones analiticas de la "
        "linea, desde el inicio del periodo hasta la fecha de corte "
        "(wip_recalculation_date del presupuesto, o hoy). Las reversiones netean, por "
        "lo que muestra el ingreso reconocido acumulado a la fecha (no lo sube ni baja "
        "la reversion).",
    )

    def _compute_aunnna_wip_recognized_amount(self):
        for line in self:
            line.aunnna_wip_recognized_amount = line._aunnna_wip_recognized_to_date()

    def _aunnna_wip_recognized_to_date(self):
        """Ingreso reconocido acumulado (neto) en la cuenta 705 del diario WIP para la
        analitica de la linea, hasta la fecha de corte. Reutiliza los helpers de
        ``budget.analytic`` (modulo aunna_wip_budget_calc) via ``budget_analytic_id``.
        """
        self.ensure_one()
        budget = self.budget_analytic_id
        if not budget:
            return 0.0
        # Solo tiene sentido en lineas de ingreso.
        if not budget._aunna_wip_is_income_budget_line(self):
            return 0.0
        company = budget._aunna_wip_get_company().sudo()
        income_account = company.aunnna_wip_income_account_id
        wip_journal = company.aunnna_wip_journal_id
        if not income_account or not wip_journal:
            return 0.0
        analytic_dimensions = budget._aunna_wip_get_analytic_dimensions(self)
        if not analytic_dimensions:
            return 0.0
        try:
            date_from, _date_to = budget._aunna_wip_get_line_dates(self)
        except UserError:
            return 0.0
        cutoff_date = budget.wip_recalculation_date or fields.Date.context_today(budget)

        MoveLine = self.env["account.move.line"].sudo()
        domain = [
            ("account_id", "=", income_account.id),
            ("journal_id", "=", wip_journal.id),
            ("date", ">=", date_from),
            ("date", "<=", cutoff_date),
            ("company_id", "=", company.id),
            ("analytic_distribution", "!=", False),
        ]
        if "parent_state" in MoveLine._fields:
            domain.append(("parent_state", "=", "posted"))
        else:
            domain.append(("move_id.state", "=", "posted"))
        # Cruce de dimensiones analiticas de la linea/presupuesto.
        for dimension in analytic_dimensions:
            domain = expression.AND(
                [domain, [("analytic_distribution", "in", dimension["accounts"].ids)]]
            )

        total = 0.0
        for move_line in MoveLine.search(domain):
            ratio = budget._aunna_wip_distribution_ratio(
                move_line.analytic_distribution,
                analytic_dimensions,
            )
            if not ratio:
                continue
            # -balance: el credito a 705 (reconocimiento) suma; el debito de la
            # reversion resta -> el neto queda con el ultimo acumulado vigente al corte.
            total += budget._aunna_wip_move_line_income_amount(move_line) * ratio
        return total
