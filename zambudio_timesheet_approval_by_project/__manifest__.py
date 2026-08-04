{
    "name": "Zambudio - Aprobacion de partes por responsable de proyecto",
    "summary": "Validacion nativa de Odoo + el responsable del proyecto puede validar "
    "los partes de horas de su proyecto",
    "version": "19.0.5.0.0",
    "category": "Human Resources/Timesheets",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        "timesheet_grid",
        "project",
    ],
    "data": [
        "security/ir_rule.xml",
        "data/scope_validation_to_project.xml",
    ],
    "installable": True,
    "application": False,
}
