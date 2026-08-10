{
    "name": "Coste estandar dinamico basado en ultimo precio de compra",
    "summary": "Actualiza el coste estandar con el ultimo coste de compra y revaloriza stock",
    "version": "19.0.2.1.0",
    "category": "Inventory/Inventory",
    "author": "Aunnna",
    "license": "LGPL-3",
    "depends": [
        "purchase_stock",
        "stock_account",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/dynamic_standard_cost_log_views.xml",
        "views/product_category_views.xml",
    ],
    "installable": True,
    "application": False,
}
