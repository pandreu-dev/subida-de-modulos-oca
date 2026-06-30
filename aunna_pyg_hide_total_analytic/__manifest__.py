{
    "name": "AUNNA PyG Hide Total Analytic",
    "summary": "Oculta la columna Total en el informe de Perdidas y Ganancias",
    "version": "19.0.3.0.0",
    "category": "Accounting/Reporting",
    "author": "AUNNA IT",
    "license": "LGPL-3",
    "depends": [
        "account_reports",
        "web",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "aunna_pyg_hide_total_analytic/static/src/js/hide_total_columns.js",
        ],
    },
    "installable": True,
    "application": False,
}
