import logging

from odoo import api, fields, models


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

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get("aunna_skip_wip_distribution_force"):
            lines._aunna_wip_force_distribution_from_move()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if (
            not self.env.context.get("aunna_skip_wip_distribution_force")
            and "analytic_distribution" not in vals
        ):
            self._aunna_wip_force_distribution_from_move()
        return result

    def _aunna_wip_force_distribution_from_move(self):
        moves = self.filtered(lambda line: line.move_id).mapped("move_id")
        moves._aunna_wip_force_analytic_distribution_from_calculation()

    def _aunna_wip_expected_distribution(self):
        self.ensure_one()
        account = self._aunna_wip_expected_analytic_account()
        if not account:
            return {}
        return {str(account.id): 100.0}

    def _aunna_wip_expected_analytic_account(self):
        self.ensure_one()
        calc_line = self.aunna_wip_calculation_line_id
        calculation = calc_line.calculation_id
        if calculation and hasattr(calculation, "_aunna_wip_calc_line_analytic_account"):
            account = calculation._aunna_wip_calc_line_analytic_account(calc_line)
            if account:
                return account
        if calc_line.analytic_account_id:
            return calc_line.analytic_account_id
        if calc_line.project_id and "account_id" in calc_line.project_id._fields:
            account = calc_line.project_id.account_id
            if account:
                return account
        return self._aunna_wip_distribution_analytic_account()

    def _aunna_wip_distribution_analytic_account(self):
        self.ensure_one()
        distribution = self._aunna_wip_normalized_distribution(
            self.analytic_distribution
        )
        for key in distribution:
            account_ids = [
                int(item)
                for item in str(key).split(",")
                if item and item.isdigit()
            ]
            account = self.env["account.analytic.account"].browse(
                account_ids[:1]
            ).exists()
            if account:
                return account
        return self.env["account.analytic.account"]

    def _aunna_wip_fix_distribution(self):
        changed_lines = self.env["account.move.line"]
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
            changed_lines |= line
        return changed_lines

    def _aunna_wip_normalized_distribution(self, distribution):
        normalized = {}
        for key, value in (distribution or {}).items():
            percentage = self._aunna_wip_distribution_percentage(value)
            if percentage <= 0.0:
                continue
            normalized[str(key)] = percentage
        return normalized

    def _aunna_wip_distribution_percentage(self, value):
        if isinstance(value, dict):
            for key in ("percentage", "amount", "value"):
                if key in value:
                    return self._aunna_wip_distribution_percentage(value[key])
            if len(value) == 1:
                return self._aunna_wip_distribution_percentage(
                    next(iter(value.values()))
                )
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

    def _aunna_wip_analytic_amount(self):
        self.ensure_one()
        return -self._aunna_wip_balance_amount()

    def _aunna_wip_needs_analytic_rebuild(self, analytic_lines):
        self.ensure_one()
        if not self.analytic_distribution:
            return False
        currency = (self.company_id or self.move_id.company_id).currency_id
        expected_amount = self._aunna_wip_analytic_amount()
        if currency.is_zero(expected_amount):
            return False
        if not analytic_lines:
            return True
        if len(analytic_lines) != 1:
            return True
        return currency.compare_amounts(
            analytic_lines.amount,
            expected_amount,
        ) != 0

    def _aunna_wip_rebuild_analytic_lines(self, analytic_lines):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                analytic_lines.exists().unlink()
                if self._aunna_wip_create_expected_analytic_line():
                    return
        except Exception:
            _logger.exception(
                "No se pudo crear manualmente el apunte analitico WIP de %s",
                self.display_name,
            )

        try:
            with self.env.cr.savepoint():
                analytic_lines.exists().unlink()
                if not hasattr(self, "_create_analytic_lines"):
                    return
                self.with_context(check_move_validity=False)._create_analytic_lines()
        except Exception:
            _logger.exception(
                "No se pudieron reconstruir los apuntes analiticos WIP de %s",
                self.display_name,
            )

    def _aunna_wip_create_expected_analytic_line(self):
        self.ensure_one()
        calc_line = self.aunna_wip_calculation_line_id
        analytic_account = self._aunna_wip_expected_analytic_account()
        if not analytic_account:
            return self.env["account.analytic.line"]

        AnalyticLine = self.env["account.analytic.line"].sudo().with_context(
            aunna_skip_project_cost_moves=True
        )
        if "account_id" not in AnalyticLine._fields:
            return AnalyticLine

        amount = self._aunna_wip_analytic_amount()
        currency = (self.company_id or self.move_id.company_id).currency_id
        if currency.is_zero(amount):
            return AnalyticLine

        move = self.move_id
        vals = {
            "name": self.name or move.ref or move.name or "WIP",
            "account_id": analytic_account.id,
            "amount": amount,
            "date": self.date or move.date or fields.Date.context_today(self),
        }
        optional_values = {
            "company_id": (self.company_id or move.company_id).id,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "general_account_id": self.account_id.id if self.account_id else False,
            "ref": move.ref or move.name,
            "project_id": self.aunna_wip_project_id.id
            if self.aunna_wip_project_id
            else False,
            "aunna_wip_project_id": self.aunna_wip_project_id.id
            if self.aunna_wip_project_id
            else False,
            "aunna_wip_calculation_line_id": calc_line.id,
        }
        for field_name, value in optional_values.items():
            if field_name in AnalyticLine._fields and value not in (False, None):
                vals[field_name] = value
        for field_name in ("move_line_id", "account_move_line_id"):
            if field_name in AnalyticLine._fields:
                vals[field_name] = self.id
                break
        return AnalyticLine.create(vals)


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

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        if not self.env.context.get("aunna_skip_wip_project_link_fix"):
            moves._aunna_wip_tag_from_matching_calculation()
            moves._aunna_wip_force_analytic_distribution_from_calculation()
        return moves

    def action_post(self):
        self._aunna_wip_tag_from_matching_calculation()
        self._aunna_wip_force_analytic_distribution_from_calculation()
        self._aunna_wip_fix_move_line_distributions()
        result = super().action_post()
        self._aunna_wip_force_analytic_distribution_from_calculation()
        self._aunna_wip_link_analytic_lines_to_projects(force_rebuild=True)
        return result

    def _aunna_wip_tag_from_matching_calculation(self):
        for move in self.sudo():
            calculation = move._aunna_wip_find_matching_calculation()
            if calculation:
                calculation.with_context(
                    aunna_skip_wip_project_link_fix=True
                )._aunna_wip_tag_move_lines_from_calculation(move)
        return True

    def _aunna_wip_find_matching_calculation(self):
        self.ensure_one()
        Calculation = self.env["aunna.wip.calculation"].sudo()
        refs = []
        for value in (self.ref, self.name):
            if not value:
                continue
            refs.append(value)
            if value.startswith("WIP "):
                refs.append(value[4:])
        refs = [value for value in dict.fromkeys(refs) if value]
        if not refs:
            return Calculation
        return Calculation.search(
            [
                ("name", "in", refs),
                ("company_id", "=", self.company_id.id),
            ],
            order="id desc",
            limit=1,
        )

    def _aunna_wip_force_analytic_distribution_from_calculation(self):
        for move in self.sudo():
            calculation = move._aunna_wip_find_matching_calculation()
            if not calculation:
                continue
            settings = calculation._aunna_wip_accounting_settings(
                calculation.company_id
            )
            income_account = settings.get("income_account")
            if not income_account:
                continue
            used_line_ids = set()
            income_lines = move.line_ids.filtered(
                lambda line: line.account_id == income_account
            )
            for move_line in income_lines:
                calc_line = calculation._aunna_wip_match_move_line_to_calc_line(
                    calculation._aunna_wip_project_candidate_lines(),
                    used_line_ids,
                    move_line.analytic_distribution,
                    self._aunna_wip_move_line_abs_amount(move_line),
                )
                if not calc_line:
                    continue
                used_line_ids.add(calc_line.id)
                analytic_account = calculation._aunna_wip_calc_line_analytic_account(
                    calc_line
                )
                if not analytic_account:
                    continue
                distribution = {str(analytic_account.id): 100.0}
                vals = {
                    "analytic_distribution": distribution,
                    "aunna_wip_calculation_line_id": calc_line.id,
                }
                project = calculation._aunna_wip_calc_line_project(calc_line)
                if project:
                    vals["aunna_wip_project_id"] = project.id
                move_line.with_context(
                    aunna_skip_wip_distribution_force=True,
                    check_move_validity=False,
                ).write(vals)
        return True

    def _aunna_wip_move_line_abs_amount(self, move_line):
        if "balance" in move_line._fields:
            return abs(move_line.balance)
        return abs((move_line.debit or 0.0) - (move_line.credit or 0.0))

    def _aunna_wip_fix_move_line_distributions(self):
        wip_lines = self.sudo().line_ids.filtered(
            lambda line: line.aunna_wip_calculation_line_id
        )
        return wip_lines._aunna_wip_fix_distribution()

    def _aunna_wip_link_analytic_lines_to_projects(self, force_rebuild=False):
        AnalyticLine = self.env["account.analytic.line"].sudo().with_context(
            aunna_skip_project_cost_moves=True
        )
        move_line_field = self._aunna_wip_analytic_move_line_field(AnalyticLine)
        if not move_line_field:
            return
        project_field = AnalyticLine._fields.get("project_id")
        can_write_standard_project = (
            project_field
            and project_field.type == "many2one"
            and project_field.comodel_name == "project.project"
            and not self.env.context.get("aunna_skip_standard_project_link")
        )
        for move in self.sudo():
            changed_lines = move._aunna_wip_fix_move_line_distributions()
            wip_lines = move.line_ids.filtered(
                lambda line: line.aunna_wip_calculation_line_id
                and line.analytic_distribution
            )
            for move_line in wip_lines:
                analytic_lines = AnalyticLine.search(
                    [(move_line_field, "=", move_line.id)]
                )
                if (
                    force_rebuild
                    or move_line in changed_lines
                    or move_line._aunna_wip_needs_analytic_rebuild(analytic_lines)
                ):
                    move_line._aunna_wip_rebuild_analytic_lines(analytic_lines)
                    analytic_lines = AnalyticLine.search(
                        [(move_line_field, "=", move_line.id)]
                    )
                vals = {
                    "aunna_wip_calculation_line_id": move_line.aunna_wip_calculation_line_id.id,
                }
                if move_line.aunna_wip_project_id:
                    vals["aunna_wip_project_id"] = move_line.aunna_wip_project_id.id
                    if can_write_standard_project:
                        vals["project_id"] = move_line.aunna_wip_project_id.id
                analytic_lines.write(vals)

    def _aunna_wip_analytic_move_line_field(self, AnalyticLine):
        for field_name in ("move_line_id", "account_move_line_id"):
            field = AnalyticLine._fields.get(field_name)
            if (
                field
                and field.type == "many2one"
                and field.comodel_name == "account.move.line"
            ):
                return field_name
        return False
