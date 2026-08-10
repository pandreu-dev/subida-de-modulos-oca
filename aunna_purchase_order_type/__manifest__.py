{
    "name": "Aunnna Purchase Order Type",
    "summary": "Anade tipo de pedido en solicitudes de presupuesto y pedidos de compra",
    "version": "19.0.1.2.0",
    "category": "Purchase",
    "author": "Aunnna",
    "license": "LGPL-3",
    "depends": [
        "purchase",
        # Aporta picking_type_id ("Entregar a"), ancla del move de payment_term_id.
        "purchase_stock",
        # Aporta project_id ("Proyecto"): modulo NATIVO de Odoo 19 que enlaza
        # pedidos de compra con proyectos (project.project).
        "project_purchase",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order_type_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
