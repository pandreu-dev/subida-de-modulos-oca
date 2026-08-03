from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSubscriptionInvoiceInArrears(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Plan = cls.env["sale.subscription.plan"]
        cls.Order = cls.env["sale.order"]
        cls.partner = cls.env["res.partner"].create({"name": "Cliente pruebas vencido"})

    def _create_plan(self, name, value=1, unit="month", arrears=True, aligned=False):
        vals = {"name": name, "invoice_in_arrears": arrears}
        if "billing_period_value" in self.Plan._fields:
            vals["billing_period_value"] = value
        if "billing_period_unit" in self.Plan._fields:
            vals["billing_period_unit"] = unit
        if "billing_first_day" in self.Plan._fields:
            vals["billing_first_day"] = aligned
        return self.Plan.create(vals)

    def _create_order(self, plan, start, next_invoice):
        vals = {
            "partner_id": self.partner.id,
            "plan_id": plan.id,
        }
        for field_name in ("start_date", "subscription_start_date", "date_start"):
            if field_name in self.Order._fields:
                vals[field_name] = start
                break
        if "next_invoice_date" in self.Order._fields:
            vals["next_invoice_date"] = next_invoice
        return self.Order.create(vals)

    def test_01_standard_plan_is_not_touched(self):
        plan = self._create_plan("Mensual normal", arrears=False)
        order = self._create_order(plan, date(2026, 7, 1), date(2026, 7, 1))

        order._ensure_invoice_in_arrears_initialized()

        self.assertFalse(order.invoice_in_arrears_initialized)
        self.assertEqual(order.next_invoice_date, date(2026, 7, 1))

    def test_02_monthly_first_cycle_is_shifted_to_period_end(self):
        plan = self._create_plan("Mensual vencido")
        order = self._create_order(plan, date(2026, 7, 1), date(2026, 7, 1))

        order._ensure_invoice_in_arrears_initialized()
        period_start, period_end = order._get_invoice_in_arrears_period(date(2026, 8, 1))

        self.assertEqual(order.next_invoice_date, date(2026, 8, 1))
        self.assertEqual(period_start, date(2026, 7, 1))
        self.assertEqual(period_end, date(2026, 7, 31))
        self.assertEqual(order._add_invoice_in_arrears_period(date(2026, 8, 1)), date(2026, 9, 1))

    def test_03_second_cycle_does_not_duplicate_previous_month(self):
        plan = self._create_plan("Mensual vencido segundo ciclo")
        order = self._create_order(plan, date(2026, 7, 1), date(2026, 9, 1))
        order._mark_invoice_in_arrears_period(date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 1))

        period_start, period_end = order._get_invoice_in_arrears_period(date(2026, 9, 1))

        self.assertEqual(period_start, date(2026, 8, 1))
        self.assertEqual(period_end, date(2026, 8, 31))

    def test_04_next_invoice_date_is_advanced_only_if_standard_did_not(self):
        plan = self._create_plan("Mensual avance seguro")
        order = self._create_order(plan, date(2026, 7, 1), date(2026, 8, 1))

        order._mark_invoice_in_arrears_period(date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 1))

        self.assertEqual(order.next_invoice_date, date(2026, 9, 1))

        order._mark_invoice_in_arrears_period(date(2026, 8, 1), date(2026, 8, 31), date(2026, 8, 1))

        self.assertEqual(order.next_invoice_date, date(2026, 9, 1))

    def test_05_year_boundary(self):
        plan = self._create_plan("Mensual cambio anno")
        order = self._create_order(plan, date(2026, 12, 1), date(2027, 1, 1))

        period_start, period_end = order._get_invoice_in_arrears_period(date(2027, 1, 1))

        self.assertEqual(period_start, date(2026, 12, 1))
        self.assertEqual(period_end, date(2026, 12, 31))

    def test_06_february_leap_and_non_leap_years(self):
        plan = self._create_plan("Mensual febrero")
        leap_order = self._create_order(plan, date(2028, 2, 1), date(2028, 3, 1))
        regular_order = self._create_order(plan, date(2027, 2, 1), date(2027, 3, 1))

        self.assertEqual(
            leap_order._get_invoice_in_arrears_period(date(2028, 3, 1)),
            (date(2028, 2, 1), date(2028, 2, 29)),
        )
        self.assertEqual(
            regular_order._get_invoice_in_arrears_period(date(2027, 3, 1)),
            (date(2027, 2, 1), date(2027, 2, 28)),
        )

    def test_07_quarterly_and_annual_periods(self):
        quarterly = self._create_plan("Trimestral vencido", value=3, unit="month")
        annual = self._create_plan("Anual vencido", value=1, unit="year")

        quarterly_order = self._create_order(quarterly, date(2026, 7, 1), date(2026, 10, 1))
        annual_order = self._create_order(annual, date(2026, 1, 1), date(2027, 1, 1))

        self.assertEqual(
            quarterly_order._get_invoice_in_arrears_period(date(2026, 10, 1)),
            (date(2026, 7, 1), date(2026, 9, 30)),
        )
        self.assertEqual(
            annual_order._get_invoice_in_arrears_period(date(2027, 1, 1)),
            (date(2026, 1, 1), date(2026, 12, 31)),
        )

    def test_08_cron_and_manual_share_the_same_period_context(self):
        plan = self._create_plan("Mensual contexto compartido")
        order = self._create_order(plan, date(2026, 7, 1), date(2026, 8, 1))
        period_start, period_end = order._get_invoice_in_arrears_period(date(2026, 8, 1))

        context_values = order._get_invoice_in_arrears_context(period_start, period_end)

        self.assertTrue(context_values["subscription_invoice_in_arrears"])
        self.assertEqual(context_values["subscription_invoice_in_arrears_period_start"], "2026-07-01")
        self.assertEqual(context_values["subscription_invoice_in_arrears_period_end"], "2026-07-31")

    def test_09_aligned_monthly_first_cycle_starts_next_month(self):
        plan = self._create_plan("Mensual vencido alineado", aligned=True)
        order = self._create_order(plan, date(2026, 7, 22), date(2026, 7, 22))

        order._ensure_invoice_in_arrears_initialized()
        period_start, period_end = order._get_invoice_in_arrears_period(date(2026, 8, 1))

        self.assertEqual(order.next_invoice_date, date(2026, 8, 1))
        self.assertEqual(period_start, date(2026, 7, 22))
        self.assertEqual(period_end, date(2026, 7, 31))

        order._mark_invoice_in_arrears_period(period_start, period_end, date(2026, 8, 1))

        self.assertEqual(order.next_invoice_date, date(2026, 9, 1))

    def test_10_aligned_monthly_existing_buggy_first_date_is_corrected(self):
        plan = self._create_plan("Mensual vencido alineado corregible", aligned=True)
        order = self._create_order(plan, date(2026, 7, 22), date(2026, 8, 22))
        order.write({"invoice_in_arrears_initialized": True})

        order._ensure_invoice_in_arrears_initialized(force=True)

        self.assertEqual(order.next_invoice_date, date(2026, 8, 1))

    def test_11_aligned_annual_first_cycle_ends_on_year_boundary(self):
        plan = self._create_plan("Anual vencido alineado", unit="year", aligned=True)
        order = self._create_order(plan, date(2026, 7, 22), date(2026, 7, 22))

        order._ensure_invoice_in_arrears_initialized()
        period_start, period_end = order._get_invoice_in_arrears_period(date(2027, 1, 1))

        self.assertEqual(order.next_invoice_date, date(2027, 1, 1))
        self.assertEqual(period_start, date(2026, 7, 22))
        self.assertEqual(period_end, date(2026, 12, 31))

    def test_12_aligned_monthly_first_cycle_proration_factor(self):
        plan = self._create_plan("Mensual vencido alineado prorrateado", aligned=True)
        order = self._create_order(plan, date(2026, 7, 29), date(2026, 7, 29))

        order._ensure_invoice_in_arrears_initialized()
        period_start, period_end = order._get_invoice_in_arrears_period(date(2026, 8, 1))
        context_values = order._get_invoice_in_arrears_context(
            period_start,
            period_end,
            date(2026, 8, 1),
        )

        self.assertEqual(order.next_invoice_date, date(2026, 8, 1))
        self.assertEqual(period_start, date(2026, 7, 29))
        self.assertEqual(period_end, date(2026, 7, 31))
        self.assertAlmostEqual(
            context_values["subscription_invoice_in_arrears_proration_factor"],
            3 / 31,
        )

    def test_13_invoice_line_price_unit_is_prorated_from_context(self):
        line = self.env["sale.order.line"].new(
            {
                "name": "Servicio recurrente",
                "price_unit": 2492.0,
            }
        )

        vals = line._prepare_invoice_in_arrears_line_update(
            date(2026, 7, 29),
            date(2026, 7, 31),
            "Servicio recurrente",
            {"price_unit": 2492.0},
            3 / 31,
        )

        self.assertAlmostEqual(vals["price_unit"], 2492.0 * 3 / 31)
