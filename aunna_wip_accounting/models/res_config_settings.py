from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
    aunnna_wip_auto_accounting_enabled = fields.Boolean(
        string="Habilitar contabilizacion automatica del WIP",
        config_parameter="aunna_wip_accounting.auto_accounting_enabled",
        default=False,
    )
    aunnna_wip_auto_accounting_grace_days = fields.Integer(
        string="Dias de espera para contabilizacion automatica",
        config_parameter="aunna_wip_accounting.auto_accounting_grace_days",
        default=5,
    )
    aunnna_wip_allow_negative_amounts = fields.Boolean(
        string="Permitir WIP negativo",
        config_parameter="aunna_wip_accounting.allow_negative_amounts",
        default=False,
    )

    def action_open_aunnna_wip_auto_test_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Probar contabilizacion automatica WIP"),
            "res_model": "aunna.wip.auto.test.wizard",
            "view_mode": "form",
            "target": "new",
        }

    @api.constrains(
        "aunnna_wip_auto_accounting_enabled",
        "aunnna_wip_auto_accounting_grace_days",
    )
    def _check_aunnna_wip_auto_accounting_grace_days(self):
        for settings in self:
            if (
                settings.aunnna_wip_auto_accounting_enabled
                and not 1 <= settings.aunnna_wip_auto_accounting_grace_days <= 28
            ):
                raise ValidationError(
                    _("Los dias de espera para contabilizacion automatica deben estar entre 1 y 28.")
                )
