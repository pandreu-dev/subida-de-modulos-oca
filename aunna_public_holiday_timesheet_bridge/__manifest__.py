{
    "name": "Aunnna Public Holiday Timesheet Bridge",
    "summary": "Genera partes de horas desde festivos publicos OCA aplicables al empleado",
    "version": "19.0.1.4.0",
    "category": "Human Resources/Timesheets",
    "author": "Aunnna",
    "license": "LGPL-3",
    "depends": [
        "hr_timesheet",
        "project_timesheet_holidays",
        "hr_holidays_public",
        "hr_employee_calendar_planning",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/public_holiday_timesheet_wizard_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}
