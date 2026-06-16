{
    "name": "Project Delivery Analytic Valuation",
    "summary": "Tracks manual delivery inventory costs on project dashboards",
    "version": "19.0.1.1.4",
    "category": "Inventory/Inventory",
    "author": "Aunnna",
    "license": "LGPL-3",
    "depends": [
        "stock_account",
        "sale_stock",
        "sale_project",
        "project",
        "project_account",
        "project_stock_account",
        "analytic",
    ],
    "data": [
        "views/project_delivery_stock_move_views.xml",
        "views/stock_picking_views.xml",
        "data/project_delivery_analytic_sync.xml",
    ],
    "installable": True,
    "application": False,
}
