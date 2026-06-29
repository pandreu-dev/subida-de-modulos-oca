from odoo import models


class AunnaWipCalculation(models.Model):
    _inherit = "aunna.wip.calculation"

    def _aunna_wip_prepare_move_vals(self, settings):
        move_vals = super()._aunna_wip_prepare_move_vals(settings)
        if not move_vals:
            return move_vals

        candidate_lines = [
            line
            for line in self.line_ids
            if line.wip_amount
            and line.analytic_account_id
            and line.project_id
        ]
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
            vals["aunna_wip_project_id"] = calc_line.project_id.id
            vals["aunna_wip_calculation_line_id"] = calc_line.id
        return move_vals

    def _aunna_wip_match_move_line_to_calc_line(self, lines, used_line_ids, distribution):
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

    def action_create_wip_move(self, reversal_date=False):
        result = super().action_create_wip_move(reversal_date=reversal_date)
        moves = self.mapped("move_id") | self.mapped("reversal_move_id")
        moves._aunna_wip_link_analytic_lines_to_projects()
        return result

    def _aunna_wip_create_native_reversal(self, move, reversal_date, settings):
        reversal_move = super()._aunna_wip_create_native_reversal(
            move,
            reversal_date,
            settings,
        )
        self._aunna_wip_copy_project_link_to_reversal_lines(move, reversal_move)
        reversal_move._aunna_wip_link_analytic_lines_to_projects()
        return reversal_move

    def _aunna_wip_copy_project_link_to_reversal_lines(self, move, reversal_move):
        used_reversal_line_ids = set()
        source_lines = move.line_ids.filtered(
            lambda line: line.aunna_wip_project_id
            and line.aunna_wip_calculation_line_id
        )
        for source_line in source_lines:
            reversal_line = reversal_move.line_ids.filtered(
                lambda line: line.id not in used_reversal_line_ids
                and line.account_id == source_line.account_id
                and not line.aunna_wip_project_id
            )[:1]
            if not reversal_line:
                continue
            used_reversal_line_ids.add(reversal_line.id)
            reversal_line.sudo().write(
                {
                    "aunna_wip_project_id": source_line.aunna_wip_project_id.id,
                    "aunna_wip_calculation_line_id": source_line.aunna_wip_calculation_line_id.id,
                }
            )
