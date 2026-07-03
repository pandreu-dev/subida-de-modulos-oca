from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    aunna_cost_move_journal_id = fields.Many2one(
        "account.journal",
        string="Diario costes tecnicos",
        check_company=True,
    )
    aunna_timesheet_cost_account_id = fields.Many2one(
        "account.account",
        string="Cuenta coste horas",
    )
    aunna_timesheet_counterpart_account_id = fields.Many2one(
        "account.account",
        string="Contrapartida coste horas",
    )
    aunna_stock_cost_account_id = fields.Many2one(
        "account.account",
        string="Cuenta coste stock",
    )
    aunna_stock_counterpart_account_id = fields.Many2one(
        "account.account",
        string="Contrapartida coste stock",
    )
    aunna_enable_timesheet_cost_moves = fields.Boolean(
        string="Generar costes tecnicos de horas",
    )
    aunna_enable_stock_delivery_cost_moves = fields.Boolean(
        string="Generar costes tecnicos de entregas",
    )
    aunna_auto_post_cost_moves = fields.Boolean(
        string="Publicar asientos tecnicos automaticamente",
        default=True,
    )
    aunna_timesheet_pl_plan_id = fields.Many2one(
        "account.analytic.plan",
        string="Plan analitico horas",
    )
    aunna_default_timesheet_pl_analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Valor P&L horas",
    )
    aunna_stock_pl_plan_id = fields.Many2one(
        "account.analytic.plan",
        string="Plan analitico stock",
    )
    aunna_default_stock_pl_analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Valor P&L stock",
    )

    def _aunna_project_cost_timesheet_plan_account(self):
        self.ensure_one()
        return self._aunna_project_cost_plan_account(
            self.aunna_default_timesheet_pl_analytic_account_id,
            self.aunna_timesheet_pl_plan_id,
        )

    def _aunna_project_cost_stock_plan_account(self):
        self.ensure_one()
        return self._aunna_project_cost_plan_account(
            self.aunna_default_stock_pl_analytic_account_id,
            self.aunna_stock_pl_plan_id,
        )

    def _aunna_project_cost_plan_account(self, account, plan):
        self.ensure_one()
        if not account or not plan:
            return self.env["account.analytic.account"]
        if self._aunna_project_cost_account_plan(account) != plan:
            return self.env["account.analytic.account"]
        return account

    def _aunna_project_cost_account_plan(self, account):
        if "plan_id" in account._fields and account.plan_id:
            return account.plan_id
        if "root_plan_id" in account._fields and account.root_plan_id:
            return account.root_plan_id
        return self.env["account.analytic.plan"]
