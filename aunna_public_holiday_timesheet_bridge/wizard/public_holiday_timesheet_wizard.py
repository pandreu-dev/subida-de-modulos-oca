from datetime import date as pydate

from odoo import fields, models


class PublicHolidayTimesheetWizard(models.TransientModel):
    _name = "aunna.public.holiday.timesheet.wizard"
    _description = "Generar partes de horas desde festivos publicos"

    date_from = fields.Date(
        string="Fecha desde",
        required=True,
        default=lambda self: pydate(fields.Date.context_today(self).year, 1, 1),
    )
    date_to = fields.Date(
        string="Fecha hasta",
        required=True,
        default=lambda self: pydate(fields.Date.context_today(self).year + 1, 12, 31),
    )
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Empleados",
        help="Dejalo vacio para procesar todos los empleados activos.",
    )
    force_update = fields.Boolean(
        string="Forzar actualizacion",
        help="Actualiza las lineas generadas aunque el hash tecnico no haya cambiado.",
    )
    line_ids = fields.One2many(
        "aunna.public.holiday.timesheet.wizard.line",
        "wizard_id",
        string="Resultado",
        readonly=True,
    )

    def action_simulate(self):
        return self._run_bridge(dry_run=True)

    def action_generate(self):
        return self._run_bridge(dry_run=False)

    def _run_bridge(self, dry_run=False):
        self.ensure_one()
        self.line_ids.unlink()
        results = self.env["aunna.public.holiday.timesheet.bridge"].run_generation(
            date_from=self.date_from,
            date_to=self.date_to,
            employee_ids=self.employee_ids,
            force_update=self.force_update,
            dry_run=dry_run,
        )
        self.write(
            {
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "employee_id": result.get("employee_id"),
                            "holiday_line_id": result.get("holiday_line_id"),
                            "holiday_name": result.get("holiday_name"),
                            "date": result.get("date"),
                            "hours": result.get("hours"),
                            "analytic_line_id": result.get("analytic_line_id"),
                            "action": result.get("action"),
                            "message": result.get("message"),
                        },
                    )
                    for result in results
                ]
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Generar partes de festivos",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }


class PublicHolidayTimesheetWizardLine(models.TransientModel):
    _name = "aunna.public.holiday.timesheet.wizard.line"
    _description = "Resultado generacion partes de festivos"
    _order = "date, employee_id"

    wizard_id = fields.Many2one(
        "aunna.public.holiday.timesheet.wizard",
        required=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one("hr.employee", string="Empleado", readonly=True)
    holiday_line_id = fields.Many2one(
        "calendar.public.holiday.line",
        string="Festivo",
        readonly=True,
    )
    holiday_name = fields.Char(string="Nombre festivo", readonly=True)
    date = fields.Date(string="Fecha", readonly=True)
    hours = fields.Float(string="Horas", readonly=True)
    analytic_line_id = fields.Many2one(
        "account.analytic.line",
        string="Parte de horas",
        readonly=True,
    )
    action = fields.Selection(
        [
            ("create", "Crear"),
            ("update", "Actualizar"),
            ("no_change", "Sin cambios"),
            ("delete_stale", "Eliminar obsoleta"),
            ("skip_manual", "Omitir manual"),
            ("skip_locked", "Omitir bloqueada"),
            ("skip_locked_stale", "Obsoleta bloqueada"),
            ("skip_no_user", "Sin usuario"),
            ("skip_no_hours", "Sin horas"),
            ("skip_config", "Sin configuracion"),
            ("error", "Error"),
        ],
        string="Accion",
        readonly=True,
    )
    message = fields.Char(string="Mensaje", readonly=True)
