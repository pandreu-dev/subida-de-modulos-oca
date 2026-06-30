from odoo import fields, models


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
        result = super().action_post()
        self._aunna_wip_link_analytic_lines_to_projects()
        return result

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
            wip_lines = move.line_ids.filtered(
                lambda line: line.aunna_wip_project_id
                and line.aunna_wip_calculation_line_id
            )
            for move_line in wip_lines:
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
