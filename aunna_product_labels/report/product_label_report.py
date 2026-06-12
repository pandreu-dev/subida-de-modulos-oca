from base64 import b64encode

from odoo import _, models
from odoo.exceptions import UserError


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_quantity(quantity_by_product, product_id):
    return _as_int(
        quantity_by_product.get(product_id, quantity_by_product.get(str(product_id), 0))
    )


def _build_label_values(product, barcode=None):
    label_barcode = barcode or product.barcode or ""
    reference = product.default_code or ""
    barcode_src = ""
    if label_barcode:
        try:
            barcode_png = product.env["ir.actions.report"].barcode(
                "Code128",
                str(label_barcode),
                width=900,
                height=220,
                humanreadable=0,
            )
            barcode_src = "data:image/png;base64,%s" % b64encode(barcode_png).decode()
        except (AttributeError, ValueError):
            barcode_src = ""
    return {
        "product": product,
        "name": (product.with_context(display_default_code=False).display_name or "").upper(),
        "reference": reference,
        "barcode": label_barcode,
        "barcode_src": barcode_src,
    }


def _prepare_product_labels(env, data):
    active_model = data.get("active_model")
    if active_model == "product.template":
        Product = env["product.template"].with_context(display_default_code=False)
    elif active_model == "product.product":
        Product = env["product.product"].with_context(display_default_code=False)
    else:
        raise UserError(_("Product model not defined, Please contact your administrator."))

    quantity_by_product = data.get("quantity_by_product") or {}
    product_ids = [_as_int(product_id) for product_id in quantity_by_product.keys()]
    products = Product.browse([product_id for product_id in product_ids if product_id]).exists()
    custom_barcodes = data.get("custom_barcodes") or {}
    labels = []

    for product in products:
        custom_lines = custom_barcodes.get(product.id) or custom_barcodes.get(str(product.id)) or []
        if custom_lines:
            for barcode, quantity in custom_lines:
                for _index in range(max(_as_int(quantity), 0)):
                    labels.append(_build_label_values(product, barcode=barcode))
            continue

        quantity = _get_quantity(quantity_by_product, product.id)
        for _index in range(max(quantity, 0)):
            labels.append(_build_label_values(product))

    return labels


class ReportProductLabel17x54(models.AbstractModel):
    _name = "report.aunna_product_labels.report_product_label_17x54"
    _description = "Aunnna Product Label 17 x 54 mm"

    def _get_report_values(self, docids, data=None):
        labels = _prepare_product_labels(self.env, data or {})
        return {
            "doc_ids": [label["product"].id for label in labels],
            "doc_model": (data or {}).get("active_model", "product.template"),
            "docs": [label["product"] for label in labels],
            "labels": labels,
        }


class ReportProductLabel29x90(models.AbstractModel):
    _name = "report.aunna_product_labels.report_product_label_29x90"
    _description = "Aunnna Product Label 29 x 90 mm"

    def _get_report_values(self, docids, data=None):
        labels = _prepare_product_labels(self.env, data or {})
        return {
            "doc_ids": [label["product"].id for label in labels],
            "doc_model": (data or {}).get("active_model", "product.template"),
            "docs": [label["product"] for label in labels],
            "labels": labels,
        }


class ReportProductLabel30x30(models.AbstractModel):
    _name = "report.aunna_product_labels.report_product_label_30x30"
    _description = "Aunnna Product Label 30 x 30 mm"

    def _get_report_values(self, docids, data=None):
        labels = _prepare_product_labels(self.env, data or {})
        return {
            "doc_ids": [label["product"].id for label in labels],
            "doc_model": (data or {}).get("active_model", "product.template"),
            "docs": [label["product"] for label in labels],
            "labels": labels,
        }
