from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    aunnna_wip_journal_id = fields.Many2one(
        "account.journal",
        string="Diario WIP",
        domain="[('type', '=', 'general')]",
    )
    aunnna_wip_income_account_id = fields.Many2one(
        "account.account",
        string="Cuenta ingreso WIP",
    )
    aunnna_wip_deferred_account_id = fields.Many2one(
        "account.account",
        string="Cuenta ingresos anticipados",
    )
    aunnna_wip_auto_post_moves = fields.Boolean(
        string="Publicar asientos WIP automaticamente",
        default=True,
    )
    aunnna_wip_auto_accounting_enabled = fields.Boolean(
        string="Habilitar contabilizacion automatica del WIP",
    )
    aunnna_wip_auto_accounting_grace_days = fields.Integer(
        string="Dias de espera para contabilizacion automatica",
        default=5,
    )
    aunnna_wip_allow_negative_amounts = fields.Boolean(
        string="Permitir WIP negativo",
    )

    @api.constrains("aunnna_wip_journal_id")
    def _check_aunnna_wip_journal_id(self):
        for company in self:
            journal = company.aunnna_wip_journal_id
            if journal and journal.type != "general":
                raise ValidationError(_("El diario WIP debe ser de tipo Miscelanea."))
            if journal and journal.company_id != company:
                raise ValidationError(
                    _("El diario WIP debe pertenecer a la compania %s.")
                    % company.display_name
                )

    @api.constrains(
        "aunnna_wip_auto_accounting_enabled",
        "aunnna_wip_auto_accounting_grace_days",
    )
    def _check_aunnna_wip_auto_accounting_grace_days(self):
        for company in self:
            if (
                company.aunnna_wip_auto_accounting_enabled
                and not 1 <= company.aunnna_wip_auto_accounting_grace_days <= 28
            ):
                raise ValidationError(
                    _("Los dias de espera para contabilizacion automatica deben estar entre 1 y 28.")
                )
