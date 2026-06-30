{
    "name": "AUNNA Stock Picking Departments",
    "summary": "Anade departamentos BR en albaranes y pedidos de compra",
    "version": "19.0.1.1.0",
    "category": "Inventory/Inventory",
    "author": "AUNNA IT",
    "license": "LGPL-3",
    "depends": [
        "purchase_stock",
        "stock_account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/aunna_stock_department_data.xml",
        "views/aunna_stock_department_views.xml",
        "views/stock_picking_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
