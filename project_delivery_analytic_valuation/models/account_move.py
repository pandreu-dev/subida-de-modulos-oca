from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        self.filtered(lambda move: move._is_stock_valuation_closing_move())._apply_delivery_project_analytics()
        return super()._post(soft=soft)

    def _is_stock_valuation_closing_move(self):
        self.ensure_one()
        if not self.company_id:
            return False
        key = f"{self.company_id.id}.stock_valuation_closing_ids"
        closing_ids = self.env["ir.config_parameter"].sudo().get_param(key)
        return str(self.id) in (closing_ids.split(",") if closing_ids else [])

    def _apply_delivery_project_analytics(self):
        for move in self:
            if move.state != "draft":
                continue
            distribution_by_account = move._get_delivery_project_analytic_distribution_by_account()
            for line in move.line_ids.filtered(lambda line: not line.analytic_distribution):
                distribution = distribution_by_account.get(line.account_id.id)
                if distribution:
                    line.analytic_distribution = distribution

    def _get_delivery_project_analytic_distribution_by_account(self):
        self.ensure_one()
        if not self.company_id:
            return {}
        project_move_ids = self.env.context.get("delivery_project_stock_move_ids")
        project_moves = (
            self.env["stock.move"].browse(project_move_ids).exists()
            if project_move_ids
            else self.company_id._get_delivery_project_stock_moves_for_valuation_closing(at_date=self.date)
        )
        amount_by_account = {}
        for stock_move in project_moves:
            distribution = stock_move._get_project_analytic_distribution()
            if not distribution:
                continue
            account = stock_move.product_id._get_product_accounts().get("stock_variation")
            if not account:
                account = stock_move.product_id.categ_id.property_account_expense_categ_id
            if not account:
                continue
            amount = abs(stock_move.value)
            if stock_move.company_currency_id.is_zero(amount):
                continue
            account_amounts = amount_by_account.setdefault(account.id, {})
            for analytic_account_id, percentage in distribution.items():
                account_amounts[analytic_account_id] = account_amounts.get(analytic_account_id, 0.0) + (
                    amount * percentage / 100.0
                )

        distribution_by_account = {}
        for account_id, analytic_amounts in amount_by_account.items():
            total = sum(analytic_amounts.values())
            if not total:
                continue
            distribution_by_account[account_id] = {
                analytic_account_id: amount * 100.0 / total
                for analytic_account_id, amount in analytic_amounts.items()
            }
        return distribution_by_account
