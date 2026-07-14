from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    aunnna_wip_journal_id = fields.Many2one(
        related="company_id.aunnna_wip_journal_id",
        readonly=False,
        string="Diario WIP",
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
    )
    aunnna_wip_income_account_id = fields.Many2one(
        related="company_id.aunnna_wip_income_account_id",
        readonly=False,
        string="Cuenta ingreso avance",
    )
    aunnna_wip_deferred_account_id = fields.Many2one(
        related="company_id.aunnna_wip_deferred_account_id",
        readonly=False,
        string="Cuenta ingresos anticipados",
    )
    aunnna_wip_auto_post_moves = fields.Boolean(
        related="company_id.aunnna_wip_auto_post_moves",
        readonly=False,
        string="Publicar asientos de avance automaticamente",
    )
    aunnna_wip_auto_accounting_enabled = fields.Boolean(
        related="company_id.aunnna_wip_auto_accounting_enabled",
        readonly=False,
        string="Habilitar contabilizacion automatica del avance",
    )
    aunnna_wip_auto_accounting_grace_days = fields.Integer(
        related="company_id.aunnna_wip_auto_accounting_grace_days",
        readonly=False,
        string="Dias de espera para contabilizacion automatica",
    )
    aunnna_wip_allow_negative_amounts = fields.Boolean(
        related="company_id.aunnna_wip_allow_negative_amounts",
        readonly=False,
        string="Permitir avance negativo",
    )

    def action_open_aunnna_wip_auto_test_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Probar contabilizacion automatica de avance"),
            "res_model": "aunna.wip.auto.test.wizard",
            "view_mode": "form",
            "target": "new",
        }
