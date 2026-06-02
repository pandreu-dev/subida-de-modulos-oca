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

    def test_theoretical_adjustment_recalculates_wip(self):
        line = self.env["aunna.wip.calculation.line"].new(
            {
                "calculated_theoretical_amount": 1000.0,
                "theoretical_amount": 1000.0,
                "achieved_amount": 400.0,
                "calculated_wip_amount": 600.0,
                "wip_amount": 600.0,
            }
        )
        line.theoretical_amount = 900.0
        line._onchange_theoretical_amount()
        self.assertAlmostEqual(line.wip_amount, 500.0)
