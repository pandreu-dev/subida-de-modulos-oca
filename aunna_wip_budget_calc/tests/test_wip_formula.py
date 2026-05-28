from datetime import date

from odoo.tests.common import TransactionCase


class TestAunnaWipFormula(TransactionCase):
    def test_theoretical_proration(self):
        budget = self.env["budget.analytic"].new({})
        amount = budget._aunna_wip_compute_theoretical_amount(
            3100.0,
            date(2026, 5, 1),
            date(2026, 5, 31),
            date(2026, 5, 15),
        )
        self.assertAlmostEqual(amount, 1500.0)
