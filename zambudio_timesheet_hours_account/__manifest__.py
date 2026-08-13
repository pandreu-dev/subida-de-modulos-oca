# -*- coding: utf-8 -*-
{
    "name": "Zambudio - Horas: cuenta analitica por tipo de empleado",
    "version": "19.0.1.0.0",
    "summary": "Asigna auto_account_id a Horas internas/externas segun el tipo de empleado.",
    "description": """
Sustituye las automatizaciones de Odoo Studio (on_create_or_write) sobre
account.analytic.line que asignaban la cuenta analitica de 'Horas internas'
u 'Horas externas' en el campo auto_account_id, en funcion del tipo (y
subtipo) de empleado.

La logica se implementa como override de create/write en el modelo, sin usar
base.automation ni ir.actions.server.
""",
    "author": "Zambudio",
    "license": "LGPL-3",
    "category": "Human Resources/Timesheets",
    "depends": [
        "analytic",
        "hr_timesheet",
    ],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
