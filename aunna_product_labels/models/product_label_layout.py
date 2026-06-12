from odoo import _, fields, models
from odoo.exceptions import UserError


class ProductLabelLayout(models.TransientModel):
    _inherit = "product.label.layout"

    print_format = fields.Selection(
        selection_add=[
            ("label_17_54_custom", "Etiqueta 17 x 54 mm"),
            ("label_29_90_custom", "Etiqueta 29 x 90 mm"),
            ("label_30_30_custom", "Etiqueta 30 x 30 mm"),
        ],
        ondelete={
            "label_17_54_custom": "set default",
            "label_29_90_custom": "set default",
            "label_30_30_custom": "set default",
        },
    )

    def _prepare_report_data(self):
        self.ensure_one()
        custom_reports = {
            "label_17_54_custom": "aunna_product_labels.action_report_product_label_17x54",
            "label_29_90_custom": "aunna_product_labels.action_report_product_label_29x90",
            "label_30_30_custom": "aunna_product_labels.action_report_product_label_30x30",
        }
        if self.print_format not in custom_reports:
            return super()._prepare_report_data()

        if self.custom_quantity <= 0:
            raise UserError(_("You need to set a positive quantity."))

        if self.product_tmpl_ids:
            products = self.product_tmpl_ids.ids
            active_model = "product.template"
        elif self.product_ids:
            products = self.product_ids.ids
            active_model = "product.product"
        else:
            raise UserError(
                _(
                    "No product to print, if the product is archived please "
                    "unarchive it before printing its label."
                )
            )

        data = {
            "active_model": active_model,
            "quantity_by_product": {product_id: self.custom_quantity for product_id in products},
            "layout_wizard": self.id,
            "price_included": False,
        }
        return custom_reports[self.print_format], data
