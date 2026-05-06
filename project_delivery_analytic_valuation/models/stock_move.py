from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_project_analytic_account(self):
        self.ensure_one()
        picking = self.picking_id
        if not picking or not picking._is_manual_project_delivery():
            return self.env["account.analytic.account"]
        return picking._get_project_analytic_account()

    def _get_project_analytic_distribution(self):
        self.ensure_one()
        account = self._get_project_analytic_account()
        return {str(account.id): 100.0} if account else {}

    def _get_analytic_distribution(self):
        distribution = super()._get_analytic_distribution()
        if distribution:
            return distribution
        self.ensure_one()
        if not self.picking_id._is_manual_project_delivery():
            return {}
        return self._get_project_analytic_distribution()

    def _get_account_move_line_vals(self):
        vals_list = super()._get_account_move_line_vals()
        self.ensure_one()
        distribution = self._get_project_analytic_distribution()
        if not distribution:
            return vals_list
        product_accounts = self.product_id._get_product_accounts()
        analytic_account_ids = {
            account.id
            for account in (
                product_accounts.get("stock_variation"),
                product_accounts.get("expense"),
                self.product_id.categ_id.property_account_expense_categ_id,
            )
            if account
        }
        for vals in vals_list:
            if vals.get("account_id") in analytic_account_ids:
                vals.setdefault("analytic_distribution", distribution)
        return vals_list

    def _prepare_analytic_line_values(self, account_field_values, amount, unit_amount):
        vals = super()._prepare_analytic_line_values(account_field_values, amount, unit_amount)
        self.ensure_one()
        if self.picking_id._is_manual_project_delivery() and self._get_project_analytic_distribution():
            vals.update(
                {
                    "name": "%s - %s" % (self.reference, self.product_id.display_name),
                    "ref": self.picking_id.name or self.reference,
                }
            )
        return vals
