from odoo.tests.common import TransactionCase


class TestAunnaWipAccounting(TransactionCase):
    def test_settings_model_fields_exist(self):
        settings = self.env["res.config.settings"].new({})
        self.assertIn("aunnna_wip_journal_id", settings._fields)
        self.assertIn("aunnna_wip_income_account_id", settings._fields)
        self.assertIn("aunnna_wip_deferred_account_id", settings._fields)
        self.assertIn("aunnna_wip_auto_accounting_enabled", settings._fields)
        self.assertIn("aunnna_wip_auto_accounting_grace_days", settings._fields)

    def test_settings_are_read_from_company(self):
        self.env.company.aunnna_wip_auto_accounting_grace_days = 7
        settings = self.env["aunna.wip.calculation"]._aunna_wip_accounting_settings(
            self.env.company
        )
        self.assertEqual(settings["company"].id, self.env.company.id)
        self.assertEqual(settings["auto_accounting_grace_days"], 7)

    def test_empty_grace_days_uses_default(self):
        self.env.company.aunnna_wip_auto_accounting_grace_days = 0
        settings = self.env["aunna.wip.calculation"]._aunna_wip_accounting_settings(
            self.env.company
        )
        self.assertEqual(settings["auto_accounting_grace_days"], 5)
