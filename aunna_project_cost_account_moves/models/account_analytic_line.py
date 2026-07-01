from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    aunna_project_cost_move_count = fields.Integer(
        string="Asientos tecnicos",
        compute="_compute_aunna_project_cost_move_count",
    )

    def _compute_aunna_project_cost_move_count(self):
        Link = self.env["aunna.project.cost.move.link"].sudo()
        for line in self:
            line.aunna_project_cost_move_count = Link.search_count(
                Link._aunna_active_link_domain(line, "timesheet")
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get("aunna_skip_project_cost_moves"):
            lines.sudo()._aunna_sync_timesheet_cost_move()
        return lines

    def write(self, vals):
        result = super().write(vals)
        watched = {
            "amount",
            "unit_amount",
            "date",
            "account_id",
            "project_id",
            "task_id",
            "employee_id",
            "validated",
            "is_validated",
            "state",
            "analytic_distribution",
        }
        if watched.intersection(vals) and not self.env.context.get("aunna_skip_project_cost_moves"):
            self.sudo()._aunna_sync_timesheet_cost_move()
        return result

    def unlink(self):
        if not self.env.context.get("aunna_skip_project_cost_moves"):
            self.sudo()._aunna_reverse_timesheet_cost_moves()
        return super().unlink()

    def _aunna_reverse_timesheet_cost_moves(self):
        Link = self.env["aunna.project.cost.move.link"].sudo()
        for line in self:
            links = Link.search(Link._aunna_active_link_domain(line, "timesheet"))
            links.action_reverse_technical_move()

    def _aunna_sync_timesheet_cost_move(self, allow_no_validation_field=False):
        links = self.env["aunna.project.cost.move.link"].sudo()
        result_links = links.browse()
        for line in self:
            active_links = links.search(links._aunna_active_link_domain(line, "timesheet"))
            allow_fallback = allow_no_validation_field or bool(active_links)
            if not line._aunna_is_timesheet_cost_candidate(
                allow_no_validation_field=allow_fallback,
            ):
                line._aunna_reverse_timesheet_cost_moves()
                continue
            result_links |= line._aunna_create_timesheet_cost_move()
        return result_links

    def _aunna_is_timesheet_cost_candidate(self, allow_no_validation_field=False):
        self.ensure_one()
        company = (self.company_id or self.env.company).sudo()
        if not company.aunna_enable_timesheet_cost_moves:
            return False
        if "employee_id" not in self._fields or not self.employee_id:
            return False
        if "unit_amount" not in self._fields or not self.unit_amount:
            return False
        if "move_line_id" in self._fields and self.move_line_id:
            return False
        if not self.amount or self.amount >= 0.0:
            return False
        return self._aunna_timesheet_is_validated(
            allow_no_validation_field=allow_no_validation_field,
        )

    def _aunna_timesheet_is_validated(self, allow_no_validation_field=False):
        self.ensure_one()
        for field_name in ("validated", "is_validated", "timesheet_validated"):
            if field_name in self._fields:
                return bool(self[field_name])
        if "state" in self._fields and self.state:
            return self.state in ("validated", "approved", "done", "posted")
        return allow_no_validation_field

    def _aunna_create_timesheet_cost_move(self):
        self.ensure_one()
        company = (self.company_id or self.env.company).sudo()
        distribution = self._aunna_project_cost_analytic_distribution(
            company.aunna_default_timesheet_pl_analytic_account_id
        )
        counterpart = (
            company.aunna_timesheet_counterpart_account_id
            or company.aunna_timesheet_cost_account_id
        )
        label = "COSTE TH"
        return self.env["aunna.project.cost.move.link"].sudo()._aunna_create_or_update(
            source=self,
            cost_type="timesheet",
            amount=abs(self.amount),
            date=self.date or fields.Date.context_today(self),
            analytic_distribution=distribution,
            debit_account=company.aunna_timesheet_cost_account_id,
            credit_account=counterpart,
            journal=company.aunna_cost_move_journal_id,
            label=label,
            auto_post=company.aunna_auto_post_cost_moves,
        )

    def _aunna_project_cost_analytic_distribution(self, default_pl_account=False):
        self.ensure_one()
        distribution = {}
        if "analytic_distribution" in self._fields and self.analytic_distribution:
            distribution.update(dict(self.analytic_distribution))
        for field_name, field in self._fields.items():
            if getattr(field, "comodel_name", False) != "account.analytic.account":
                continue
            if field.type == "many2one" and self[field_name]:
                analytic_account = self[field_name]
                if not self._aunna_distribution_has_account(
                    distribution,
                    analytic_account,
                ):
                    distribution[str(analytic_account.id)] = 100.0
        has_source_distribution = bool(distribution)
        if not has_source_distribution:
            return {}
        if default_pl_account:
            distribution = self.env[
                "aunna.project.cost.move.link"
            ].sudo()._aunna_distribution_with_default_account(
                distribution,
                default_pl_account,
            )
        if self._aunna_distribution_account_count(distribution) < 2:
            return {}
        return distribution

    def _aunna_distribution_has_account(self, distribution, account):
        account_id = str(account.id)
        for key, value in (distribution or {}).items():
            if self._aunna_distribution_percentage(distribution, key, value) <= 0.0:
                continue
            if account_id in str(key).split(","):
                return True
        return False

    def _aunna_distribution_account_count(self, distribution):
        account_ids = set()
        for key, value in (distribution or {}).items():
            if self._aunna_distribution_percentage(distribution, key, value) <= 0.0:
                continue
            account_ids.update(
                item
                for item in str(key).split(",")
                if item and item.isdigit()
            )
        return len(account_ids)

    def _aunna_distribution_percentage(self, distribution, key, value=None):
        try:
            return float(distribution.get(key) if value is None else value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def action_aunna_open_project_cost_moves(self):
        self.ensure_one()
        Link = self.env["aunna.project.cost.move.link"]
        return {
            "type": "ir.actions.act_window",
            "name": "Asientos tecnicos",
            "res_model": "aunna.project.cost.move.link",
            "view_mode": "list,form",
            "domain": Link._aunna_active_link_domain(self, "timesheet"),
        }
