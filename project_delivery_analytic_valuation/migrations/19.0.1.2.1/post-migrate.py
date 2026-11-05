from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # Traslados internos pendientes creados antes de la regla: sus líneas vienen vacías.
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["stock.move"]._apply_project_delivery_rule_to_pending_moves(only_empty=True)
