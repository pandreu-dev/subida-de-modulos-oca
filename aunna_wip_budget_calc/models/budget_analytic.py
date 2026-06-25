import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


_logger = logging.getLogger(__name__)


class BudgetAnalytic(models.Model):
    _inherit = "budget.analytic"

    wip_recalculation_date = fields.Date(
        string="Fecha recalculo WIP",
        copy=False,
        help="Fecha de corte usada para recalcular teorico, alcanzado y WIP.",
    )
    wip_last_calculation_id = fields.Many2one(
        "aunna.wip.calculation",
        string="Ultimo calculo WIP",
        readonly=True,
        copy=False,
    )
    wip_calculation_count = fields.Integer(
        string="Calculos WIP",
        compute="_compute_wip_calculation_count",
    )

    def _compute_wip_calculation_count(self):
        grouped = self.env["aunna.wip.calculation"].read_group(
            [("budget_id", "in", self.ids)],
            ["budget_id"],
            ["budget_id"],
        )
        count_by_budget = {
            item["budget_id"][0]: item["budget_id_count"]
            for item in grouped
            if item.get("budget_id")
        }
        for budget in self:
            budget.wip_calculation_count = count_by_budget.get(budget.id, 0)

    def action_open_wip_calculation_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Calcular WIP"),
            "res_model": "aunna.wip.calculate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_budget_id": self.id,
                "default_cutoff_date": self.wip_recalculation_date
                or fields.Date.context_today(self),
            },
        }

    def action_calculate_wip(self):
        self.ensure_one()
        cutoff_date = self.wip_recalculation_date or fields.Date.context_today(self)
        calculation = self._aunna_wip_calculate_to_date(cutoff_date, source="manual")
        return {
            "type": "ir.actions.act_window",
            "name": _("Calculo WIP"),
            "res_model": "aunna.wip.calculation",
            "view_mode": "form",
            "res_id": calculation.id,
        }

    def action_reset_wip_recalculation_date(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        calculation = self._aunna_wip_calculate_to_date(today, source="manual")
        return {
            "type": "ir.actions.act_window",
            "name": _("Calculo WIP"),
            "res_model": "aunna.wip.calculation",
            "view_mode": "form",
            "res_id": calculation.id,
        }

    def action_view_wip_calculations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Calculos WIP"),
            "res_model": "aunna.wip.calculation",
            "view_mode": "list,form",
            "domain": [("budget_id", "=", self.id)],
            "context": {"default_budget_id": self.id},
        }

    def _aunna_wip_calculate_to_date(self, cutoff_date, source="manual"):
        self.ensure_one()
        cutoff_date = fields.Date.to_date(cutoff_date)
        if not cutoff_date:
            raise UserError(_("Debes indicar una fecha de calculo."))

        budget_lines = self._aunna_wip_get_budget_lines()
        if not budget_lines:
            raise UserError(_("No se han encontrado lineas de presupuesto para calcular WIP."))

        company = self._aunna_wip_get_company()
        line_commands = []
        notes = []

        for budget_line in budget_lines:
            vals = self._aunna_wip_prepare_line_values(budget_line, cutoff_date, company)
            if vals.get("calculation_note"):
                notes.append(vals["calculation_note"])
            line_commands.append((0, 0, vals))

        calculation = self.env["aunna.wip.calculation"].create(
            {
                "budget_id": self.id,
                "company_id": company.id,
                "cutoff_date": cutoff_date,
                "source": source,
                "note": "\n".join(dict.fromkeys(notes)) or False,
                "line_ids": line_commands,
            }
        )
        self.write(
            {
                "wip_recalculation_date": cutoff_date,
                "wip_last_calculation_id": calculation.id,
            }
        )
        return calculation

    def _aunna_wip_get_company(self):
        self.ensure_one()
        if "company_id" in self._fields and self.company_id:
            return self.company_id
        return self.env.company

    def _aunna_wip_get_budget_lines(self):
        self.ensure_one()
        candidate_fields = [
            "budget_line_ids",
            "line_ids",
            "budget_analytic_line_ids",
            "analytic_budget_line_ids",
            "crossovered_budget_line_ids",
        ]
        for field_name in candidate_fields:
            if field_name in self._fields:
                records = self[field_name]
                if records:
                    return records

        amount_fields = set(self._aunna_wip_amount_field_candidates())
        for field_name, field in self._fields.items():
            if field.type != "one2many":
                continue
            records = self[field_name]
            if not records:
                continue
            if amount_fields.intersection(records._fields):
                return records
        return self.env["aunna.wip.calculation.line"].browse()

    def _aunna_wip_amount_field_candidates(self):
        return [
            "budget_amount",
            "budgeted_amount",
            "planned_amount",
            "amount",
            "planned_amount_currency",
        ]

    def _aunna_wip_get_float(self, record, candidates, default=0.0):
        for field_name in candidates:
            if field_name in record._fields:
                return record[field_name] or default
        return default

    def _aunna_wip_get_date(self, record, candidates):
        for field_name in candidates:
            if field_name in record._fields and record[field_name]:
                return fields.Date.to_date(record[field_name])
        return False

    def _aunna_wip_get_line_dates(self, budget_line):
        date_from = self._aunna_wip_get_date(
            budget_line,
            ["date_from", "start_date", "from_date"],
        ) or self._aunna_wip_get_date(self, ["date_from", "start_date", "from_date"])
        date_to = self._aunna_wip_get_date(
            budget_line,
            ["date_to", "end_date", "to_date"],
        ) or self._aunna_wip_get_date(self, ["date_to", "end_date", "to_date"])
        if not date_from or not date_to:
            raise UserError(
                _("No se han encontrado fechas de periodo para la linea %s.")
                % budget_line.display_name
            )
        return date_from, date_to

    def _aunna_wip_compute_theoretical_amount(self, budgeted_amount, date_from, date_to, cutoff_date):
        if cutoff_date < date_from:
            return 0.0
        if cutoff_date >= date_to:
            return budgeted_amount
        total_days = (date_to - date_from).days + 1
        elapsed_days = (cutoff_date - date_from).days + 1
        if total_days <= 0:
            return 0.0
        return budgeted_amount * elapsed_days / total_days

    def _aunna_wip_get_analytic_accounts(self, budget_line):
        accounts = self.env["account.analytic.account"].browse()
        for record in [budget_line, self]:
            for field_name, field in record._fields.items():
                if getattr(field, "comodel_name", False) != "account.analytic.account":
                    continue
                if field.type == "many2one" and record[field_name]:
                    accounts |= record[field_name]
                elif field.type == "many2many" and record[field_name]:
                    accounts |= record[field_name]
        return accounts

    def _aunna_wip_get_analytic_dimensions(self, budget_line):
        dimensions_by_field = {}
        for record in [budget_line, self]:
            for field_name, field in record._fields.items():
                if getattr(field, "comodel_name", False) != "account.analytic.account":
                    continue
                if field.type not in ("many2one", "many2many"):
                    continue
                accounts = record[field_name]
                if not accounts:
                    continue
                dimensions_by_field.setdefault(
                    field_name,
                    {
                        "source_field": field_name,
                        "source_label": field.string or field_name,
                        "accounts": self.env["account.analytic.account"].browse(),
                    },
                )
                dimensions_by_field[field_name]["accounts"] |= accounts
        return list(dimensions_by_field.values())

    def _aunna_wip_get_account_plan(self, account):
        if "plan_id" in account._fields and account.plan_id:
            return account.plan_id
        if "root_plan_id" in account._fields and account.root_plan_id:
            return account.root_plan_id
        return self.env["account.analytic.plan"].browse()

    def _aunna_wip_get_dimension_plans(self, accounts):
        if "account.analytic.plan" not in self.env.registry:
            return self.env["account.analytic.account"].browse()
        plans = self.env["account.analytic.plan"].browse()
        for account in accounts:
            plan = self._aunna_wip_get_account_plan(account)
            if plan:
                plans |= plan
                if "root_id" in plan._fields and plan.root_id:
                    plans |= plan.root_id
                if "parent_id" in plan._fields and plan.parent_id:
                    plans |= plan.parent_id
        return plans

    def _aunna_wip_get_analytic_line_account_fields(self, AnalyticLine):
        return [
            field_name
            for field_name, field in AnalyticLine._fields.items()
            if field.type == "many2one"
            and field.store
            and getattr(field, "comodel_name", False) == "account.analytic.account"
        ]

    def _aunna_wip_find_analytic_line_field(self, AnalyticLine, dimension, account_fields):
        source_field = dimension["source_field"]
        if source_field in account_fields:
            return source_field

        accounts = dimension["accounts"]
        plans = self._aunna_wip_get_dimension_plans(accounts)
        plan_names = {plan.name.strip().lower() for plan in plans if plan.name}
        plan_field_names = set()
        for plan in plans:
            plan_field_names.update(
                {
                    "x_plan%s_id" % plan.id,
                    "x_plan_%s_id" % plan.id,
                    "x_plan%s" % plan.id,
                    "x_plan_%s" % plan.id,
                }
            )

        for field_name in account_fields:
            if field_name in plan_field_names:
                return field_name
            field = AnalyticLine._fields[field_name]
            field_label = (field.string or "").strip().lower()
            if field_label and field_label in plan_names:
                return field_name
            field_domain = str(getattr(field, "domain", "") or "")
            if plans and any(str(plan.id) in field_domain for plan in plans):
                return field_name
        return False

    def _aunna_wip_get_dimension_domain(self, AnalyticLine, dimension, account_fields):
        accounts = dimension["accounts"]
        field_name = self._aunna_wip_find_analytic_line_field(
            AnalyticLine,
            dimension,
            account_fields,
        )
        if field_name:
            return [(field_name, "in", accounts.ids)]
        return expression.OR(
            [[(field_name, "in", accounts.ids)] for field_name in account_fields]
        )

    def _aunna_wip_get_wip_journal(self):
        journal_id = self.env["ir.config_parameter"].sudo().get_param(
            "aunna_wip_accounting.journal_id"
        )
        try:
            journal_id = int(journal_id or 0)
        except (TypeError, ValueError):
            journal_id = 0
        return self.env["account.journal"].sudo().browse(journal_id).exists()

    def _aunna_wip_get_wip_exclusion_domain(self, AnalyticLine, wip_journal):
        if "move_line_id" not in AnalyticLine._fields:
            return []

        move_line_field = AnalyticLine._fields["move_line_id"]
        MoveLine = self.env[move_line_field.comodel_name]
        domain = []
        if wip_journal and "journal_id" in MoveLine._fields:
            domain = expression.AND(
                [
                    domain,
                    expression.OR(
                        [
                            [("move_line_id", "=", False)],
                            [("move_line_id.journal_id", "!=", wip_journal.id)],
                        ]
                    ),
                ]
            )
        if "name" in MoveLine._fields:
            domain = expression.AND(
                [
                    domain,
                    expression.OR(
                        [
                            [("move_line_id", "=", False)],
                            [("move_line_id.name", "not ilike", "WIP")],
                        ]
                    ),
                ]
            )
        if "move_id" in MoveLine._fields:
            Move = self.env[MoveLine._fields["move_id"].comodel_name]
            if "ref" in Move._fields:
                domain = expression.AND(
                    [
                        domain,
                        expression.OR(
                            [
                                [("move_line_id", "=", False)],
                                [("move_line_id.move_id.ref", "not ilike", "WIP")],
                            ]
                        ),
                    ]
                )
        return domain

    def _aunna_wip_keep_achieved_line(self, line, wip_journal):
        if "move_line_id" not in line._fields or not line.move_line_id:
            return True

        move_line = line.move_line_id
        if "parent_state" in move_line._fields and move_line.parent_state != "posted":
            return False
        if (
            wip_journal
            and "journal_id" in move_line._fields
            and move_line.journal_id == wip_journal
        ):
            return False

        wip_markers = []
        if "name" in move_line._fields and move_line.name:
            wip_markers.append(move_line.name)
        if "move_id" in move_line._fields and move_line.move_id:
            move = move_line.move_id
            if (
                wip_journal
                and "journal_id" in move._fields
                and move.journal_id == wip_journal
            ):
                return False
            if "ref" in move._fields and move.ref:
                wip_markers.append(move.ref)
            if "name" in move._fields and move.name:
                wip_markers.append(move.name)
        return not any("WIP" in marker.upper() for marker in wip_markers)

    def _aunna_wip_log_achieved_lines(self, domain, lines, account_fields):
        amount = sum(lines.mapped("amount"))
        _logger.info("WIP achieved domain: %s", domain)
        _logger.info("WIP achieved analytic line IDs: %s", lines.ids)
        _logger.info("WIP achieved amount: %s", amount)
        for line in lines:
            move_line = line.move_line_id if "move_line_id" in line._fields else False
            journal = False
            if move_line and "journal_id" in move_line._fields:
                journal = move_line.journal_id
            dimension_values = {
                field_name: line[field_name].display_name
                for field_name in account_fields
                if field_name in line._fields and line[field_name]
            }
            _logger.info(
                "WIP achieved line: date=%s name=%s amount=%s dimensions=%s "
                "move_line_id=%s journal_id=%s",
                line.date,
                line.name if "name" in line._fields else False,
                line.amount,
                dimension_values,
                move_line.id if move_line else False,
                journal.id if journal else False,
            )

    def _aunna_wip_get_project(self, analytic_accounts):
        if not analytic_accounts or "project.project" not in self.env.registry:
            return False
        Project = self.env["project.project"].sudo()
        for field_name, field in Project._fields.items():
            if (
                getattr(field, "comodel_name", False) == "account.analytic.account"
                and field.type == "many2one"
            ):
                project = Project.search([(field_name, "in", analytic_accounts.ids)], limit=1)
                if project:
                    return project
        return False

    def _aunna_wip_get_achieved_amount(self, analytic_dimensions, date_from, cutoff_date, company):
        if not analytic_dimensions:
            return 0.0, _("Sin cuenta analitica detectada; alcanzado calculado como 0.")

        AnalyticLine = self.env["account.analytic.line"].sudo()
        required_fields = {"date", "amount"}
        if not required_fields.issubset(set(AnalyticLine._fields)):
            return 0.0, _("No se han encontrado los campos esperados en account.analytic.line.")

        account_fields = self._aunna_wip_get_analytic_line_account_fields(AnalyticLine)
        if not account_fields:
            return 0.0, _("No se han encontrado campos analiticos en account.analytic.line.")

        domain = [
            ("date", ">=", date_from),
            ("date", "<=", cutoff_date),
            ("company_id", "in", [company.id, False]),
        ]
        for dimension in analytic_dimensions:
            domain = expression.AND(
                [
                    domain,
                    self._aunna_wip_get_dimension_domain(
                        AnalyticLine,
                        dimension,
                        account_fields,
                    ),
                ]
            )
        wip_journal = self._aunna_wip_get_wip_journal()
        domain = expression.AND(
            [
                domain,
                self._aunna_wip_get_wip_exclusion_domain(AnalyticLine, wip_journal),
            ]
        )
        lines = AnalyticLine.search(domain)

        lines = lines.filtered(
            lambda line: self._aunna_wip_keep_achieved_line(line, wip_journal)
        )
        self._aunna_wip_log_achieved_lines(domain, lines, account_fields)
        return sum(lines.mapped("amount")), False

    def _aunna_wip_prepare_line_values(self, budget_line, cutoff_date, company):
        date_from, date_to = self._aunna_wip_get_line_dates(budget_line)
        budgeted_amount = self._aunna_wip_get_float(
            budget_line,
            self._aunna_wip_amount_field_candidates(),
        )
        theoretical_amount = self._aunna_wip_compute_theoretical_amount(
            budgeted_amount,
            date_from,
            date_to,
            cutoff_date,
        )
        analytic_accounts = self._aunna_wip_get_analytic_accounts(budget_line)
        analytic_dimensions = self._aunna_wip_get_analytic_dimensions(budget_line)
        achieved_amount, note = self._aunna_wip_get_achieved_amount(
            analytic_dimensions,
            date_from,
            cutoff_date,
            company,
        )
        main_account = analytic_accounts[:1]
        project = self._aunna_wip_get_project(main_account)
        return {
            "budget_line_model": budget_line._name,
            "budget_line_res_id": budget_line.id,
            "budget_line_name": budget_line.display_name,
            "analytic_account_id": main_account.id if main_account else False,
            "project_id": project.id if project else False,
            "date_from": date_from,
            "date_to": date_to,
            "budgeted_amount": budgeted_amount,
            "calculated_theoretical_amount": theoretical_amount,
            "theoretical_amount": theoretical_amount,
            "achieved_amount": achieved_amount,
            "calculated_wip_amount": theoretical_amount - achieved_amount,
            "wip_amount": theoretical_amount - achieved_amount,
            "calculation_note": note,
        }
