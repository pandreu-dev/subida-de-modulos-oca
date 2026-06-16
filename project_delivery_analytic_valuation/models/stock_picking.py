from odoo import api, models


class StockPicking(models.Model):
    _inherit = ["stock.picking", "analytic.mixin"]

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._propagate_project_delivery_analytic_distribution()
        return pickings

    def write(self, vals):
        result = super().write(vals)
        if "analytic_distribution" in vals or "move_ids" in vals or "move_ids_without_package" in vals:
            self._propagate_project_delivery_analytic_distribution(
                force="analytic_distribution" in vals,
            )
        if "analytic_distribution" in vals:
            self.filtered(lambda picking: picking.state == "done")._sync_project_delivery_analytic_lines()
        return result

    @api.onchange("analytic_distribution")
    def _onchange_project_delivery_analytic_distribution(self):
        self._propagate_project_delivery_analytic_distribution(force=True)

    def button_validate(self):
        result = super().button_validate()
        self._sync_project_delivery_analytic_lines()
        return result

    def _propagate_project_delivery_analytic_distribution(self, force=False):
        for picking in self:
            if not picking.analytic_distribution and not force:
                continue
            distribution = dict(picking.analytic_distribution or {})
            for move in picking.move_ids:
                move.with_context(skip_project_delivery_analytic_sync=True).analytic_distribution = distribution

    def _sync_project_delivery_analytic_lines(self):
        moves = self.move_ids.filtered(
            lambda move: move.state == "done" and move._is_manual_project_delivery_move()
        )
        if moves:
            moves.sudo()._sync_project_delivery_analytic_lines()

    @api.model
    def _sync_existing_project_delivery_analytic_lines(self):
        pickings = self.sudo().search([
            ("state", "=", "done"),
            ("picking_type_code", "in", self._get_project_delivery_picking_type_codes()),
        ])
        pickings._sync_project_delivery_analytic_lines()
        return True

    def _get_project_analytic_account(self):
        self.ensure_one()
        project = self._get_project_for_analytic_valuation()
        return self._get_project_account(project)

    def _get_project_for_analytic_valuation(self):
        self.ensure_one()
        projects = self.env["project.project"]
        if "project_id" in self._fields:
            projects |= self.project_id
        if self._move_model_has_field("project_id"):
            projects |= self.move_ids.mapped("project_id")
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

    def _is_project_delivery_candidate(self):
        self.ensure_one()
        return (
            self.picking_type_code in self._get_project_delivery_picking_type_codes()
            and not self._has_purchase_source()
        )

    @api.model
    def _get_project_delivery_picking_type_codes(self):
        return ("outgoing", "internal")

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
