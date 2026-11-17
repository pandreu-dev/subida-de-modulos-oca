from odoo import api, models


class StockPicking(models.Model):
    _inherit = ["stock.picking", "analytic.mixin"]

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._propagate_project_delivery_analytic_distribution()
        return pickings

    def write(self, vals):
        line_vals = {}
        if "move_ids" in vals and ("project_id" in vals or "picking_type_id" in vals):
            # Las líneas del mismo guardado (p. ej. una herramienta puesta a mano al
            # 100 %) se escriben después de aplicar la regla del proyecto o del tipo.
            vals = dict(vals)
            line_vals = {"move_ids": vals.pop("move_ids")}
        result = super().write(vals)
        if "project_id" in vals:
            self._apply_project_delivery_rule_to_done_moves()
        if line_vals:
            result = super().write(line_vals) and result
            vals = dict(vals, **line_vals)
        if "analytic_distribution" in vals or "move_ids" in vals or "move_ids_without_package" in vals:
            self._propagate_project_delivery_analytic_distribution(
                force="analytic_distribution" in vals,
            )
        if "analytic_distribution" in vals or "project_id" in vals:
            done_pickings = self.filtered(lambda picking: picking.state == "done")
            done_pickings._sync_project_delivery_analytic_lines()
            if "project_id" in vals:
                # Sin proyecto ya no hay coste que imputar: fuera los apuntes previos.
                for move in done_pickings.move_ids.filtered(
                    lambda move: move.state == "done" and not move._is_manual_project_delivery_move()
                ):
                    move.sudo()._reset_project_delivery_analytic_lines()
        return result

    @api.onchange("analytic_distribution")
    def _onchange_project_delivery_analytic_distribution(self):
        self._propagate_project_delivery_analytic_distribution(force=True)

    def button_validate(self):
        result = super().button_validate()
        self._sync_project_delivery_analytic_lines()
        return result

    def _apply_project_delivery_rule_to_done_moves(self):
        """El cálculo automático no toca lo validado: al cambiar el proyecto de un
        traslado hecho, la regla se aplica aquí (y luego se rehacen sus apuntes)."""
        for move in self.filtered(lambda picking: picking.state == "done").move_ids:
            if move.state != "done":
                continue
            distribution = move._get_project_delivery_internal_distribution()
            if distribution is not None:
                move.with_context(skip_project_delivery_analytic_sync=True).analytic_distribution = distribution

    def _create_backorder(self, backorder_moves=None):
        """La parte pendiente conserva la distribución de sus líneas, también la puesta a
        mano: pasarlas al pedido pendiente no cambia ni el producto ni el proyecto."""
        moves = backorder_moves or self.move_ids.filtered(lambda move: move.state not in ("done", "cancel"))
        saved = {move.id: dict(move.analytic_distribution) for move in moves if move.analytic_distribution}
        backorders = super()._create_backorder(backorder_moves=backorder_moves)
        for move in backorders.move_ids:
            if move.id in saved and move.analytic_distribution != saved[move.id]:
                move.with_context(skip_project_delivery_analytic_sync=True).analytic_distribution = saved[move.id]
        return backorders

    def _propagate_project_delivery_analytic_distribution(self, force=False):
        for picking in self:
            if not picking.analytic_distribution and not force:
                continue
            distribution = dict(picking.analytic_distribution or {})
            for move in picking.move_ids:
                if not force and move.analytic_distribution:
                    continue  # sin forzar solo se rellenan las líneas vacías
                move_distribution = move._get_project_delivery_internal_distribution()
                move.with_context(skip_project_delivery_analytic_sync=True).analytic_distribution = (
                    distribution if move_distribution is None else move_distribution
                )

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

    @api.model
    def _get_project_delivery_rule_picking_type_codes(self):
        """Operaciones a las que se aplica la regla 100 % / 0 % por categoría."""
        return ("internal",)

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
