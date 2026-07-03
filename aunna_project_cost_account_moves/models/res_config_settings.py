from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    aunna_cost_move_journal_id = fields.Many2one(
        related="company_id.aunna_cost_move_journal_id",
        readonly=False,
    )
    aunna_timesheet_cost_account_id = fields.Many2one(
        related="company_id.aunna_timesheet_cost_account_id",
        readonly=False,
    )
    aunna_timesheet_counterpart_account_id = fields.Many2one(
        related="company_id.aunna_timesheet_counterpart_account_id",
        readonly=False,
    )
    aunna_stock_cost_account_id = fields.Many2one(
        related="company_id.aunna_stock_cost_account_id",
        readonly=False,
    )
    aunna_stock_counterpart_account_id = fields.Many2one(
        related="company_id.aunna_stock_counterpart_account_id",
        readonly=False,
    )
    aunna_enable_timesheet_cost_moves = fields.Boolean(
        related="company_id.aunna_enable_timesheet_cost_moves",
        readonly=False,
    )
    aunna_enable_stock_delivery_cost_moves = fields.Boolean(
        related="company_id.aunna_enable_stock_delivery_cost_moves",
        readonly=False,
    )
    aunna_auto_post_cost_moves = fields.Boolean(
        related="company_id.aunna_auto_post_cost_moves",
        readonly=False,
    )
    aunna_default_timesheet_pl_analytic_account_id = fields.Many2one(
        related="company_id.aunna_default_timesheet_pl_analytic_account_id",
        readonly=False,
    )
    aunna_default_stock_pl_analytic_account_id = fields.Many2one(
        related="company_id.aunna_default_stock_pl_analytic_account_id",
        readonly=False,
    )

    def action_aunna_generate_project_cost_moves(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        result = (
            self.env["aunna.project.cost.move.link"]
            .with_company(company)
            ._aunna_generate_pending(company=company)
        )
        message = (
            "%(company)s - Horas: %(timesheet)s. Entregas: %(stock)s. Errores: %(errors)s."
            % {**result, "company": company.display_name}
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Costes tecnicos de proyecto",
                "message": message,
                "type": "success" if not result["errors"] else "warning",
                "sticky": False,
            },
        }
