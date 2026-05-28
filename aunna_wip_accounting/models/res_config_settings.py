from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    aunnna_wip_journal_id = fields.Many2one(
        "account.journal",
        string="Diario WIP",
        domain="[('type', '=', 'general')]",
        config_parameter="aunna_wip_accounting.journal_id",
    )
    aunnna_wip_income_account_id = fields.Many2one(
        "account.account",
        string="Cuenta ingreso WIP",
        config_parameter="aunna_wip_accounting.income_account_id",
    )
    aunnna_wip_deferred_account_id = fields.Many2one(
        "account.account",
        string="Cuenta ingresos anticipados",
        config_parameter="aunna_wip_accounting.deferred_account_id",
    )
    aunnna_wip_auto_post_moves = fields.Boolean(
        string="Publicar asientos WIP automaticamente",
        config_parameter="aunna_wip_accounting.auto_post_moves",
        default=True,
    )
    aunnna_wip_allow_negative_amounts = fields.Boolean(
        string="Permitir WIP negativo",
        config_parameter="aunna_wip_accounting.allow_negative_amounts",
        default=False,
    )
    aunnna_wip_manual_reversal_days = fields.Integer(
        string="Dias hasta reversion manual",
        config_parameter="aunna_wip_accounting.manual_reversal_days",
        default=1,
    )
