import logging
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

    def _aunna_wip_settings_company(self, company=False):
        if company:
            return company
        if len(self) == 1 and self.company_id:
            return self.company_id
        return self.env.company

    def _aunna_wip_accounting_settings(self, company=False):
        company = self._aunna_wip_settings_company(company).sudo()
        grace_days = company.aunnna_wip_auto_accounting_grace_days or 5
        return {
            "company": company,
            "journal": company.aunnna_wip_journal_id,
            "income_account": company.aunnna_wip_income_account_id,
            "deferred_account": company.aunnna_wip_deferred_account_id,
            "auto_post": company.aunnna_wip_auto_post_moves,
            "allow_negative": company.aunnna_wip_allow_negative_amounts,
            "auto_accounting_enabled": company.aunnna_wip_auto_accounting_enabled,
            "auto_accounting_grace_days": max(1, min(grace_days, 28)),
        }

    def _aunna_wip_check_accounting_settings(self, settings):
        self.ensure_one()
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
        company = self.company_id
        if settings["journal"].company_id != company:
            raise UserError(
                _("El diario WIP configurado no pertenece a la compania %s.")
                % company.display_name
            )
        if settings["journal"].type != "general":
            raise UserError(_("El diario WIP configurado debe ser de tipo Miscelanea."))
        for account, label in [
            (settings["income_account"], _("Cuenta ingreso WIP")),
            (settings["deferred_account"], _("Cuenta ingresos anticipados")),
        ]:
            account_companies = (
                account.sudo().company_ids
                if "company_ids" in account._fields
                else self.env["res.company"].browse()
            )
            company_is_allowed = (
                not account_companies
                or self.env["res.company"].sudo().search_count(
                    [
                        ("id", "=", company.id),
                        ("id", "child_of", account_companies.ids),
                    ],
                    limit=1,
                )
            )
            if not company_is_allowed:
                raise UserError(
                    _("%s no esta disponible para la compania %s.")
                    % (label, company.display_name)
                )

    def _aunna_wip_existing_move(self):
        self.ensure_one()
        return self.search(
            [
                ("id", "!=", self.id),
                ("budget_id", "=", self.budget_id.id),
                ("cutoff_date", "=", self.cutoff_date),
                ("company_id", "=", self.company_id.id),
                ("move_id", "!=", False),
            ],
            limit=1,
        )

    def _aunna_wip_manual_move_since_month_start(
        self,
        budget,
        first_day,
        execution_date,
    ):
        start_datetime = datetime.combine(first_day, datetime.min.time())
        end_datetime = datetime.combine(
            execution_date + timedelta(days=1),
            datetime.min.time(),
        )
        return self.search(
            [
                ("budget_id", "=", budget.id),
                ("source", "=", "manual"),
                ("move_id", "!=", False),
                (
                    "move_id.create_date",
                    ">=",
                    fields.Datetime.to_string(start_datetime),
                ),
                (
                    "move_id.create_date",
                    "<",
                    fields.Datetime.to_string(end_datetime),
                ),
            ],
            limit=1,
        )

    def _aunna_wip_line_analytic_distribution(self, line):
        if not line.analytic_account_id:
            return False
        return {str(line.analytic_account_id.id): 100.0}

    def _aunna_wip_lock_budget(self):
        self.ensure_one()
        self.env.cr.execute(
            f"SELECT id FROM {self.budget_id._table} WHERE id = %s FOR UPDATE",
            [self.budget_id.id],
        )

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
                raise UserError(
                    _(
                        "La linea %s tiene WIP negativo. Activa la opcion correspondiente o revisa el calculo."
                    )
                    % (calc_line.budget_line_name or calc_line.display_name)
                )
            if not calc_line.analytic_account_id:
                raise UserError(
                    _("La linea %s no tiene cuenta analitica. No se crea un asiento sin imputacion.")
                    % (calc_line.budget_line_name or calc_line.display_name)
                )
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

    def _aunna_wip_create_native_reversal(self, move, reversal_date, settings):
        reversal_move = move.with_company(move.company_id)._reverse_moves(
            default_values_list=[
                {
                    "date": reversal_date,
                    "ref": _("Reversion de: %s") % (move.name or move.ref or self.name),
                }
            ],
            cancel=False,
        )
        if settings["auto_post"]:
            today = fields.Date.context_today(self)
            if reversal_date <= today:
                reversal_move.action_post()
            else:
                reversal_move.write({"auto_post": "at_date"})
        return reversal_move

    def action_create_wip_move(self, reversal_date=False):
        self.ensure_one()
        if self.state == "cancelled":
            raise UserError(_("No se puede contabilizar un calculo WIP cancelado."))
        self._aunna_wip_lock_budget()
        self.invalidate_recordset(["move_id"])
        if self.move_id:
            return self.action_open_wip_move()
        duplicate = self._aunna_wip_existing_move()
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

        move = self.env["account.move"].with_company(self.company_id).create(move_vals)
        if settings["auto_post"]:
            move.action_post()

        if not reversal_date:
            reversal_date = fields.Date.to_date(self.cutoff_date) + timedelta(days=1)
        reversal_move = self._aunna_wip_create_native_reversal(
            move,
            fields.Date.to_date(reversal_date),
            settings,
        )

        self.write(
            {
                "journal_id": settings["journal"].id,
                "move_id": move.id,
                "reversal_move_id": reversal_move.id,
                "reversal_date": reversal_date,
                "accounting_state": "posted" if move.state == "posted" else "pending",
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

    def _run_monthly_auto_accounting(
        self,
        execution_date=False,
        budget=False,
        create_moves=True,
        enforce_schedule=True,
    ):
        execution_date = fields.Date.to_date(
            execution_date or fields.Date.context_today(self)
        )
        first_day = execution_date.replace(day=1)
        cutoff_date = first_day - relativedelta(days=1)
        Budget = self.env["budget.analytic"].sudo()
        domain = [("wip_auto_accounting", "=", True)]
        if "state" in Budget._fields:
            domain.append(
                (
                    "state",
                    "in",
                    ["open", "opened", "confirmed", "validate", "validated"],
                )
            )
        if budget and not budget.wip_auto_accounting:
            return {
                "calculations": self.browse(),
                "message": _(
                    "El presupuesto seleccionado no tiene marcada la contabilizacion WIP automatica."
                ),
            }
        if budget:
            domain.append(("id", "=", budget.id))
        budgets = Budget.search(domain)

        calculations = self.browse()
        messages = []
        for current_budget in budgets:
            budget_company = current_budget._aunna_wip_get_company()
            settings = self._aunna_wip_accounting_settings(budget_company)
            if not settings["auto_accounting_enabled"]:
                messages.append(
                    _(
                        "No se genera el automatico para %s: la contabilizacion WIP automatica esta desactivada en la compania %s."
                    )
                    % (current_budget.display_name, budget_company.display_name)
                )
                continue
            trigger_date = first_day + timedelta(
                days=settings["auto_accounting_grace_days"] - 1
            )
            if enforce_schedule and execution_date < trigger_date:
                messages.append(
                    _(
                        "El automatico WIP de %s esperara hasta el %s."
                    )
                    % (current_budget.display_name, trigger_date)
                )
                continue
            manual_calculation = self._aunna_wip_manual_move_since_month_start(
                current_budget,
                first_day,
                execution_date,
            )
            if manual_calculation and create_moves:
                messages.append(
                    _(
                        "No se genera el automatico para %s: ya se creo manualmente un asiento WIP durante el plazo de espera."
                    )
                    % current_budget.display_name
                )
                continue
            existing = self.search(
                [
                    ("budget_id", "=", current_budget.id),
                    ("cutoff_date", "=", cutoff_date),
                    ("company_id", "=", budget_company.id),
                    ("move_id", "!=", False),
                ],
                limit=1,
            )
            if existing and create_moves:
                messages.append(
                    _("Ya existe un asiento WIP para %s a fecha %s.")
                    % (current_budget.display_name, cutoff_date)
                )
                continue
            try:
                with self.env.cr.savepoint():
                    calculation = current_budget._aunna_wip_calculate_to_date(
                        cutoff_date,
                        source="auto",
                    )
                    if create_moves:
                        calculation.action_create_wip_move(reversal_date=first_day)
                calculations |= calculation
            except UserError as error:
                _logger.warning(
                    "No se pudo contabilizar automaticamente el WIP de %s: %s",
                    current_budget.display_name,
                    error,
                )
                messages.append(
                    _("%s: %s") % (current_budget.display_name, str(error))
                )
            except Exception as error:
                _logger.exception(
                    "Fallo inesperado al contabilizar automaticamente el WIP de %s",
                    current_budget.display_name,
                )
                messages.append(
                    _("%s: error inesperado: %s")
                    % (current_budget.display_name, str(error))
                )
        return {
            "calculations": calculations,
            "message": "\n".join(messages),
        }

    def _cron_monthly_auto_accounting(self):
        result = self._run_monthly_auto_accounting()
        if result["message"]:
            _logger.info("Resultado de contabilizacion automatica WIP:\n%s", result["message"])
        return True
