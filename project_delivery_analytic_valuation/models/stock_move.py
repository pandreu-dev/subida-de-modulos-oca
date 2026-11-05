from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = ["stock.move", "analytic.mixin"]

    project_delivery_analytic_cost = fields.Monetary(
        string="Project Delivery Cost",
        currency_field="company_currency_id",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._set_project_delivery_analytic_distribution_from_picking()
        return moves

    def write(self, vals):
        result = super().write(vals)
        if "analytic_distribution" in vals and not self.env.context.get("skip_project_delivery_analytic_sync"):
            self.filtered(lambda move: move.state == "done").sudo()._sync_project_delivery_analytic_lines()
        return result

    @api.depends("product_id", "picking_id.project_id", "picking_id.picking_type_id")
    def _compute_analytic_distribution(self):
        """Regla de los traslados internos (Laura, 05/11/2026): con proyecto, cada
        línea va a la cuenta del proyecto al 100 %, salvo los productos de las
        categorías marcadas «al 0 %» (herramientas y EPI). Se recalcula al cambiar el
        producto o el proyecto; un cambio a mano en la línea se respeta hasta entonces.
        Lo validado no se recalcula aquí: el cambio de proyecto de un traslado hecho lo
        aplica stock.picking.write, que además rehace los apuntes."""
        super()._compute_analytic_distribution()
        for move in self:
            if move.state == "done":
                continue
            distribution = move._get_project_delivery_internal_distribution()
            if distribution is None:
                # Fuera de la regla (p. ej. el traslado pasa a ser una entrega): no se
                # queda con el 0 % que había puesto la regla.
                current = move.analytic_distribution or {}
                if not current or any(float(value or 0.0) for value in current.values()):
                    continue
                distribution = dict(move.picking_id.analytic_distribution or {})
            move.analytic_distribution = distribution

    @api.model
    def _apply_project_delivery_rule_to_pending_moves(self, only_empty=False):
        """Aplica la regla a las líneas pendientes de traslados internos con proyecto: al
        instalar (se calcularon antes de marcar las categorías) o al actualizar (vienen
        vacías de antes de 19.0.1.2.0)."""
        moves = self.search([
            ("state", "not in", ("done", "cancel")),
            ("picking_id.picking_type_code", "in",
             self.env["stock.picking"]._get_project_delivery_rule_picking_type_codes()),
            ("picking_id.project_id", "!=", False),
        ])
        for move in moves:
            if only_empty and move.analytic_distribution:
                continue
            distribution = move._get_project_delivery_internal_distribution()
            if distribution is not None:
                move.analytic_distribution = distribution
        return moves

    def _get_project_delivery_internal_distribution(self):
        """Distribución que corresponde a la línea de un traslado interno, o None si
        el movimiento no está sujeto a la regla (entregas, recepciones, traslados que
        vienen de una compra...)."""
        self.ensure_one()
        picking = self.picking_id
        if (
            not picking
            or picking.picking_type_code not in picking._get_project_delivery_rule_picking_type_codes()
            or picking._has_purchase_source()
        ):
            return None
        header = dict(picking.analytic_distribution or {})
        account = self._get_project_account(picking.project_id)
        if not account:
            return header
        distribution = header or {str(account.id): 100.0}
        if self._is_project_delivery_excluded_product():
            return {key: 0.0 for key in distribution}
        return distribution

    def _is_project_delivery_excluded_product(self):
        self.ensure_one()
        category = self.product_id.categ_id
        return bool(category) and category._is_project_delivery_analytic_excluded()

    def _set_project_delivery_analytic_distribution_from_picking(self):
        for move in self:
            if move.analytic_distribution:
                continue
            distribution = move._get_project_delivery_internal_distribution()
            if distribution is None:
                distribution = dict(move.picking_id.analytic_distribution or {})
            if distribution:
                move.analytic_distribution = distribution

    def _action_done(self, cancel_backorder=False):
        self._set_project_delivery_analytic_distribution_from_picking()
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves.sudo()._sync_project_delivery_analytic_lines()
        return moves

    def _get_project_analytic_account(self):
        self.ensure_one()
        if self._is_manual_project_delivery_move():
            return self._get_project_delivery_analytic_account()
        super_method = getattr(super(), "_get_project_analytic_account", None)
        if super_method:
            return super_method()
        return self.env["account.analytic.account"]

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
        if self.analytic_distribution:
            return dict(self.analytic_distribution)
        # Solo para lo pendiente: los movimientos ya hechos sin distribución se
        # imputaron al 100 % y así siguen, igual que sus apuntes.
        if self.state != "done":
            distribution = self._get_project_delivery_internal_distribution()
            if distribution:
                return distribution
        if self.picking_id and self.picking_id.analytic_distribution:
            return dict(self.picking_id.analytic_distribution)
        account = self._get_project_delivery_analytic_account()
        if account:
            return {str(account.id): 100.0}
        return self._get_sale_line_analytic_distribution()

    def _get_project_delivery_account_share(self, account):
        """% del coste del movimiento que va a la cuenta analítica indicada."""
        self.ensure_one()
        account_id = str(account.id)
        share = 0.0
        for key, percentage in (self._get_project_analytic_distribution() or {}).items():
            if account_id in str(key).split(","):
                share += float(percentage or 0.0)
        return share

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
        if self._is_manual_project_delivery_move():
            project_distribution = self._get_project_analytic_distribution()
            if project_distribution:
                return project_distribution
        return super()._get_analytic_distribution()

    def _prepare_analytic_lines(self):
        vals = super()._prepare_analytic_lines()
        self.ensure_one()
        if not self._is_manual_project_delivery_move():
            return vals
        if vals and self._has_project_delivery_analytic_values(vals):
            return vals
        if self._get_project_delivery_analytic_lines():
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

    def _has_project_delivery_analytic_values(self, vals):
        vals_list = vals if isinstance(vals, list) else [vals]
        return any(
            line_vals.get("amount") or line_vals.get("unit_amount")
            for line_vals in vals_list
            if line_vals
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
            amount, _unit_amount = move._get_project_delivery_analytic_amounts()
            move.project_delivery_analytic_cost = amount
            if move._get_project_analytic_distribution():
                move._reset_project_delivery_analytic_lines()
                move._create_analytic_move()

    def _reset_project_delivery_analytic_lines(self):
        self.ensure_one()
        analytic_lines = self._get_project_delivery_analytic_lines()
        if analytic_lines:
            analytic_lines.unlink()

    def _get_project_delivery_analytic_lines(self):
        self.ensure_one()
        analytic_lines = self.analytic_account_line_ids.filtered(
            lambda line: line.category == "picking_entry"
        )
        if "move_line_id" in analytic_lines._fields:
            analytic_lines = analytic_lines.filtered(lambda line: not line.move_line_id)
        return analytic_lines

    def _prepare_analytic_line_values(self, account_field_values, amount, unit_amount):
        vals = super()._prepare_analytic_line_values(account_field_values, amount, unit_amount)
        self.ensure_one()
        if self._is_manual_project_delivery_move() and self._get_project_analytic_distribution():
            vals.update(
                {
                    "name": "%s - %s" % (self.reference, self.product_id.display_name),
                    "ref": self.picking_id.name or self.reference,
                    "category": "picking_entry",
                    # Fecha del movimiento, no la del día en que se regenera el apunte
                    # (al editar la línea o al actualizar el módulo).
                    "date": fields.Date.context_today(self, self.date),
                }
            )
        return vals
