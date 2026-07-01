import logging

from odoo import fields, models


_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    aunna_wip_calculation_line_id = fields.Many2one(
        "aunna.wip.calculation.line",
        string="Linea calculo WIP",
        copy=False,
        index=True,
        ondelete="set null",
    )
    aunna_wip_project_id = fields.Many2one(
        "project.project",
        string="Proyecto WIP",
        copy=False,
        index=True,
        ondelete="set null",
    )

    def _aunna_wip_expected_distribution(self):
        self.ensure_one()
        calc_line = self.aunna_wip_calculation_line_id
        account = calc_line.analytic_account_id
        if not account:
            return {}
        account_key = str(account.id)
        for key in self.analytic_distribution or {}:
            key_parts = [item for item in str(key).split(",") if item]
            if account_key in key_parts:
                return {str(key): 100.0}
        return {account_key: 100.0}

    def _aunna_wip_fix_distribution(self):
        for line in self:
            distribution = line._aunna_wip_expected_distribution()
            if not distribution:
                continue
            if line._aunna_wip_normalized_distribution(
                line.analytic_distribution
            ) == line._aunna_wip_normalized_distribution(distribution):
                continue
            line.sudo().with_context(check_move_validity=False).write(
                {"analytic_distribution": distribution}
            )

    def _aunna_wip_normalized_distribution(self, distribution):
        normalized = {}
        for key, value in (distribution or {}).items():
            percentage = self._aunna_wip_distribution_percentage(value)
            if percentage <= 0.0:
                continue
            normalized[str(key)] = percentage
        return normalized

    def _aunna_wip_distribution_percentage(self, value):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _aunna_wip_balance_amount(self):
        self.ensure_one()
        if "balance" in self._fields:
            return self.balance
        debit = self.debit if "debit" in self._fields else 0.0
        credit = self.credit if "credit" in self._fields else 0.0
        return debit - credit

    def _aunna_wip_needs_analytic_rebuild(self, analytic_lines):
        self.ensure_one()
        if not self.analytic_distribution:
            return False
        currency = (self.company_id or self.move_id.company_id).currency_id
        if currency.is_zero(self._aunna_wip_balance_amount()):
            return False
        if not analytic_lines:
            return True
        return not any(
            not currency.is_zero(analytic_line.amount)
            for analytic_line in analytic_lines
        )

    def _aunna_wip_rebuild_analytic_lines(self, analytic_lines):
        self.ensure_one()
        try:
            if hasattr(self, "_create_analytic_lines"):
                analytic_lines.unlink()
                self.with_context(check_move_validity=False)._create_analytic_lines()
                return
            AnalyticAccount = self.env["account.analytic.account"]
            if hasattr(AnalyticAccount, "_perform_analytic_distribution"):
                analytic_lines.unlink()
                AnalyticAccount._perform_analytic_distribution(
                    self.analytic_distribution,
                    self._aunna_wip_balance_amount(),
                    1.0,
                    self.env["account.analytic.line"],
                    self,
                )
        except Exception:
            _logger.exception(
                "No se pudieron reconstruir los apuntes analiticos WIP de %s",
                self.display_name,
            )


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    aunna_wip_calculation_line_id = fields.Many2one(
        "aunna.wip.calculation.line",
        string="Linea calculo WIP",
        copy=False,
        index=True,
        ondelete="set null",
    )
    aunna_wip_project_id = fields.Many2one(
        "project.project",
        string="Proyecto WIP",
        copy=False,
        index=True,
        ondelete="set null",
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        self._aunna_wip_fix_move_line_distributions()
        result = super().action_post()
        self._aunna_wip_link_analytic_lines_to_projects()
        return result

    def _aunna_wip_fix_move_line_distributions(self):
        wip_lines = self.sudo().line_ids.filtered(
            lambda line: line.aunna_wip_calculation_line_id
        )
        wip_lines._aunna_wip_fix_distribution()

    def _aunna_wip_link_analytic_lines_to_projects(self):
        AnalyticLine = self.env["account.analytic.line"].sudo()
        if "move_line_id" not in AnalyticLine._fields:
            return
        project_field = AnalyticLine._fields.get("project_id")
        can_write_standard_project = (
            project_field
            and project_field.type == "many2one"
            and project_field.comodel_name == "project.project"
            and not self.env.context.get("aunna_skip_standard_project_link")
        )
        for move in self.sudo():
            move._aunna_wip_fix_move_line_distributions()
            wip_lines = move.line_ids.filtered(
                lambda line: line.aunna_wip_project_id
                and line.aunna_wip_calculation_line_id
            )
            for move_line in wip_lines:
                analytic_lines = AnalyticLine.search(
                    [("move_line_id", "=", move_line.id)]
                )
                if move_line._aunna_wip_needs_analytic_rebuild(analytic_lines):
                    move_line._aunna_wip_rebuild_analytic_lines(analytic_lines)
                    analytic_lines = AnalyticLine.search(
                        [("move_line_id", "=", move_line.id)]
                    )
                vals = {
                    "aunna_wip_project_id": move_line.aunna_wip_project_id.id,
                    "aunna_wip_calculation_line_id": move_line.aunna_wip_calculation_line_id.id,
                }
                if can_write_standard_project:
                    vals["project_id"] = move_line.aunna_wip_project_id.id
                analytic_lines.write(vals)
