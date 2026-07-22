import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class SaleSubscriptionPlan(models.Model):
    _inherit = "sale.subscription.plan"

    invoice_in_arrears = fields.Boolean(
        string="Facturar a periodo vencido",
        help=(
            "Cuando esta activado, la factura recurrente se genera al finalizar "
            "el periodo y representa el periodo inmediatamente anterior."
        ),
        default=False,
    )

    @api.model
    def install_invoice_in_arrears_view(self):
        """Create a small inherited view without depending on a brittle XML id."""
        View = self.env["ir.ui.view"].sudo()
        base_view = View.search(
            [
                ("model", "=", "sale.subscription.plan"),
                ("type", "=", "form"),
                ("inherit_id", "=", False),
            ],
            order="priority, id",
            limit=1,
        )
        if not base_view:
            _logger.warning(
                "No primary sale.subscription.plan form view found; invoice_in_arrears "
                "field was added on the model but not injected in the UI."
            )
            return False

        arch = base_view.arch_db or ""
        if 'name="billing_period_unit"' in arch or "name='billing_period_unit'" in arch:
            xpath_expr = "//field[@name='billing_period_unit']"
            field_arch = '<field name="invoice_in_arrears"/>'
            position = "after"
        elif 'name="billing_period_value"' in arch or "name='billing_period_value'" in arch:
            xpath_expr = "//field[@name='billing_period_value']"
            field_arch = '<field name="invoice_in_arrears"/>'
            position = "after"
        elif 'name="name"' in arch or "name='name'" in arch:
            xpath_expr = "//field[@name='name']"
            field_arch = '<field name="invoice_in_arrears"/>'
            position = "after"
        else:
            xpath_expr = "//sheet"
            field_arch = '<group><field name="invoice_in_arrears"/></group>'
            position = "inside"

        view_values = {
            "name": "sale.subscription.plan.form.invoice.in.arrears",
            "type": "form",
            "model": "sale.subscription.plan",
            "inherit_id": base_view.id,
            "priority": 90,
            "arch_db": (
                "<data>"
                f'<xpath expr="{xpath_expr}" position="{position}">'
                f"{field_arch}"
                "</xpath>"
                "</data>"
            ),
        }

        xmlid = "subscription_invoice_in_arrears.view_sale_subscription_plan_form_invoice_in_arrears"
        IrModelData = self.env["ir.model.data"].sudo()
        module, name = xmlid.split(".")
        xml_record = IrModelData.search(
            [("module", "=", module), ("name", "=", name)],
            limit=1,
        )
        view = self.env.ref(xmlid, raise_if_not_found=False) if xml_record else False
        if view:
            view.write(view_values)
            return True

        view = View.create(view_values)
        xml_values = {
            "module": module,
            "name": name,
            "model": "ir.ui.view",
            "res_id": view.id,
            "noupdate": False,
        }
        if xml_record:
            xml_record.write(xml_values)
        else:
            IrModelData.create(xml_values)
        return True
