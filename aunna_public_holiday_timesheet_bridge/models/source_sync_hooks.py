from odoo import api, fields, models
from odoo.osv import expression


SYNC_CONTEXT_KEY = "aunna_public_holiday_timesheet_sync"


def _bridge(env):
    return env["aunna.public.holiday.timesheet.bridge"].sudo()


def _date_min(values):
    values = [fields.Date.to_date(value) for value in values if value]
    return min(values) if values else False


def _date_max(values):
    values = [fields.Date.to_date(value) for value in values if value]
    return max(values) if values else False


def _sync_range(record, date_from=False, date_to=False, employees=False):
    if record.env.context.get(SYNC_CONTEXT_KEY):
        return
    bridge = _bridge(record.env)
    if not date_from or not date_to:
        default_from, default_to = bridge._get_default_range()
        date_from = date_from or default_from
        date_to = date_to or default_to
    bridge.sync_generated_timesheets(
        date_from=date_from,
        date_to=date_to,
        employee_ids=employees,
    )


def _combine_ranges(*ranges):
    dates_from = [item[0] for item in ranges if item and item[0]]
    dates_to = [item[1] for item in ranges if item and item[1]]
    return _date_min(dates_from), _date_max(dates_to)


class CalendarPublicHolidayLine(models.Model):
    _inherit = "calendar.public.holiday.line"

    def _aunna_line_range(self):
        return _date_min(self.mapped("date")), _date_max(self.mapped("date"))

    def _aunna_sync_public_holiday_lines(self, old_range=False):
        date_from, date_to = _combine_ranges(old_range, self._aunna_line_range())
        _sync_range(self, date_from=date_from, date_to=date_to)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._aunna_sync_public_holiday_lines()
        return records

    def write(self, vals):
        old_range = self._aunna_line_range()
        res = super().write(vals)
        sync_fields = {"name", "date", "state_ids", "city_ids", "public_holiday_id"}
        if sync_fields.intersection(vals):
            self._aunna_sync_public_holiday_lines(old_range=old_range)
        return res

    def unlink(self):
        old_range = self._aunna_line_range()
        _bridge(self.env).delete_generated_lines_for_holidays(self)
        res = super().unlink()
        _sync_range(self, date_from=old_range[0], date_to=old_range[1])
        return res


class CalendarPublicHoliday(models.Model):
    _inherit = "calendar.public.holiday"

    def _aunna_public_holiday_range(self):
        dates = self.mapped("line_ids.date")
        if dates:
            return _date_min(dates), _date_max(dates)

        years = [year for year in self.mapped("year") if year]
        if not years:
            return False, False
        return fields.Date.to_date("%s-01-01" % min(years)), fields.Date.to_date("%s-12-31" % max(years))

    def write(self, vals):
        old_range = self._aunna_public_holiday_range()
        res = super().write(vals)
        sync_fields = {"country_id", "year", "line_ids"}
        if sync_fields.intersection(vals):
            date_from, date_to = _combine_ranges(old_range, self._aunna_public_holiday_range())
            _sync_range(self, date_from=date_from, date_to=date_to)
        return res

    def unlink(self):
        old_range = self._aunna_public_holiday_range()
        _bridge(self.env).delete_generated_lines_for_holidays(self.mapped("line_ids"))
        res = super().unlink()
        _sync_range(self, date_from=old_range[0], date_to=old_range[1])
        return res


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _aunna_sync_employee_public_holiday_timesheets(self):
        _sync_range(self, employees=self)

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._aunna_sync_employee_public_holiday_timesheets()
        return employees

    def write(self, vals):
        res = super().write(vals)
        sync_fields = {
            "address_id",
            "private_contact_id",
            "address_home_id",
            "home_address_id",
            "work_contact_id",
            "user_id",
            "company_id",
            "resource_calendar_id",
            "calendar_ids",
        }
        if sync_fields.intersection(vals):
            self._aunna_sync_employee_public_holiday_timesheets()
        return res


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _aunna_related_employees(self):
        Employee = self.env["hr.employee"].sudo()
        employee_fields = [
            "address_id",
            "private_contact_id",
            "address_home_id",
            "home_address_id",
            "work_contact_id",
        ]
        domains = [
            [(field_name, "in", self.ids)]
            for field_name in employee_fields
            if field_name in Employee._fields
        ]
        if "user_id" in Employee._fields:
            domains.append([("user_id.partner_id", "in", self.ids)])
        if not domains:
            return Employee.browse()
        return Employee.search(expression.OR(domains))

    def write(self, vals):
        res = super().write(vals)
        sync_fields = {"country_id", "state_id", "city_id"}
        if sync_fields.intersection(vals):
            _sync_range(self, employees=self._aunna_related_employees())
        return res

    def unlink(self):
        employees = self._aunna_related_employees()
        res = super().unlink()
        _sync_range(self, employees=employees)
        return res


class HrEmployeeCalendar(models.Model):
    _inherit = "hr.employee.calendar"

    def _aunna_employee_calendar_range(self):
        bridge = _bridge(self.env)
        default_from, default_to = bridge._get_default_range()
        starts = [item.date_start or default_from for item in self]
        ends = [item.date_end or default_to for item in self]
        return _date_min(starts), _date_max(ends)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        date_from, date_to = records._aunna_employee_calendar_range()
        _sync_range(
            records,
            date_from=date_from,
            date_to=date_to,
            employees=records.mapped("employee_id"),
        )
        return records

    def write(self, vals):
        old_range = self._aunna_employee_calendar_range()
        old_employees = self.mapped("employee_id")
        res = super().write(vals)
        sync_fields = {"date_start", "date_end", "calendar_id", "employee_id"}
        if sync_fields.intersection(vals):
            date_from, date_to = _combine_ranges(
                old_range,
                self._aunna_employee_calendar_range(),
            )
            _sync_range(
                self,
                date_from=date_from,
                date_to=date_to,
                employees=old_employees | self.mapped("employee_id"),
            )
        return res

    def unlink(self):
        date_from, date_to = self._aunna_employee_calendar_range()
        employees = self.mapped("employee_id")
        res = super().unlink()
        _sync_range(self, date_from=date_from, date_to=date_to, employees=employees)
        return res


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def _aunna_calendar_employees(self):
        Employee = self.env["hr.employee"].sudo()
        employees = Employee.browse()
        if "employee_calendar_ids" in self._fields:
            employees |= self.mapped("employee_calendar_ids.employee_id")
        if "resource_calendar_id" in Employee._fields:
            employees |= Employee.search([("resource_calendar_id", "in", self.ids)])
        return employees

    def write(self, vals):
        employees = self._aunna_calendar_employees()
        res = super().write(vals)
        sync_fields = {
            "attendance_ids",
            "global_leave_ids",
            "hours_per_day",
            "tz",
            "two_weeks_calendar",
        }
        if sync_fields.intersection(vals):
            employees |= self._aunna_calendar_employees()
            _sync_range(self, employees=employees)
        return res


class ResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    def _aunna_attendance_employees(self):
        return self.mapped("calendar_id")._aunna_calendar_employees()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        _sync_range(records, employees=records._aunna_attendance_employees())
        return records

    def write(self, vals):
        employees = self._aunna_attendance_employees()
        res = super().write(vals)
        employees |= self._aunna_attendance_employees()
        _sync_range(self, employees=employees)
        return res

    def unlink(self):
        employees = self._aunna_attendance_employees()
        res = super().unlink()
        _sync_range(self, employees=employees)
        return res
