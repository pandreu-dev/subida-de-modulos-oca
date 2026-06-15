{
    "name": "Aunnna Stock Negative Control",
    "summary": "Bloquea stock negativo con reglas configurables por producto, categoria, ubicacion o almacen",
    "version": "19.0.1.1.0",
    "category": "Inventory/Inventory",
    "author": "Aunnna",
    "license": "LGPL-3",
    "depends": [
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_negative_rule_views.xml",
    ],
    "installable": True,
    "application": False,
}
