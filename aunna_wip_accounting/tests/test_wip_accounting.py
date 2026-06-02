from odoo.tests.common import TransactionCase


class TestAunnaWipAccounting(TransactionCase):
    def test_settings_model_fields_exist(self):
        settings = self.env["res.config.settings"].new({})
        self.assertIn("aunnna_wip_journal_id", settings._fields)
        self.assertIn("aunnna_wip_income_account_id", settings._fields)
        self.assertIn("aunnna_wip_deferred_account_id", settings._fields)
        self.assertIn("aunnna_wip_auto_accounting_enabled", settings._fields)
        self.assertIn("aunnna_wip_auto_accounting_grace_days", settings._fields)

    def test_invalid_grace_days_parameter_uses_default(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "aunna_wip_accounting.auto_accounting_grace_days",
            "valor-invalido",
        )
        settings = self.env["aunna.wip.calculation"]._aunna_wip_accounting_settings()
        self.assertEqual(settings["auto_accounting_grace_days"], 5)
