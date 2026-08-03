import re

from odoo import fields, models
from odoo.tools import format_date


_DATE_TOKEN_RE = re.compile(r"\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_lines_vals_list(self, **optional_values):
        vals_list = super()._prepare_invoice_lines_vals_list(**optional_values)
        if not self.env.context.get("subscription_invoice_in_arrears"):
            return vals_list

        self.ensure_one()
        if not self._is_invoice_in_arrears_recurring_line():
            return vals_list

        period_start, period_end = self._get_invoice_in_arrears_period_from_context()
        if not period_start or not period_end:
            return vals_list

        proration_factor = self._get_invoice_in_arrears_proration_factor_from_context()
        for vals in vals_list:
            if vals.get("display_type") not in (False, None, "product"):
                continue
            vals.update(
                self._prepare_invoice_in_arrears_line_update(
                    period_start,
                    period_end,
                    vals.get("name"),
                    vals,
                    proration_factor,
                )
            )
        return vals_list

    def _is_invoice_in_arrears_recurring_line(self):
        self.ensure_one()
        if self.display_type or getattr(self, "is_downpayment", False):
            return False

        if "recurring_invoice" in self._fields:
            return bool(self.recurring_invoice)

        product = self.product_id
        template = self.product_template_id
        if product and "recurring_invoice" in product._fields:
            return bool(product.recurring_invoice)
        if template and "recurring_invoice" in template._fields:
            return bool(template.recurring_invoice)

        return False

    def _get_invoice_in_arrears_period_from_context(self):
        self.ensure_one()
        return (
            fields.Date.to_date(self.env.context.get("subscription_invoice_in_arrears_period_start")),
            fields.Date.to_date(self.env.context.get("subscription_invoice_in_arrears_period_end")),
        )

    def _prepare_invoice_in_arrears_line_update(
        self,
        period_start,
        period_end,
        current_name=None,
        current_vals=None,
        proration_factor=1.0,
    ):
        self.ensure_one()
        vals = {
            "name": self._get_invoice_in_arrears_line_name(current_name, period_start, period_end),
        }
        vals.update(
            self._prepare_invoice_in_arrears_proration_update(
                current_vals or {},
                proration_factor,
            )
        )

        start_field, end_field = self._get_invoice_in_arrears_deferred_fields()
        if start_field and end_field:
            vals[start_field] = fields.Date.to_string(period_start)
            vals[end_field] = fields.Date.to_string(period_end)

        return vals

    def _get_invoice_in_arrears_proration_factor_from_context(self):
        self.ensure_one()
        factor = self.env.context.get("subscription_invoice_in_arrears_proration_factor", 1.0)
        try:
            factor = float(factor)
        except (TypeError, ValueError):
            return 1.0
        if factor < 0.0:
            return 0.0
        if factor > 1.0:
            return 1.0
        return factor

    def _prepare_invoice_in_arrears_proration_update(self, current_vals, proration_factor):
        self.ensure_one()
        if proration_factor >= 1.0:
            return {}
        price_unit = current_vals.get("price_unit")
        if price_unit in (False, None):
            return {}
        try:
            price_unit = float(price_unit)
        except (TypeError, ValueError):
            return {}
        try:
            full_price_unit = float(self.price_unit)
        except (TypeError, ValueError):
            full_price_unit = price_unit
        tolerance = max(abs(full_price_unit), abs(price_unit), 1.0) * 0.000001
        if abs(price_unit - full_price_unit) > tolerance:
            return {}
        quantity = current_vals.get("quantity")
        if quantity not in (False, None) and self.product_uom_qty:
            try:
                quantity = float(quantity)
                full_quantity = float(self.product_uom_qty)
            except (TypeError, ValueError):
                full_quantity = quantity
            quantity_tolerance = max(abs(full_quantity), abs(quantity), 1.0) * 0.000001
            if abs(quantity - full_quantity) > quantity_tolerance:
                return {}
        return {"price_unit": price_unit * proration_factor}

    def _get_invoice_in_arrears_line_name(self, current_name, period_start, period_end):
        self.ensure_one()
        base_name = self._strip_trailing_period_line(current_name or self.name or "")
        period_line = "%s - %s" % (
            format_date(self.env, period_start),
            format_date(self.env, period_end),
        )
        return f"{base_name}\n{period_line}" if base_name else period_line

    @staticmethod
    def _strip_trailing_period_line(name):
        lines = (name or "").rstrip().splitlines()
        while lines and len(_DATE_TOKEN_RE.findall(lines[-1])) >= 2:
            lines.pop()
        return "\n".join(lines).rstrip()

    def _get_invoice_in_arrears_deferred_fields(self):
        line_fields = self.env["account.move.line"]._fields
        candidates = (
            ("deferred_start_date", "deferred_end_date"),
            ("service_start_date", "service_end_date"),
            ("subscription_start_date", "subscription_end_date"),
        )
        for start_field, end_field in candidates:
            if start_field in line_fields and end_field in line_fields:
                return start_field, end_field
        return False, False
