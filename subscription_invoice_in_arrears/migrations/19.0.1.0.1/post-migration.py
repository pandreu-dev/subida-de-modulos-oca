from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Plan = env["sale.subscription.plan"]
    Order = env["sale.order"]

    if "invoice_in_arrears" not in Plan._fields or "billing_first_day" not in Plan._fields:
        return

    plans = Plan.search([
        ("invoice_in_arrears", "=", True),
        ("billing_first_day", "=", True),
    ])
    if not plans:
        return

    domain = [
        ("plan_id", "in", plans.ids),
        ("invoice_in_arrears_initialized", "=", True),
        ("invoice_in_arrears_last_period_end", "=", False),
    ]
    orders = Order.search(domain)
    orders._ensure_invoice_in_arrears_initialized(force=True)
