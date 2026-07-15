{
    "name": "Zambudio - Aprobacion de partes por responsable de proyecto",
    "summary": "El jefe de proyecto valida los partes de horas imputados a sus "
    "proyectos, sin tocar el flujo de validacion nativo",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Timesheets",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        "timesheet_grid",
        "project",
    ],
    "data": [
        "security/ir_rule.xml",
        "views/timesheet_approval_views.xml",
    ],
    "installable": True,
    "application": False,
}
