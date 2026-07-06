from odoo import models


class AunnaWipCalculation(models.Model):
    _inherit = "aunna.wip.calculation"

    def _aunna_wip_prepare_move_vals(self, settings):
        move_vals = super()._aunna_wip_prepare_move_vals(settings)
        if not move_vals:
            return move_vals

        candidate_lines = self._aunna_wip_project_candidate_lines()
        used_line_ids = set()
        for command in move_vals.get("line_ids", []):
            if len(command) < 3 or not isinstance(command[2], dict):
                continue
            vals = command[2]
            distribution = vals.get("analytic_distribution") or {}
            if not distribution:
                continue
            calc_line = self._aunna_wip_match_move_line_to_calc_line(
                candidate_lines,
                used_line_ids,
                distribution,
            )
            if not calc_line:
                continue
            used_line_ids.add(calc_line.id)
            vals["analytic_distribution"] = self._aunna_wip_distribution_for_calc_line(
                distribution,
                calc_line,
            )
            vals["aunna_wip_project_id"] = calc_line.project_id.id or False
            vals["aunna_wip_calculation_line_id"] = calc_line.id
        return move_vals

    def _aunna_wip_project_candidate_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.wip_amount
            and line.analytic_account_id
        )

    def _aunna_wip_match_move_line_to_calc_line(self, lines, used_line_ids, distribution):
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
            if line.analytic_account_id.id in distribution_ids:
                return line
        for line in lines:
            if line.id not in used_line_ids:
                return line
        return self.env["aunna.wip.calculation.line"]

    def _aunna_wip_distribution_for_calc_line(self, distribution, calc_line):
        account_key = str(calc_line.analytic_account_id.id)
        return {account_key: 100.0}

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
                )
            if not calc_line:
                continue
            used_line_ids.add(calc_line.id)
            vals = {}
            if move_line.aunna_wip_project_id != calc_line.project_id:
                vals["aunna_wip_project_id"] = calc_line.project_id.id or False
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
