from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_manual_project_delivery = fields.Boolean(
        string="Manual Project Delivery",
        compute="_compute_is_manual_project_delivery",
    )

    def _compute_is_manual_project_delivery(self):
        for picking in self:
            picking.is_manual_project_delivery = picking._is_manual_project_delivery()

    def _get_project_analytic_account(self):
        self.ensure_one()
        if "project_id" not in self._fields:
            return self.env["account.analytic.account"]
        project = self.project_id
        if not project or "account_id" not in project._fields:
            return self.env["account.analytic.account"]
        account = project.account_id
        if account and account.company_id and account.company_id != self.company_id:
            return self.env["account.analytic.account"]
        return account

    def _is_manual_project_delivery(self):
        self.ensure_one()
        return (
            self.picking_type_code == "outgoing"
            and bool(self._get_project_analytic_account())
            and not self._has_sale_or_purchase_source()
        )

    def _has_sale_or_purchase_source(self):
        self.ensure_one()
        if "sale_id" in self._fields and self.sale_id:
            return True
        if "purchase_id" in self._fields and self.purchase_id:
            return True
        if self.move_ids.filtered(
            lambda move: ("sale_line_id" in move._fields and move.sale_line_id)
            or ("purchase_line_id" in move._fields and move.purchase_line_id)
        ):
            return True
        if "reference_ids" in self._fields and self.reference_ids:
            references = self.reference_ids
            if "sale_ids" in references._fields and references.sale_ids:
                return True
            if "purchase_ids" in references._fields and references.purchase_ids:
                return True
        return self._origin_matches_sale_or_purchase()

    def _origin_matches_sale_or_purchase(self):
        self.ensure_one()
        origin_names = [name.strip() for name in (self.origin or "").split(",") if name.strip()]
        if not origin_names:
            return False
        return self._model_has_name("sale.order", origin_names) or self._model_has_name(
            "purchase.order",
            origin_names,
        )

    def _model_has_name(self, model_name, names):
        try:
            model = self.env[model_name]
        except KeyError:
            return False
        return bool(model.sudo().search_count([("name", "in", names)], limit=1))
