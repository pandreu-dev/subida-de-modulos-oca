from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class AunnaWipCalculation(models.Model):
    _inherit = "aunna.wip.calculation"

    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        readonly=True,
        copy=False,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Asiento WIP",
        readonly=True,
        copy=False,
    )
    reversal_move_id = fields.Many2one(
        "account.move",
        string="Asiento reversion",
        readonly=True,
        copy=False,
    )
    reversal_date = fields.Date(string="Fecha reversion", readonly=True, copy=False)
    accounting_state = fields.Selection(
        [
            ("not_required", "No requerido"),
            ("pending", "Pendiente"),
            ("posted", "Contabilizado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado contable",
        default="pending",
        readonly=True,
        copy=False,
    )
    budget_wip_auto_accounting = fields.Boolean(
        string="Presupuesto con WIP automatico",
        related="budget_id.wip_auto_accounting",
        readonly=True,
    )

    def _get_param_int(self, key):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        return int(value or 0)

    def _get_param_bool(self, key, default=False):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if value in (None, False, ""):
            return default
        return str(value).lower() in {"1", "true", "yes", "on"}

    def _aunna_wip_accounting_settings(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        journal_id = int(get_param("aunna_wip_accounting.journal_id") or 0)
        income_account_id = int(get_param("aunna_wip_accounting.income_account_id") or 0)
        deferred_account_id = int(get_param("aunna_wip_accounting.deferred_account_id") or 0)
        return {
            "journal": self.env["account.journal"].browse(journal_id).exists(),
            "income_account": self.env["account.account"].browse(income_account_id).exists(),
            "deferred_account": self.env["account.account"].browse(deferred_account_id).exists(),
            "auto_post": self._get_param_bool(
                "aunna_wip_accounting.auto_post_moves",
                default=True,
            ),
            "allow_negative": self._get_param_bool(
                "aunna_wip_accounting.allow_negative_amounts",
                default=False,
            ),
            "manual_reversal_days": self._get_param_int(
                "aunna_wip_accounting.manual_reversal_days"
            )
            or 1,
        }

    def _aunna_wip_check_accounting_settings(self, settings):
        missing = []
        if not settings["journal"]:
            missing.append(_("Diario WIP"))
        if not settings["income_account"]:
            missing.append(_("Cuenta ingreso WIP"))
        if not settings["deferred_account"]:
            missing.append(_("Cuenta ingresos anticipados"))
        if missing:
            raise UserError(
                _("Configura antes los siguientes valores WIP: %s.")
                % ", ".join(missing)
            )

    def _aunna_wip_existing_posted_move(self):
        self.ensure_one()
        return self.search(
            [
                ("id", "!=", self.id),
                ("budget_id", "=", self.budget_id.id),
                ("cutoff_date", "=", self.cutoff_date),
                ("company_id", "=", self.company_id.id),
                ("move_id", "!=", False),
                ("accounting_state", "=", "posted"),
            ],
            limit=1,
        )

    def _aunna_wip_line_analytic_distribution(self, line):
        if not line.analytic_account_id:
            return False
        return {str(line.analytic_account_id.id): 100.0}

    def _aunna_wip_move_line_vals(self, account, debit, credit, name, analytic_distribution=False):
        vals = {
            "name": name,
            "account_id": account.id,
            "debit": debit,
            "credit": credit,
        }
        if analytic_distribution:
            vals["analytic_distribution"] = analytic_distribution
        return vals

    def _aunna_wip_prepare_move_vals(self, settings):
        self.ensure_one()
        lines = []
        for calc_line in self.line_ids:
            amount = calc_line.wip_amount
            if not amount:
                continue
            if amount < 0 and not settings["allow_negative"]:
                continue
            abs_amount = abs(amount)
            analytic_distribution = self._aunna_wip_line_analytic_distribution(calc_line)
            line_name = _("WIP %s") % (calc_line.budget_line_name or self.name)

            if amount > 0:
                lines.append(
                    (
                        0,
                        0,
                        self._aunna_wip_move_line_vals(
                            settings["deferred_account"],
                            abs_amount,
                            0.0,
                            line_name,
                        ),
                    )
                )
                lines.append(
                    (
                        0,
                        0,
                        self._aunna_wip_move_line_vals(
                            settings["income_account"],
                            0.0,
                            abs_amount,
                            line_name,
                            analytic_distribution,
                        ),
                    )
                )
            else:
                lines.append(
                    (
                        0,
                        0,
                        self._aunna_wip_move_line_vals(
                            settings["income_account"],
                            abs_amount,
                            0.0,
                            line_name,
                            analytic_distribution,
                        ),
                    )
                )
                lines.append(
                    (
                        0,
                        0,
                        self._aunna_wip_move_line_vals(
                            settings["deferred_account"],
                            0.0,
                            abs_amount,
                            line_name,
                        ),
                    )
                )

        if not lines:
            return False

        return {
            "move_type": "entry",
            "journal_id": settings["journal"].id,
            "date": self.cutoff_date,
            "ref": _("WIP %s") % self.name,
            "company_id": self.company_id.id,
            "line_ids": lines,
        }

    def _aunna_wip_prepare_reversal_vals(self, move, reversal_date):
        line_commands = []
        for line in move.line_ids:
            vals = {
                "name": _("Reversion %s") % (line.name or move.name),
                "account_id": line.account_id.id,
                "debit": line.credit,
                "credit": line.debit,
            }
            if "analytic_distribution" in line._fields and line.analytic_distribution:
                vals["analytic_distribution"] = line.analytic_distribution
            line_commands.append((0, 0, vals))
        return {
            "move_type": "entry",
            "journal_id": move.journal_id.id,
            "date": reversal_date,
            "ref": _("Reversion %s") % (move.name or move.ref or self.name),
            "company_id": move.company_id.id,
            "line_ids": line_commands,
        }

    def action_create_wip_move(self, reversal_date=False):
        self.ensure_one()
        if self.budget_wip_auto_accounting and not reversal_date:
            raise UserError(
                _(
                    "Este presupuesto tiene contabilizacion WIP automatica. "
                    "El asiento se generara por el proceso automatico mensual."
                )
            )
        if self.state == "cancelled":
            raise UserError(_("No se puede contabilizar un calculo WIP cancelado."))
        if self.move_id:
            return self.action_open_wip_move()

        duplicate = self._aunna_wip_existing_posted_move()
        if duplicate:
            raise UserError(
                _(
                    "Ya existe un asiento WIP contabilizado para este presupuesto y fecha: %s."
                )
                % duplicate.move_id.display_name
            )

        settings = self._aunna_wip_accounting_settings()
        self._aunna_wip_check_accounting_settings(settings)
        move_vals = self._aunna_wip_prepare_move_vals(settings)
        if not move_vals:
            self.write({"accounting_state": "not_required"})
            raise UserError(
                _(
                    "El WIP es cero, o negativo sin permiso de configuracion. No se crea asiento."
                )
            )

        move = self.env["account.move"].create(move_vals)
        if settings["auto_post"]:
            move.action_post()

        if not reversal_date:
            reversal_date = fields.Date.to_date(self.cutoff_date) + timedelta(
                days=settings["manual_reversal_days"]
            )
        reversal_move = self.env["account.move"].create(
            self._aunna_wip_prepare_reversal_vals(move, reversal_date)
        )
        if settings["auto_post"]:
            reversal_move.action_post()

        self.write(
            {
                "journal_id": settings["journal"].id,
                "move_id": move.id,
                "reversal_move_id": reversal_move.id,
                "reversal_date": reversal_date,
                "accounting_state": "posted" if settings["auto_post"] else "pending",
            }
        )
        return self.action_open_wip_move()

    def action_open_wip_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asiento WIP"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }

    def action_open_reversal_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asiento reversion WIP"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.reversal_move_id.id,
        }

    def _cron_monthly_auto_accounting(self):
        today = fields.Date.context_today(self)
        if today.day != 1:
            return True
        cutoff_date = today - relativedelta(days=1)
        Budget = self.env["budget.analytic"].sudo()
        domain = [("wip_auto_accounting", "=", True)]
        if "state" in Budget._fields:
            domain.append(
                (
                    "state",
                    "in",
                    ["open", "opened", "confirmed", "validate", "validated", "done"],
                )
            )
        budgets = Budget.search(domain)
        for budget in budgets:
            existing = self.search(
                [
                    ("budget_id", "=", budget.id),
                    ("cutoff_date", "=", cutoff_date),
                    ("company_id", "=", budget._aunna_wip_get_company().id),
                    ("move_id", "!=", False),
                ],
                limit=1,
            )
            if existing:
                continue
            calculation = budget._aunna_wip_calculate_to_date(
                cutoff_date,
                source="auto",
            )
            try:
                calculation.action_create_wip_move(reversal_date=today)
            except UserError:
                continue
        return True
