from collections import defaultdict

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, *args, **kwargs):
        self._aunna_check_negative_stock_before_done()
        return super()._action_done(*args, **kwargs)

    def _aunna_check_negative_stock_before_done(self):
        demands = defaultdict(float)
        metadata = {}

        for move in self:
            if not move.product_id or not self._aunna_is_storable_product(move.product_id):
                continue
            move_lines = move.move_line_ids
            if move_lines:
                for line in move_lines:
                    qty = self._aunna_get_move_line_quantity(line)
                    if float_is_zero(qty, precision_rounding=move.product_id.uom_id.rounding):
                        continue
                    location = line.location_id or move.location_id
                    if not self._aunna_location_can_go_negative(location):
                        continue
                    product = line.product_id or move.product_id
                    company = move.company_id or self.env.company
                    key = (
                        product.id,
                        location.id,
                        line.lot_id.id or False,
                        line.package_id.id or False,
                        line.owner_id.id or False,
                        company.id,
                    )
                    demands[key] += qty
                    metadata[key] = {
                        "product": product,
                        "location": location,
                        "lot": line.lot_id,
                        "package": line.package_id,
                        "owner": line.owner_id,
                        "company": company,
                        "move": move,
                    }
            else:
                qty = self._aunna_get_move_quantity(move)
                if float_is_zero(qty, precision_rounding=move.product_id.uom_id.rounding):
                    continue
                location = move.location_id
                if not self._aunna_location_can_go_negative(location):
                    continue
                company = move.company_id or self.env.company
                key = (
                    move.product_id.id,
                    location.id,
                    False,
                    False,
                    False,
                    company.id,
                )
                demands[key] += qty
                metadata[key] = {
                    "product": move.product_id,
                    "location": location,
                    "lot": self.env["stock.lot"],
                    "package": self.env["stock.quant.package"],
                    "owner": self.env["res.partner"],
                    "company": company,
                    "move": move,
                }

        errors = []
        Rule = self.env["aunna.stock.negative.rule"]
        for key, demanded_qty in demands.items():
            values = metadata[key]
            product = values["product"]
            location = values["location"]
            company = values["company"]
            should_block, rule = Rule._aunna_should_block(product, location, company)
            if not should_block:
                continue

            current_qty = self._aunna_get_physical_quantity(
                product=product,
                location=location,
                lot=values["lot"],
                package=values["package"],
                owner=values["owner"],
            )
            resulting_qty = current_qty - demanded_qty
            if float_compare(
                resulting_qty,
                0.0,
                precision_rounding=product.uom_id.rounding,
            ) >= 0:
                continue

            details = [
                _("Producto: %s") % product.display_name,
                _("Ubicacion: %s") % location.display_name,
                _("Stock actual: %s %s") % (current_qty, product.uom_id.display_name),
                _("Cantidad a retirar: %s %s") % (demanded_qty, product.uom_id.display_name),
                _("Stock resultante: %s %s") % (resulting_qty, product.uom_id.display_name),
            ]
            if values["lot"]:
                details.append(_("Lote/serie: %s") % values["lot"].display_name)
            if rule and rule.message:
                details.append(rule.message)
            errors.append("\n".join(details))

        if errors:
            raise UserError(
                _(
                    "No se puede validar la operacion porque dejaria stock negativo.\n\n%s"
                )
                % "\n\n".join(errors)
            )

    def _aunna_is_storable_product(self, product):
        if "is_storable" in product._fields:
            return bool(product.is_storable)
        return product.type == "product"

    def _aunna_location_can_go_negative(self, location):
        return location and location.usage in ("internal", "transit")

    def _aunna_get_move_line_quantity(self, line):
        product = line.product_id
        if "quantity_product_uom" in line._fields:
            return line.quantity_product_uom
        if "quantity" in line._fields:
            qty = line.quantity
        else:
            qty = line.qty_done
        uom = line.product_uom_id or product.uom_id
        return uom._compute_quantity(qty, product.uom_id)

    def _aunna_get_move_quantity(self, move):
        product = move.product_id
        if "quantity" in move._fields:
            qty = move.quantity
        elif "quantity_done" in move._fields:
            qty = move.quantity_done
        else:
            qty = move.product_uom_qty
        return move.product_uom._compute_quantity(qty, product.uom_id)

    def _aunna_get_physical_quantity(self, product, location, lot=False, package=False, owner=False):
        Quant = self.env["stock.quant"].sudo()
        if hasattr(Quant, "_gather"):
            quants = Quant._gather(
                product,
                location,
                lot_id=lot,
                package_id=package,
                owner_id=owner,
                strict=True,
            )
            return sum(quants.mapped("quantity"))

        domain = [
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
            ("lot_id", "=", lot.id if lot else False),
            ("package_id", "=", package.id if package else False),
            ("owner_id", "=", owner.id if owner else False),
        ]
        grouped = Quant.read_group(domain, ["quantity:sum"], [])
        return grouped[0]["quantity"] if grouped else 0.0
