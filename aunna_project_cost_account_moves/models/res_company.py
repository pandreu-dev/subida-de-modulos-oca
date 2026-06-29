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
    aunna_group_cost_moves = fields.Boolean(
        string="Agrupar costes tecnicos",
        help="Reservado para agrupacion futura. Actualmente se genera un asiento por origen.",
    )
    aunna_default_timesheet_pl_analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="P&L defecto horas",
    )
    aunna_default_stock_pl_analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="P&L defecto stock",
    )
