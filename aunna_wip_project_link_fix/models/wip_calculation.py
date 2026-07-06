from odoo import models


class AunnaWipCalculation(models.Model):
    _inherit = "aunna.wip.calculation"

    def _aunna_wip_prepare_move_vals(self, settings):
        move_vals = super()._aunna_wip_prepare_move_vals(settings)
        if not move_vals:
            return move_vals

        candidate_lines = self._aunna_wip_project_candidate_lines()
        income_account = settings.get("income_account")
        used_line_ids = set()
        for command in move_vals.get("line_ids", []):
            if len(command) < 3 or not isinstance(command[2], dict):
                continue
            vals = command[2]
            distribution = vals.get("analytic_distribution") or {}
            is_wip_income_line = (
                income_account
                and vals.get("account_id") == income_account.id
            )
            if not distribution and not is_wip_income_line:
                continue
            line_amount = abs(vals.get("debit") or vals.get("credit") or 0.0)
            calc_line = self._aunna_wip_match_move_line_to_calc_line(
                candidate_lines,
                used_line_ids,
                distribution,
                line_amount,
            )
            if not calc_line:
                continue
            used_line_ids.add(calc_line.id)
            vals["analytic_distribution"] = self._aunna_wip_distribution_for_calc_line(
                distribution,
                calc_line,
            )
            project = self._aunna_wip_calc_line_project(calc_line)
            vals["aunna_wip_project_id"] = project.id or False
            vals["aunna_wip_calculation_line_id"] = calc_line.id
        return move_vals

    def _aunna_wip_project_candidate_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.wip_amount
            and self._aunna_wip_calc_line_analytic_account(line)
        )

    def _aunna_wip_line_analytic_distribution(self, line):
        distribution = self._aunna_wip_distribution_for_calc_line(False, line)
        return distribution or super()._aunna_wip_line_analytic_distribution(line)

    def _aunna_wip_calc_line_analytic_account(self, calc_line):
        if calc_line.analytic_account_id:
            return calc_line.analytic_account_id
        project = calc_line.project_id
        if project and "account_id" in project._fields:
            account = project.account_id
            if account:
                return account
        source = self._aunna_wip_calc_line_source_record(calc_line)
        return self._aunna_wip_analytic_account_from_record(source)

    def _aunna_wip_calc_line_project(self, calc_line):
        if calc_line.project_id:
            return calc_line.project_id
        source = self._aunna_wip_calc_line_source_record(calc_line)
        return self._aunna_wip_project_from_record(source)

    def _aunna_wip_calc_line_source_record(self, calc_line):
        if not calc_line.budget_line_model or not calc_line.budget_line_res_id:
            return self.env["account.analytic.account"]
        try:
            return self.env[calc_line.budget_line_model].browse(
                calc_line.budget_line_res_id
            ).exists()
        except KeyError:
            return self.env["account.analytic.account"]

    def _aunna_wip_project_from_record(self, record):
        if not record or "project.project" not in self.env.registry:
            return self.env["project.project"]
        if "project_id" in record._fields and record.project_id:
            return record.project_id
        account = self._aunna_wip_analytic_account_from_record(record)
        if not account:
            return self.env["project.project"]
        Project = self.env["project.project"].sudo()
        for field_name, field in Project._fields.items():
            if (
                field.type == "many2one"
                and getattr(field, "comodel_name", False) == "account.analytic.account"
            ):
                project = Project.search([(field_name, "=", account.id)], limit=1)
                if project:
                    return project
        return self.env["project.project"]

    def _aunna_wip_analytic_account_from_record(self, record):
        if not record:
            return self.env["account.analytic.account"]
        for field_name in ("analytic_account_id", "account_id"):
            field = record._fields.get(field_name)
            if (
                field
                and field.type == "many2one"
                and getattr(field, "comodel_name", False) == "account.analytic.account"
                and record[field_name]
            ):
                return record[field_name]
        accounts = self.env["account.analytic.account"]
        for field_name, field in record._fields.items():
            if getattr(field, "comodel_name", False) != "account.analytic.account":
                continue
            if field.type == "many2one" and record[field_name]:
                accounts |= record[field_name]
            elif field.type == "many2many" and record[field_name]:
                accounts |= record[field_name]
        if len(accounts) == 1:
            return accounts
        return self.env["account.analytic.account"]

    def _aunna_wip_match_move_line_to_calc_line(
        self,
        lines,
        used_line_ids,
        distribution,
        amount=False,
    ):
        distribution = distribution or {}
        distribution_ids = set()
        for key in distribution:
            distribution_ids.update(
                int(item)
                for item in str(key).split(",")
                if item and item.isdigit()
            )
        for line in lines:
            if line.id in used_line_ids:
                continue
            if self._aunna_wip_calc_line_analytic_account(line).id in distribution_ids:
                return line
        if amount:
            currency = self.company_id.currency_id
            for line in lines:
                if line.id in used_line_ids:
                    continue
                if not currency.compare_amounts(abs(line.wip_amount), abs(amount)):
                    return line
        for line in lines:
            if line.id not in used_line_ids:
                return line
        return self.env["aunna.wip.calculation.line"]

    def _aunna_wip_distribution_for_calc_line(self, distribution, calc_line):
        account = self._aunna_wip_calc_line_analytic_account(calc_line)
        if not account:
            return {}
        return {account.id: 100.0}

    def _aunna_wip_distribution_percentage(self, value):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def action_create_wip_move(self, reversal_date=False):
        result = super().action_create_wip_move(reversal_date=reversal_date)
        self._aunna_wip_tag_calculation_moves_to_projects()
        return result

    def _aunna_wip_create_native_reversal(self, move, reversal_date, settings):
        reversal_move = super()._aunna_wip_create_native_reversal(
            move,
            reversal_date,
            settings,
        )
        self._aunna_wip_tag_move_lines_from_calculation(reversal_move)
        self._aunna_wip_copy_project_link_to_reversal_lines(move, reversal_move)
        reversal_move._aunna_wip_link_analytic_lines_to_projects(force_rebuild=True)
        return reversal_move

    def action_open_wip_move(self):
        self._aunna_wip_tag_calculation_moves_to_projects()
        return super().action_open_wip_move()

    def action_open_reversal_move(self):
        self._aunna_wip_tag_calculation_moves_to_projects()
        return super().action_open_reversal_move()

    def _aunna_wip_tag_calculation_moves_to_projects(self):
        for calculation in self:
            moves = calculation.move_id | calculation.reversal_move_id
            for move in moves:
                calculation._aunna_wip_tag_move_lines_from_calculation(move)
            moves._aunna_wip_link_analytic_lines_to_projects(force_rebuild=True)
        return True

    def _aunna_wip_tag_move_lines_from_calculation(self, move):
        self.ensure_one()
        if not move:
            return
        candidate_lines = self._aunna_wip_project_candidate_lines()
        if not candidate_lines:
            return
        settings = self._aunna_wip_accounting_settings(self.company_id)
        income_account = settings.get("income_account")
        candidate_line_ids = set(candidate_lines.ids)
        used_line_ids = set(move.line_ids.mapped("aunna_wip_calculation_line_id").ids)
        move_lines = move.line_ids.filtered(
            lambda line: line.analytic_distribution
            or line.aunna_wip_calculation_line_id
            or (income_account and line.account_id == income_account)
            or self._aunna_wip_is_income_move_line(line)
        )
        for move_line in move_lines:
            calc_line = move_line.aunna_wip_calculation_line_id
            if calc_line and calc_line.id not in candidate_line_ids:
                calc_line = self.env["aunna.wip.calculation.line"]
            if not calc_line:
                calc_line = self._aunna_wip_match_move_line_to_calc_line(
                    candidate_lines,
                    used_line_ids,
                    move_line.analytic_distribution,
                    self._aunna_wip_move_line_abs_amount(move_line),
                )
            if not calc_line:
                continue
            used_line_ids.add(calc_line.id)
            vals = {}
            project = self._aunna_wip_calc_line_project(calc_line)
            if move_line.aunna_wip_project_id != project:
                vals["aunna_wip_project_id"] = project.id or False
            if move_line.aunna_wip_calculation_line_id != calc_line:
                vals["aunna_wip_calculation_line_id"] = calc_line.id
            distribution = self._aunna_wip_distribution_for_calc_line(
                move_line.analytic_distribution,
                calc_line,
            )
            if not self._aunna_wip_same_distribution(
                move_line.analytic_distribution,
                distribution,
            ):
                vals["analytic_distribution"] = distribution
            if vals:
                move_line.sudo().with_context(check_move_validity=False).write(vals)

    def _aunna_wip_is_income_move_line(self, move_line):
        account = move_line.account_id
        if not account:
            return False
        amount = self._aunna_wip_move_line_abs_amount(move_line)
        if not amount:
            return False
        account_type = account.account_type if "account_type" in account._fields else ""
        if account_type in ("income", "income_other"):
            return True
        code = account.code if "code" in account._fields else ""
        return bool(code and code.startswith("7"))

    def _aunna_wip_move_line_abs_amount(self, move_line):
        if "balance" in move_line._fields:
            return abs(move_line.balance)
        return abs((move_line.debit or 0.0) - (move_line.credit or 0.0))

    def _aunna_wip_copy_project_link_to_reversal_lines(self, move, reversal_move):
        used_reversal_line_ids = set()
        source_lines = move.line_ids.filtered(
            lambda line: line.aunna_wip_project_id
            and line.aunna_wip_calculation_line_id
        )
        for source_line in source_lines:
            reversal_line = self._aunna_wip_find_reversal_line(
                source_line,
                reversal_move.line_ids,
                used_reversal_line_ids,
            )
            if not reversal_line:
                continue
            used_reversal_line_ids.add(reversal_line.id)
            reversal_line.sudo().with_context(check_move_validity=False).write(
                {
                    "aunna_wip_project_id": source_line.aunna_wip_project_id.id,
                    "aunna_wip_calculation_line_id": source_line.aunna_wip_calculation_line_id.id,
                    "analytic_distribution": self._aunna_wip_distribution_for_calc_line(
                        reversal_line.analytic_distribution,
                        source_line.aunna_wip_calculation_line_id,
                    ),
                }
            )

    def _aunna_wip_find_reversal_line(self, source_line, reversal_lines, used_line_ids):
        candidates = reversal_lines.filtered(
            lambda line: line.id not in used_line_ids
            and line.account_id == source_line.account_id
            and not line.aunna_wip_project_id
        )
        if not candidates:
            return candidates
        same_distribution = candidates.filtered(
            lambda line: self._aunna_wip_same_distribution(
                line.analytic_distribution,
                source_line.analytic_distribution,
            )
        )
        return same_distribution[:1] or candidates[:1]

    def _aunna_wip_same_distribution(self, first, second):
        return self._aunna_wip_normalized_distribution(
            first
        ) == self._aunna_wip_normalized_distribution(second)

    def _aunna_wip_normalized_distribution(self, distribution):
        normalized = {}
        for key, value in (distribution or {}).items():
            percentage = self._aunna_wip_distribution_percentage(value)
            if percentage <= 0.0:
                continue
            normalized[str(key)] = percentage
        return normalized
