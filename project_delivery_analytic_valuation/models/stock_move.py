from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves.sudo()._sync_project_delivery_analytic_lines()
        return moves

    def _get_project_analytic_account(self):
        self.ensure_one()
        if not self._is_manual_project_delivery_move():
            return self.env["account.analytic.account"]
        return self._get_project_delivery_analytic_account()

    def _get_project_delivery_analytic_account(self):
        self.ensure_one()
        project = self._get_project_for_analytic_valuation()
        if project:
            return self._get_project_account(project)
        picking = self.picking_id
        return picking._get_project_analytic_account() if picking else self.env["account.analytic.account"]

    def _get_project_for_analytic_valuation(self):
        self.ensure_one()
        projects = self.env["project.project"]
        if "project_id" in self._fields:
            projects |= self.project_id
        if "sale_line_id" in self._fields and self.sale_line_id:
            sale_line = self.sale_line_id
            if "project_id" in sale_line._fields:
                projects |= sale_line.project_id
            if "order_id" in sale_line._fields and "project_id" in sale_line.order_id._fields:
                projects |= sale_line.order_id.project_id
        projects = projects.filtered(lambda project: project and project.account_id)
        return projects if len(projects) == 1 else self.env["project.project"]

    def _get_project_account(self, project):
        self.ensure_one()
        if not project or "account_id" not in project._fields:
            return self.env["account.analytic.account"]
        account = project.account_id
        if account and account.company_id and account.company_id != self.company_id:
            return self.env["account.analytic.account"]
        return account

    def _is_manual_project_delivery_move(self):
        self.ensure_one()
        picking = self.picking_id
        return bool(
            picking
            and picking._is_project_delivery_candidate()
            and self._get_project_analytic_distribution()
        )

    def _get_project_analytic_distribution(self):
        self.ensure_one()
        account = self._get_project_delivery_analytic_account()
        if account:
            return {str(account.id): 100.0}
        return self._get_sale_line_analytic_distribution()

    def _get_sale_line_analytic_distribution(self):
        self.ensure_one()
        if "sale_line_id" not in self._fields or not self.sale_line_id:
            return {}
        sale_line = self.sale_line_id
        if "analytic_distribution" not in sale_line._fields:
            return {}
        return dict(sale_line.analytic_distribution or {})

    def _get_analytic_distribution(self):
        self.ensure_one()
        project_distribution = self._get_project_analytic_distribution()
        if project_distribution:
            return project_distribution
        return super()._get_analytic_distribution()

    def _prepare_analytic_lines(self):
        vals = super()._prepare_analytic_lines()
        self.ensure_one()
        if vals or self.analytic_account_line_ids or not self._is_manual_project_delivery_move():
            return vals
        amount, unit_amount = self._get_project_delivery_analytic_amounts()
        if not amount and not unit_amount:
            return vals
        return self.env["account.analytic.account"]._perform_analytic_distribution(
            self._get_project_analytic_distribution(),
            amount,
            unit_amount,
            self.analytic_account_line_ids,
            self,
        )

    def _get_project_delivery_analytic_amounts(self):
        self.ensure_one()
        unit_amount = self._get_valued_qty()
        if not unit_amount:
            unit_amount = self.product_uom._compute_quantity(self.quantity, self.product_id.uom_id)
        amount = self.value
        if not amount and unit_amount:
            amount = unit_amount * self._get_project_delivery_fallback_price_unit()
        return -abs(amount), unit_amount

    def _get_project_delivery_fallback_price_unit(self):
        self.ensure_one()
        if "sale_line_id" in self._fields and self.sale_line_id:
            sale_line = self.sale_line_id
            if "purchase_price" in sale_line._fields and sale_line.purchase_price:
                return sale_line.purchase_price
        return self.product_id.with_company(self.company_id).standard_price

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
