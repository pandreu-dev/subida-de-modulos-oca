from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recalcula el TCV de las suscripciones ya existentes tras corregir el
    conteo de meses: ahora la fecha de fin cuenta como ultimo dia cubierto
    (de 1-abr a 31-mar = 12 meses enteros, antes salian 11,97)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env["sale.order"].search([("is_subscription", "=", True)])
    if not orders:
        return
    orders._compute_tcv_amount()
    orders.flush_recordset(["tcv_amount", "tcv_months", "tcv_missing_end_date"])
