from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class ProductCategory(models.Model):
    _inherit = "product.category"

    aunna_use_dynamic_standard_cost = fields.Boolean(
        string="Usar ultimo coste de compra",
        company_dependent=True,
        help=(
            "Si esta marcado, los productos de la categoria con coste estandar "
            "actualizaran automaticamente su coste con el ultimo precio de compra."
        ),
    )
    aunna_dynamic_cost_counterpart_account_id = fields.Many2one(
        "account.account",
        string="Cuenta contrapartida revalorizacion",
        company_dependent=True,
        check_company=True,
        help=(
            "Cuenta usada como contrapartida del asiento de revalorizacion cuando "
            "cambia el coste estandar. Si se deja vacia se intentara usar la cuenta "
            "de diferencia de precio o la cuenta de gasto del producto."
        ),
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _aunna_dynamic_standard_cost_enabled(self, company):
        self.ensure_one()
        product = self.with_company(company)
        return (
            bool(product.is_storable)
            and product.cost_method == "standard"
            and product.categ_id.aunna_use_dynamic_standard_cost
        )

    def _aunna_get_revaluation_qty(self, company):
        self.ensure_one()
        product = self.with_company(company)
        if hasattr(product, "_with_valuation_context"):
            product = product._with_valuation_context()
        return product.qty_available

    def _aunna_get_revaluation_accounts(self, company):
        self.ensure_one()
        product = self.with_company(company)
        accounts = product.product_tmpl_id.get_product_accounts()
        stock_accounts = product.product_tmpl_id._get_product_accounts()
        valuation_account = accounts.get("stock_valuation")
        journal = accounts.get("stock_journal")
        counterpart_account = (
            product.categ_id.aunna_dynamic_cost_counterpart_account_id
            or product.product_tmpl_id._get_price_diff_account()
            or stock_accounts.get("stock_variation")
            or accounts.get("expense")
        )
        if not valuation_account or not journal or not counterpart_account:
            raise UserError(
                _(
                    "No se puede revalorizar el producto %s porque faltan cuentas "
                    "contables de stock, diario de stock o cuenta de contrapartida."
                )
                % product.display_name
            )
        return journal, valuation_account, counterpart_account

    def _aunna_create_revaluation_move(
        self,
        company,
        valuation_date,
        old_cost,
        new_cost,
        qty,
        amount,
        source_label,
    ):
        self.ensure_one()
        product = self.with_company(company)
        currency = company.currency_id
        if (
            float_is_zero(qty, precision_rounding=product.uom_id.rounding)
            or currency.is_zero(amount)
            or product.valuation != "real_time"
        ):
            return self.env["account.move"]

        journal, valuation_account, counterpart_account = product._aunna_get_revaluation_accounts(company)
        amount_abs = abs(currency.round(amount))
        if currency.is_zero(amount_abs):
            return self.env["account.move"]

        label = _(
            "Revalorizacion coste estandar %s: %s -> %s"
        ) % (product.display_name, old_cost, new_cost)
        if amount > 0:
            debit_account = valuation_account
            credit_account = counterpart_account
        else:
            debit_account = counterpart_account
            credit_account = valuation_account

        move = self.env["account.move"].sudo().with_company(company).create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": valuation_date,
                "ref": source_label,
                "company_id": company.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": label,
                            "account_id": debit_account.id,
                            "debit": amount_abs,
                            "credit": 0.0,
                            "product_id": product.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": label,
                            "account_id": credit_account.id,
                            "debit": 0.0,
                            "credit": amount_abs,
                            "product_id": product.id,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        return move

    def _aunna_apply_dynamic_standard_cost(
        self,
        new_cost,
        company,
        source,
        valuation_date=None,
        purchase_line=False,
        stock_move=False,
        invoice_line=False,
        revaluation_qty=False,
        note=False,
    ):
        self.ensure_one()
        product = self.with_company(company)
        if not product._aunna_dynamic_standard_cost_enabled(company):
            return self.env["aunna.dynamic.standard.cost.log"]

        precision = self.env["decimal.precision"].precision_get("Product Price")
        old_cost = product.standard_price
        if float_is_zero(new_cost, precision_digits=precision) and not old_cost:
            return self.env["aunna.dynamic.standard.cost.log"]
        if float_compare(new_cost, old_cost, precision_digits=precision) == 0:
            return self.env["aunna.dynamic.standard.cost.log"]

        date = fields.Date.to_date(valuation_date or fields.Date.context_today(self))
        qty = revaluation_qty if revaluation_qty is not False else product._aunna_get_revaluation_qty(company)
        if float_compare(qty, 0.0, precision_rounding=product.uom_id.rounding) <= 0:
            qty_for_revaluation = 0.0
        else:
            qty_for_revaluation = qty

        unit_difference = new_cost - old_cost
        valuation_difference = company.currency_id.round(unit_difference * qty_for_revaluation)
        source_label = _("Coste estandar dinamico")
        if stock_move:
            source_label = "%s - %s" % (source_label, stock_move.reference or stock_move.name)
        elif invoice_line:
            source_label = "%s - %s" % (source_label, invoice_line.move_id.name)

        revaluation_move = product._aunna_create_revaluation_move(
            company=company,
            valuation_date=date,
            old_cost=old_cost,
            new_cost=new_cost,
            qty=qty_for_revaluation,
            amount=valuation_difference,
            source_label=source_label,
        )

        product.sudo().with_context(valuation_date=date).write({"standard_price": new_cost})

        log_vals = {
            "date": fields.Datetime.now(),
            "source": source,
            "product_id": product.id,
            "company_id": company.id,
            "old_standard_price": old_cost,
            "new_standard_price": new_cost,
            "unit_difference": unit_difference,
            "qty_available": qty_for_revaluation,
            "valuation_difference": valuation_difference,
            "revaluation_move_id": revaluation_move.id or False,
            "user_id": self.env.user.id,
            "note": note or False,
        }
        if purchase_line:
            log_vals.update(
                {
                    "purchase_order_id": purchase_line.order_id.id,
                    "purchase_line_id": purchase_line.id,
                }
            )
        if stock_move:
            log_vals.update(
                {
                    "picking_id": stock_move.picking_id.id,
                    "stock_move_id": stock_move.id,
                }
            )
        if invoice_line:
            log_vals.update(
                {
                    "vendor_bill_id": invoice_line.move_id.id,
                    "vendor_bill_line_id": invoice_line.id,
                    "purchase_line_id": invoice_line.purchase_line_id.id,
                    "purchase_order_id": invoice_line.purchase_line_id.order_id.id,
                }
            )
        return self.env["aunna.dynamic.standard.cost.log"].sudo().create(log_vals)
