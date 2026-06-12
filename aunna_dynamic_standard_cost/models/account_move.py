from odoo import fields, models
from odoo.tools import float_compare, float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        result = super().action_post()
        self._aunna_update_dynamic_standard_cost_from_vendor_bills()
        return result

    def _aunna_update_dynamic_standard_cost_from_vendor_bills(self):
        bills = self.filtered(lambda move: move.move_type == "in_invoice" and move.state == "posted")
        for bill in bills:
            company = bill.company_id
            valuation_date = bill.invoice_date or bill.date or fields.Date.context_today(self)
            lines = bill.invoice_line_ids.filtered(
                lambda line: not line.display_type
                and line.product_id
                and line.quantity
                and line.product_id.with_company(company)._aunna_dynamic_standard_cost_enabled(company)
            )
            for line in lines.sorted(lambda invoice_line: invoice_line.id):
                product = line.product_id.with_company(company)
                qty = line.product_uom_id._compute_quantity(line.quantity, product.uom_id)
                if float_compare(qty, 0.0, precision_rounding=product.uom_id.rounding) <= 0:
                    continue

                if line.currency_id == company.currency_id:
                    subtotal_company = line.price_subtotal
                elif getattr(line, "currency_rate", False):
                    subtotal_company = line.price_subtotal / line.currency_rate
                else:
                    subtotal_company = line.currency_id._convert(
                        line.price_subtotal,
                        company.currency_id,
                        company,
                        valuation_date,
                    )

                subtotal_company = company.currency_id.round(subtotal_company)
                if company.currency_id.is_zero(subtotal_company) or subtotal_company <= 0.0:
                    continue

                new_cost = subtotal_company / qty
                product.with_user(self.env.user)._aunna_apply_dynamic_standard_cost(
                    new_cost=new_cost,
                    company=company,
                    source="vendor_bill",
                    valuation_date=valuation_date,
                    purchase_line=line.purchase_line_id,
                    invoice_line=line,
                    note=(
                        "Coste calculado desde factura de proveedor usando subtotal "
                        "sin impuestos, descuento aplicado, moneda convertida a compania "
                        "y cantidad convertida a la unidad del producto."
                    ),
                )
