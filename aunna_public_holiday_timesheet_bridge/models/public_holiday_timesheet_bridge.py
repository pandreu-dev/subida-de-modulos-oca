import hashlib
import json
import logging
from datetime import date as pydate
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PublicHolidayTimesheetBridge(models.Model):
    _name = "aunna.public.holiday.timesheet.bridge"
    _description = "Puente entre festivos publicos OCA y partes de horas"

    @api.model
    def _cron_generate_public_holiday_timesheets(self):
        date_from, date_to = self._get_default_range()
        return self.run_generation(date_from=date_from, date_to=date_to, origin="automatic")

    @api.model
    def _get_default_range(self):
        today = fields.Date.context_today(self)
        return pydate(today.year, 1, 1), pydate(today.year + 1, 12, 31)

    @api.model
    def sync_generated_timesheets(
        self,
        date_from=False,
        date_to=False,
        employee_ids=False,
        origin="automatic",
    ):
        date_from, date_to = self._get_sync_range(date_from, date_to, employee_ids)
        return self.with_context(aunna_public_holiday_timesheet_sync=True).run_generation(
            date_from=date_from,
            date_to=date_to,
            employee_ids=employee_ids,
            force_update=True,
            dry_run=False,
            origin=origin,
        )

    @api.model
    def _get_sync_range(self, date_from=False, date_to=False, employee_ids=False):
        default_from, default_to = self._get_default_range()
        date_from = fields.Date.to_date(date_from or default_from)
        date_to = fields.Date.to_date(date_to or default_to)

        domain = [("x_generated_by_public_holiday_bridge", "=", True)]
        if employee_ids:
            if hasattr(employee_ids, "_name"):
                employee_ids = employee_ids.ids
            domain.append(("employee_id", "in", employee_ids))

        AnalyticLine = self.env["account.analytic.line"].sudo()
        first_line = AnalyticLine.search(domain, order="date asc", limit=1)
        last_line = AnalyticLine.search(domain, order="date desc", limit=1)
        if first_line and first_line.date:
            date_from = min(date_from, fields.Date.to_date(first_line.date))
        if last_line and last_line.date:
            date_to = max(date_to, fields.Date.to_date(last_line.date))
        return date_from, date_to

    @api.model
    def delete_generated_lines_for_holidays(self, holiday_lines):
        if not holiday_lines:
            return []

        results = []
        lines = self.env["account.analytic.line"].sudo().search(
            [
                ("x_generated_by_public_holiday_bridge", "=", True),
                ("x_public_holiday_line_id", "in", holiday_lines.ids),
            ]
        )
        for line in lines:
            editable = self._is_line_editable(line)
            results.append(
                self._make_result(
                    employee=line.employee_id,
                    holiday=line.x_public_holiday_line_id,
                    holiday_date=line.date,
                    hours=line.unit_amount,
                    analytic_line=line,
                    action="delete_stale" if editable else "skip_locked_stale",
                    message=_("Linea generada eliminada porque el festivo se ha borrado.")
                    if editable
                    else _("Linea generada obsoleta, pero validada o bloqueada."),
                )
            )
            if editable:
                line.unlink()
        return results

    @api.model
    def run_generation(
        self,
        date_from=False,
        date_to=False,
        employee_ids=False,
        force_update=False,
        dry_run=False,
        origin="manual",
    ):
        date_from, date_to = self._normalize_range(date_from, date_to)
        employees = self._get_employees(employee_ids)
        results = []

        for employee in employees:
            employee_results = self._process_employee(
                employee=employee,
                date_from=date_from,
                date_to=date_to,
                force_update=force_update,
                dry_run=dry_run,
                origin=origin,
            )
            results.extend(employee_results)

        return results

    @api.model
    def _normalize_range(self, date_from=False, date_to=False):
        if not date_from or not date_to:
            default_from, default_to = self._get_default_range()
            date_from = date_from or default_from
            date_to = date_to or default_to

        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        if date_from > date_to:
            raise UserError(_("La fecha desde no puede ser posterior a la fecha hasta."))
        return date_from, date_to

    @api.model
    def _get_employees(self, employee_ids=False):
        Employee = self.env["hr.employee"].sudo()
        if employee_ids:
            if hasattr(employee_ids, "_name"):
                employees = employee_ids.sudo()
            else:
                employees = Employee.browse(employee_ids)
            return employees.exists()

        domain = []
        if "active" in Employee._fields:
            domain.append(("active", "=", True))
        return Employee.search(domain)

    @api.model
    def _process_employee(
        self,
        employee,
        date_from,
        date_to,
        force_update=False,
        dry_run=False,
        origin="manual",
    ):
        results = []

        if not employee.user_id:
            return [
                self._make_result(
                    employee=employee,
                    action="skip_no_user",
                    message=_("Empleado sin usuario vinculado."),
                )
            ]

        company = employee.company_id or self.env.company
        project, task = self._get_timesheet_target(company)
        if not project or not task:
            return [
                self._make_result(
                    employee=employee,
                    action="skip_config",
                    message=_("Falta configurar el proyecto interno o la tarea Time Off en la compania."),
                )
            ]

        desired_keys = set()
        holidays = self._get_public_holiday_lines(employee, date_from, date_to)
        if not holidays:
            partner = self._get_employee_partner(employee)
            message = _("No se han encontrado festivos OCA aplicables en el rango indicado.")
            if not partner:
                message = _("No se ha encontrado direccion/partner del empleado para calcular festivos OCA.")
            results.append(
                self._make_result(
                    employee=employee,
                    action="skip_no_holidays",
                    message=message,
                )
            )

        for holiday in holidays:
            holiday_date = self._get_holiday_date(holiday)
            if not holiday_date:
                continue
            desired_keys.add(
                (
                    holiday.id,
                    fields.Date.to_string(holiday_date),
                    company.id,
                    project.id,
                    task.id,
                )
            )
            results.append(
                self._sync_holiday_timesheet(
                    employee=employee,
                    company=company,
                    project=project,
                    task=task,
                    holiday=holiday,
                    holiday_date=holiday_date,
                    force_update=force_update,
                    dry_run=dry_run,
                    origin=origin,
                )
            )

        results.extend(
            self._reconcile_stale_generated_lines(
                employee=employee,
                date_from=date_from,
                date_to=date_to,
                desired_keys=desired_keys,
                dry_run=dry_run,
            )
        )
        return results

    @api.model
    def _get_timesheet_target(self, company):
        company = company.sudo().with_company(company)
        project = company.internal_project_id if "internal_project_id" in company._fields else False
        task = company.leave_timesheet_task_id if "leave_timesheet_task_id" in company._fields else False
        return project, task

    @api.model
    def _sync_holiday_timesheet(
        self,
        employee,
        company,
        project,
        task,
        holiday,
        holiday_date,
        force_update=False,
        dry_run=False,
        origin="manual",
    ):
        hours = self._compute_employee_hours(employee, holiday_date)
        holiday_name = self._get_record_name(holiday)
        if hours <= 0:
            return self._make_result(
                employee=employee,
                holiday=holiday,
                holiday_date=holiday_date,
                hours=hours,
                action="skip_no_hours",
                message=_("El calendario activo no tiene horas laborables ese dia."),
            )

        existing = self._find_generated_line(employee, holiday_date, project, task, holiday)
        if not existing:
            manual = self._find_manual_line(employee, holiday_date, project, task)
            if manual:
                return self._make_result(
                    employee=employee,
                    holiday=holiday,
                    holiday_date=holiday_date,
                    hours=hours,
                    analytic_line=manual,
                    action="skip_manual",
                    message=_("Ya existe una linea manual en el proyecto/tarea de ausencias."),
                )

        vals = self._prepare_timesheet_values(
            employee=employee,
            company=company,
            project=project,
            task=task,
            holiday=holiday,
            holiday_date=holiday_date,
            hours=hours,
            holiday_name=holiday_name,
            origin=origin,
        )

        if existing:
            if not self._is_line_editable(existing):
                return self._make_result(
                    employee=employee,
                    holiday=holiday,
                    holiday_date=holiday_date,
                    hours=hours,
                    analytic_line=existing,
                    action="skip_locked",
                    message=_("La linea generada esta validada o bloqueada y no se modifica."),
                )

            if not force_update and existing.x_public_holiday_hash == vals["x_public_holiday_hash"]:
                return self._make_result(
                    employee=employee,
                    holiday=holiday,
                    holiday_date=holiday_date,
                    hours=hours,
                    analytic_line=existing,
                    action="no_change",
                    message=_("La linea generada ya esta actualizada."),
                )

            if not dry_run:
                existing.sudo().write(vals)
            return self._make_result(
                employee=employee,
                holiday=holiday,
                holiday_date=holiday_date,
                hours=hours,
                analytic_line=existing,
                action="update",
                message=_("Se actualizaria la linea generada.") if dry_run else _("Linea generada actualizada."),
            )

        analytic_line = self.env["account.analytic.line"]
        if not dry_run:
            analytic_line = analytic_line.sudo().create(vals)
        return self._make_result(
            employee=employee,
            holiday=holiday,
            holiday_date=holiday_date,
            hours=hours,
            analytic_line=analytic_line,
            action="create",
            message=_("Se crearia una nueva linea.") if dry_run else _("Linea creada."),
        )

    @api.model
    def _prepare_timesheet_values(
        self,
        employee,
        company,
        project,
        task,
        holiday,
        holiday_date,
        hours,
        holiday_name,
        origin="manual",
    ):
        name = _("Time Off - %s") % holiday_name
        vals = {
            "name": name,
            "employee_id": employee.id,
            "user_id": employee.user_id.id,
            "project_id": project.id,
            "task_id": task.id,
            "date": holiday_date,
            "unit_amount": hours,
            "company_id": company.id,
            "x_is_public_holiday_timesheet": True,
            "x_generated_by_public_holiday_bridge": True,
            "x_public_holiday_line_id": holiday.id,
            "x_public_holiday_source": "%s:calendar.public.holiday.line:%s" % (origin, holiday.id),
        }
        vals["x_public_holiday_hash"] = self._make_hash(vals)
        return vals

    @api.model
    def _compute_employee_hours(self, employee, holiday_date):
        calendar = employee.resource_calendar_id
        if not calendar:
            return 0.0

        tz = employee.user_id.tz or self.env.user.tz or "Europe/Madrid"
        calendar = calendar.sudo().with_context(tz=tz)
        start_dt = datetime.combine(holiday_date, time.min)
        end_dt = datetime.combine(holiday_date, time.max)
        return calendar.get_work_hours_count(start_dt, end_dt, compute_leaves=False)

    @api.model
    def _get_public_holiday_lines(self, employee, date_from, date_to):
        model_name = "calendar.public.holiday.line"
        try:
            HolidayLine = self.env[model_name].sudo()
        except KeyError:
            raise UserError(_("No existe el modelo calendar.public.holiday.line. Revisa hr_holidays_public."))

        partner = self._get_employee_partner(employee)
        PublicHoliday = self.env["calendar.public.holiday"].sudo()
        get_holidays_list = getattr(PublicHoliday, "get_holidays_list", False)
        if get_holidays_list:
            return get_holidays_list(
                start_dt=date_from,
                end_dt=date_to,
                partner_id=partner.id if partner else None,
            )

        date_field = self._get_holiday_date_field(HolidayLine)
        if not date_field:
            raise UserError(_("No se ha encontrado un campo de fecha en calendar.public.holiday.line."))

        domain = [
            (date_field, ">=", date_from),
            (date_field, "<=", date_to),
        ]
        holidays = HolidayLine.search(domain)
        country, state, partner = self._get_employee_location(employee)
        return holidays.filtered(lambda line: self._holiday_applies_to_employee(line, country, state, partner))

    @api.model
    def _get_holiday_date_field(self, HolidayLine):
        for field_name in ("date", "holiday_date", "date_from", "day"):
            if field_name in HolidayLine._fields:
                return field_name
        return False

    @api.model
    def _get_holiday_date(self, holiday):
        for field_name in ("date", "holiday_date", "date_from", "day"):
            if field_name not in holiday._fields:
                continue
            value = holiday[field_name]
            if not value:
                continue
            return fields.Date.to_date(value)
        return False

    @api.model
    def _get_employee_location(self, employee):
        partner = self._get_employee_partner(employee)
        country = employee.country_id if "country_id" in employee._fields else False
        state = employee.state_id if "state_id" in employee._fields else False

        if partner:
            country = country or (partner.country_id if "country_id" in partner._fields else False)
            state = state or (partner.state_id if "state_id" in partner._fields else False)

        if state and not country and "country_id" in state._fields:
            country = state.country_id

        return country, state, partner

    @api.model
    def _get_employee_partner(self, employee):
        for field_name in (
            "address_id",
            "private_contact_id",
            "address_home_id",
            "home_address_id",
            "work_contact_id",
        ):
            if field_name in employee._fields and employee[field_name]:
                return employee[field_name]
        if employee.user_id and employee.user_id.partner_id:
            return employee.user_id.partner_id
        return self.env["res.partner"].browse()

    @api.model
    def _holiday_applies_to_employee(self, holiday, employee_country, employee_state, employee_partner):
        holiday_country = self._get_related_country(holiday)
        if holiday_country and employee_country and holiday_country != employee_country:
            return False
        if holiday_country and not employee_country:
            return False

        state_ids = self._get_relation_records(holiday, ("state_ids", "state_id"))
        if state_ids and (not employee_state or employee_state not in state_ids):
            return False

        city_ids = self._get_relation_records(holiday, ("city_ids", "city_id"))
        if city_ids:
            employee_city = self._get_employee_city(employee_partner)
            if not employee_city or employee_city not in city_ids:
                return False

        return True

    @api.model
    def _get_related_country(self, holiday):
        for record in self._holiday_scope_records(holiday):
            if "country_id" in record._fields and record.country_id:
                return record.country_id
        return False

    @api.model
    def _holiday_scope_records(self, holiday):
        records = [holiday]
        for field_name in ("holiday_id", "year_id", "calendar_id", "public_holiday_id"):
            if field_name in holiday._fields and holiday[field_name]:
                records.append(holiday[field_name])
        return records

    @api.model
    def _get_relation_records(self, record, field_names):
        result = False
        for scope_record in self._holiday_scope_records(record):
            for field_name in field_names:
                if field_name in scope_record._fields and scope_record[field_name]:
                    value = scope_record[field_name]
                    if not hasattr(value, "_name"):
                        continue
                    result = value if not result else result | value
        return result

    @api.model
    def _get_employee_city(self, partner):
        if not partner:
            return False
        for field_name in ("city_id", "city_ids"):
            if field_name in partner._fields and partner[field_name]:
                return partner[field_name]
        return False

    @api.model
    def _find_generated_line(self, employee, holiday_date, project, task, holiday):
        domain = [
            ("employee_id", "=", employee.id),
            ("date", "=", holiday_date),
            ("project_id", "=", project.id),
            ("task_id", "=", task.id),
            ("x_generated_by_public_holiday_bridge", "=", True),
            ("x_public_holiday_line_id", "=", holiday.id),
        ]
        return self.env["account.analytic.line"].sudo().search(domain, limit=1)

    @api.model
    def _find_manual_line(self, employee, holiday_date, project, task):
        domain = [
            ("employee_id", "=", employee.id),
            ("date", "=", holiday_date),
            ("project_id", "=", project.id),
            ("task_id", "=", task.id),
            ("x_generated_by_public_holiday_bridge", "=", False),
        ]
        return self.env["account.analytic.line"].sudo().search(domain, limit=1)

    @api.model
    def _reconcile_stale_generated_lines(self, employee, date_from, date_to, desired_keys, dry_run=False):
        domain = [
            ("employee_id", "=", employee.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("x_generated_by_public_holiday_bridge", "=", True),
        ]
        lines = self.env["account.analytic.line"].sudo().search(domain)
        results = []

        for line in lines:
            line_key = (
                line.x_public_holiday_line_id.id,
                fields.Date.to_string(line.date),
                line.company_id.id,
                line.project_id.id,
                line.task_id.id,
            )
            if line_key in desired_keys:
                continue

            if not self._is_line_editable(line):
                results.append(
                    self._make_result(
                        employee=employee,
                        holiday=line.x_public_holiday_line_id,
                        holiday_date=line.date,
                        hours=line.unit_amount,
                        analytic_line=line,
                        action="skip_locked_stale",
                        message=_("Linea generada obsoleta, pero validada o bloqueada."),
                    )
                )
                continue

            results.append(
                self._make_result(
                    employee=employee,
                    holiday=line.x_public_holiday_line_id,
                    holiday_date=line.date,
                    hours=line.unit_amount,
                    analytic_line=line,
                    action="delete_stale",
                    message=_("Se eliminaria una linea generada que ya no corresponde.")
                    if dry_run
                    else _("Linea generada obsoleta eliminada."),
                )
            )
            if not dry_run:
                line.unlink()

        return results

    @api.model
    def _is_line_editable(self, line):
        locked_boolean_fields = (
            "validated",
            "is_validated",
            "is_timesheet_locked",
            "timesheet_locked",
            "readonly_timesheet",
        )
        for field_name in locked_boolean_fields:
            if field_name in line._fields and line[field_name]:
                return False

        if "timesheet_invoice_id" in line._fields and line.timesheet_invoice_id:
            return False
        if "move_line_id" in line._fields and line.move_line_id:
            return False
        if "state" in line._fields and line.state not in (False, "draft", "open"):
            return False

        return True

    @api.model
    def _make_hash(self, vals):
        payload = {
            key: self._jsonable(value)
            for key, value in vals.items()
            if key
            in {
                "name",
                "employee_id",
                "user_id",
                "project_id",
                "task_id",
                "date",
                "unit_amount",
                "company_id",
                "x_public_holiday_line_id",
                "x_public_holiday_source",
            }
        }
        encoded = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha1(encoded.encode("utf-8")).hexdigest()

    @api.model
    def _jsonable(self, value):
        if hasattr(value, "id"):
            return value.id
        if isinstance(value, (datetime, pydate)):
            return fields.Date.to_string(value)
        return value

    @api.model
    def _get_record_name(self, record):
        if record and "name" in record._fields and record.name:
            return record.name
        return record.display_name if record else _("Festivo")

    @api.model
    def _make_result(
        self,
        employee,
        action,
        message,
        holiday=False,
        holiday_date=False,
        hours=0.0,
        analytic_line=False,
    ):
        if message and action not in ("no_change", "create", "update", "delete_stale"):
            _logger.info(
                "Public holiday timesheet bridge: %s - %s - %s",
                employee.display_name,
                action,
                message,
            )

        return {
            "employee_id": employee.id if employee else False,
            "holiday_line_id": holiday.id if holiday else False,
            "holiday_name": self._get_record_name(holiday) if holiday else False,
            "date": holiday_date or False,
            "hours": hours,
            "analytic_line_id": analytic_line.id if analytic_line else False,
            "action": action,
            "message": message,
        }
