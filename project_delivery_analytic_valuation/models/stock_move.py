from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_project_analytic_account(self):
        self.ensure_one()
        picking = self.picking_id
        if not self._is_manual_project_delivery_move():
            return self.env["account.analytic.account"]
        return picking._get_project_analytic_account()

    def _is_manual_project_delivery_move(self):
        self.ensure_one()
        picking = self.picking_id
        return bool(picking and picking._is_manual_project_delivery())

    def _get_project_analytic_distribution(self):
        self.ensure_one()
        account = self._get_project_analytic_account()
        return {str(account.id): 100.0} if account else {}

    def _get_analytic_distribution(self):
        self.ensure_one()
        project_distribution = self._get_project_analytic_distribution()
        if project_distribution:
            return project_distribution
        return super()._get_analytic_distribution()

    def _sync_project_delivery_analytic_lines(self):
        for move in self.sudo():
            if move.state != "done" or not move._is_manual_project_delivery_move():
                continue
            if move._get_project_analytic_distribution():
                move._create_analytic_move()

    def _prepare_analytic_line_values(self, account_field_values, amount, unit_amount):
        vals = super()._prepare_analytic_line_values(account_field_values, amount, unit_amount)
        self.ensure_one()
        if self._is_manual_project_delivery_move() and self._get_project_analytic_distribution():
            vals.update(
                {
                    "name": "%s - %s" % (self.reference, self.product_id.display_name),
                    "ref": self.picking_id.name or self.reference,
                    "category": "picking_entry",
                }
            )
        return vals
