{
    "name": "Informe operativo financiero",
    "summary": "Informe operativo financiero (WIP) por proyecto o cuenta analitica: prevision y reales",
    "version": "19.0.17.0.0",
    "category": "Accounting/Reporting",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        "account",
        "analytic",
        "project",
        "purchase",
        "aunna_wip_accounting",
        "aunna_purchase_order_type",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/aunna_wip_annual_report_views.xml",
    ],
    "installable": True,
    "application": False,
}
