{
    "name": "Project Delivery Analytic Valuation",
    "summary": "Tracks manual delivery inventory costs on project dashboards",
    "version": "19.0.1.0.3",
    "category": "Inventory/Inventory",
    "author": "Aunnna",
    "license": "LGPL-3",
    "depends": [
        "stock_account",
        "project",
        "project_account",
        "analytic",
    ],
    "data": [
        "views/project_delivery_stock_move_views.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "application": False,
}
