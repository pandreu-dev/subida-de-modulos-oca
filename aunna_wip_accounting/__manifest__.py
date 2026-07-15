{
    "name": "Aunnna WIP - Contabilizacion",
    "summary": "Crea y revierte asientos contables WIP desde calculos WIP",
    "version": "19.0.6.1.0",
    "category": "Accounting/Accounting",
    "author": "Aunnna",
    "license": "LGPL-3",
    "depends": [
        "aunna_wip_budget_calc",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/wip_calculation_views.xml",
        "views/budget_analytic_views.xml",
        "wizard/wip_auto_test_wizard_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}
