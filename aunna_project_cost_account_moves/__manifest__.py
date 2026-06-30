{
    "name": "AUNNA Project Cost Account Moves",
    "summary": "Genera asientos tecnicos compensados para costes analiticos de proyecto",
    "version": "19.0.1.2.2",
    "category": "Accounting/Accounting",
    "author": "AUNNA IT",
    "license": "LGPL-3",
    "depends": [
        "account",
        "analytic",
        "hr_timesheet",
        "stock_account",
        "project_delivery_analytic_valuation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/project_cost_move_link_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}
