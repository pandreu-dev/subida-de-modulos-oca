from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPublicHolidayTimesheetBridge(TransactionCase):
    def test_default_range_covers_current_and_next_year(self):
        date_from, date_to = self.env["aunna.public.holiday.timesheet.bridge"]._get_default_range()

        self.assertEqual(date_from.month, 1)
        self.assertEqual(date_from.day, 1)
        self.assertEqual(date_to.month, 12)
        self.assertEqual(date_to.day, 31)
        self.assertEqual(date_to.year, date_from.year + 1)
