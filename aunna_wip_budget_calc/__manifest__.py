{
    "name": "Aunnna WIP - Calculo de presupuesto analitico",
    "summary": "Calcula teorico, alcanzado y WIP de presupuestos analiticos a una fecha",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Aunnna",
    "license": "LGPL-3",
    "depends": [
        "account",
        "analytic",
        "account_budget",
        "project",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/wip_calculation_views.xml",
        "views/budget_analytic_views.xml",
        "wizard/wip_calculate_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
