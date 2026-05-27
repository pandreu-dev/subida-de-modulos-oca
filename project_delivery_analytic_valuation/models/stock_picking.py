from odoo import api, fields, models
from odoo.fields import Domain


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_manual_project_delivery = fields.Boolean(
        string="Manual Project Delivery",
        compute="_compute_is_manual_project_delivery",
    )

    def _compute_is_manual_project_delivery(self):
        for picking in self:
            picking.is_manual_project_delivery = picking._is_manual_project_delivery()

    def button_validate(self):
        result = super().button_validate()
        self._sync_project_delivery_analytic_lines()
        return result

    def _sync_project_delivery_analytic_lines(self):
        moves = self.move_ids.filtered(
            lambda move: move.state == "done" and move._is_manual_project_delivery_move()
        )
        if moves:
            moves.sudo()._sync_project_delivery_analytic_lines()

    @api.model
    def _sync_existing_project_delivery_analytic_lines(self):
        project_domains = self._get_existing_project_delivery_domains()
        if not project_domains:
            return True
        pickings = self.sudo().search(
            [
                ("state", "=", "done"),
                ("picking_type_code", "=", "outgoing"),
                *Domain.OR(project_domains),
            ]
        )
        pickings._sync_project_delivery_analytic_lines()
        return True

    @api.model
    def _get_existing_project_delivery_domains(self):
        domains = []
        if "project_id" in self._fields:
            domains.append([("project_id", "!=", False)])
        if "sale_id" in self._fields and self._model_has_field("sale.order", "project_id"):
            domains.append([("sale_id.project_id", "!=", False)])
        stock_move = self.env["stock.move"]
        if "sale_line_id" in stock_move._fields:
            domains.append([("move_ids.sale_line_id", "!=", False)])
            if self._model_has_field("sale.order.line", "project_id"):
                domains.append([("move_ids.sale_line_id.project_id", "!=", False)])
            if self._model_has_field("sale.order", "project_id"):
                domains.append([("move_ids.sale_line_id.order_id.project_id", "!=", False)])
        return domains

    def _get_project_analytic_account(self):
        self.ensure_one()
        project = self._get_project_for_analytic_valuation()
        return self._get_project_account(project)

    def _get_project_for_analytic_valuation(self):
        self.ensure_one()
        projects = self.env["project.project"]
        if "project_id" in self._fields:
            projects |= self.project_id
        if "sale_id" in self._fields and self.sale_id and "project_id" in self.sale_id._fields:
            projects |= self.sale_id.project_id
        if self._move_model_has_field("sale_line_id"):
            sale_lines = self.move_ids.mapped("sale_line_id")
            if sale_lines:
                if "project_id" in sale_lines._fields:
                    projects |= sale_lines.project_id
                if "order_id" in sale_lines._fields and "project_id" in sale_lines.order_id._fields:
                    projects |= sale_lines.order_id.project_id
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

    def _is_manual_project_delivery(self):
        self.ensure_one()
        return (
            self._is_project_delivery_candidate()
            and bool(self._get_project_analytic_account())
        )

    def _is_project_delivery_candidate(self):
        self.ensure_one()
        return self.picking_type_code == "outgoing" and not self._has_purchase_source()

    def _has_purchase_source(self):
        self.ensure_one()
        if "purchase_id" in self._fields and self.purchase_id:
            return True
        if self.move_ids.filtered(
            lambda move: "purchase_line_id" in move._fields and move.purchase_line_id
        ):
            return True
        if "reference_ids" in self._fields and self.reference_ids:
            references = self.reference_ids
            if "purchase_ids" in references._fields and references.purchase_ids:
                return True
        return self._origin_matches_purchase()

    def _origin_matches_purchase(self):
        self.ensure_one()
        origin_names = [name.strip() for name in (self.origin or "").split(",") if name.strip()]
        if not origin_names:
            return False
        return self._model_has_name("purchase.order", origin_names)

    def _model_has_name(self, model_name, names):
        try:
            model = self.env[model_name]
        except KeyError:
            return False
        return bool(model.sudo().search_count([("name", "in", names)], limit=1))

    def _model_has_field(self, model_name, field_name):
        try:
            model = self.env[model_name]
        except KeyError:
            return False
        return field_name in model._fields

    def _move_model_has_field(self, field_name):
        return field_name in self.env["stock.move"]._fields
