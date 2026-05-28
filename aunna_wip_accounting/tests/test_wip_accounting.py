from odoo.tests.common import TransactionCase


class TestAunnaWipAccounting(TransactionCase):
    def test_settings_model_fields_exist(self):
        settings = self.env["res.config.settings"].new({})
        self.assertIn("aunnna_wip_journal_id", settings._fields)
        self.assertIn("aunnna_wip_income_account_id", settings._fields)
        self.assertIn("aunnna_wip_deferred_account_id", settings._fields)
