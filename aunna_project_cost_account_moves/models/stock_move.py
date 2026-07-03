from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    aunna_project_cost_move_count = fields.Integer(
        string="Asientos tecnicos",
        compute="_compute_aunna_project_cost_move_count",
    )

    def _compute_aunna_project_cost_move_count(self):
        Link = self.env["aunna.project.cost.move.link"].sudo()
        for move in self:
            move.aunna_project_cost_move_count = Link.search_count(
                Link._aunna_active_link_domain(move, "stock_delivery")
            )

    def write(self, vals):
        result = super().write(vals)
        watched = {
            "state",
            "analytic_distribution",
            "quantity",
            "quantity_done",
            "product_uom_qty",
            "value",
        }
        if watched.intersection(vals) and not self.env.context.get("aunna_skip_project_cost_moves"):
            self.filtered(
                lambda move: move.state == "done"
            ).sudo()._aunna_sync_stock_delivery_cost_move()
        return result

    def _aunna_sync_stock_delivery_cost_move(self):
        links = self.env["aunna.project.cost.move.link"].sudo()
        result_links = links.browse()
        for move in self:
            if not move._aunna_is_stock_delivery_cost_candidate():
                move._aunna_reverse_stock_delivery_cost_moves()
                continue
            result_links |= move._aunna_create_stock_delivery_cost_move()
        return result_links

    def _aunna_reverse_stock_delivery_cost_moves(self):
        Link = self.env["aunna.project.cost.move.link"].sudo()
        for move in self:
            links = Link.search(Link._aunna_active_link_domain(move, "stock_delivery"))
            links.action_reverse_technical_move()

    def _aunna_is_stock_delivery_cost_candidate(self):
        self.ensure_one()
        company = (self.company_id or self.env.company).sudo()
        if not company.aunna_enable_stock_delivery_cost_moves:
            return False
        if self.state != "done":
            return False
        if not self.picking_id:
            return False
        if self.picking_id.picking_type_code not in ("outgoing", "internal"):
            return False
        if self.location_id and self.location_id.usage != "internal":
            return False
        if hasattr(self.picking_id, "_has_purchase_source") and self.picking_id._has_purchase_source():
            return False
        if hasattr(self, "_is_manual_project_delivery_move"):
            return self._is_manual_project_delivery_move()
        return bool(self.analytic_distribution)

    def _aunna_create_stock_delivery_cost_move(self):
        self.ensure_one()
        company = (self.company_id or self.env.company).sudo()
        distribution = self._aunna_stock_delivery_distribution()
        amount = self._aunna_stock_delivery_cost_amount()
        counterpart = company.aunna_stock_counterpart_account_id or company.aunna_stock_cost_account_id
        label = "COSTE STOCK"
        return self.env["aunna.project.cost.move.link"].sudo()._aunna_create_or_update(
            source=self,
            cost_type="stock_delivery",
            amount=amount,
            date=self._aunna_stock_delivery_date(),
            analytic_distribution=distribution,
            debit_account=company.aunna_stock_cost_account_id,
            credit_account=counterpart,
            journal=company.aunna_cost_move_journal_id,
            label=label,
            auto_post=company.aunna_auto_post_cost_moves,
        )

    def _aunna_stock_delivery_distribution(self):
        self.ensure_one()
        distribution = {}
        if hasattr(self, "_get_project_analytic_distribution"):
            distribution.update(self._get_project_analytic_distribution() or {})
        elif "analytic_distribution" in self._fields and self.analytic_distribution:
            distribution.update(dict(self.analytic_distribution))
        has_source_distribution = bool(distribution)
        if not has_source_distribution:
            return {}
        company = (self.company_id or self.env.company).sudo()
        default_pl = company.aunna_default_stock_pl_analytic_account_id
        if default_pl:
            distribution = self.env[
                "aunna.project.cost.move.link"
            ].sudo()._aunna_distribution_with_default_account(
                distribution,
                default_pl,
            )
        return distribution

    def _aunna_distribution_has_account(self, distribution, account):
        account_id = str(account.id)
        for key, value in (distribution or {}).items():
            if self._aunna_distribution_percentage(distribution, key, value) <= 0.0:
                continue
            if account_id in str(key).split(","):
                return True
        return False

    def _aunna_distribution_percentage(self, distribution, key, value=None):
        try:
            return float(distribution.get(key) if value is None else value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _aunna_stock_delivery_cost_amount(self):
        self.ensure_one()
        if "project_delivery_analytic_cost" in self._fields and self.project_delivery_analytic_cost:
            return abs(self.project_delivery_analytic_cost)
        analytic_lines = self.env["account.analytic.line"]
        if "analytic_account_line_ids" in self._fields:
            analytic_lines = self.analytic_account_line_ids
            if "category" in analytic_lines._fields:
                analytic_lines = analytic_lines.filtered(lambda line: line.category == "picking_entry")
            if "move_line_id" in analytic_lines._fields:
                analytic_lines = analytic_lines.filtered(lambda line: not line.move_line_id)
            amount = abs(sum(analytic_lines.mapped("amount")))
            if amount:
                return amount
        if "stock_valuation_layer_ids" in self._fields:
            amount = abs(sum(self.stock_valuation_layer_ids.mapped("value")))
            if amount:
                return amount
        if "value" in self._fields and self.value:
            return abs(self.value)
        quantity = self._aunna_stock_delivery_quantity()
        if not quantity:
            return 0.0
        uom = self.product_uom or self.product_id.uom_id
        quantity = uom._compute_quantity(quantity, self.product_id.uom_id)
        product = self.product_id.sudo().with_company(self.company_id)
        return abs(quantity * product.standard_price)

    def _aunna_stock_delivery_quantity(self):
        self.ensure_one()
        for field_name in ("quantity", "quantity_done", "product_uom_qty"):
            if field_name in self._fields and self[field_name]:
                return self[field_name]
        return 0.0

    def _aunna_stock_delivery_date(self):
        self.ensure_one()
        picking = self.picking_id
        for record, field_names in (
            (picking, ("date_done", "date", "scheduled_date")),
            (self, ("date",)),
        ):
            for field_name in field_names:
                if record and field_name in record._fields and record[field_name]:
                    return fields.Date.to_date(record[field_name])
        return fields.Date.context_today(self)

    def action_aunna_open_project_cost_moves(self):
        self.ensure_one()
        Link = self.env["aunna.project.cost.move.link"]
        return {
            "type": "ir.actions.act_window",
            "name": "Asientos tecnicos",
            "res_model": "aunna.project.cost.move.link",
            "view_mode": "list,form",
            "domain": Link._aunna_active_link_domain(self, "stock_delivery"),
        }
