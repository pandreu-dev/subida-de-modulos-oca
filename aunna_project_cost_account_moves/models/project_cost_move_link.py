import hashlib
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class AunnaProjectCostMoveLink(models.Model):
    _name = "aunna.project.cost.move.link"
    _description = "Enlace coste tecnico proyecto"
    _order = "date desc, id desc"

    name = fields.Char(required=True, readonly=True, copy=False)
    source_model = fields.Char(required=True, readonly=True, copy=False, index=True)
    source_res_id = fields.Integer(required=True, readonly=True, copy=False, index=True)
    source_display_name = fields.Char(readonly=True, copy=False)
    cost_type = fields.Selection(
        [
            ("timesheet", "Parte de horas"),
            ("stock_delivery", "Entrega de almacen"),
        ],
        required=True,
        readonly=True,
        copy=False,
        index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Asiento",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    reversed_move_id = fields.Many2one(
        "account.move",
        string="Asiento reverso",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        copy=False,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    amount = fields.Monetary(readonly=True, copy=False)
    date = fields.Date(readonly=True, copy=False, index=True)
    analytic_distribution_snapshot = fields.Text(readonly=True, copy=False)
    analytic_summary = fields.Char(
        string="Analitica",
        compute="_compute_analytic_summary",
    )
    source_hash = fields.Char(readonly=True, copy=False, index=True)
    state = fields.Selection(
        [
            ("active", "Activo"),
            ("reversed", "Revertido"),
            ("cancelled", "Cancelado"),
            ("error", "Error"),
        ],
        default="active",
        required=True,
        copy=False,
        index=True,
    )
    error_message = fields.Text(readonly=True, copy=False)

    def _compute_analytic_summary(self):
        AnalyticAccount = self.env["account.analytic.account"].sudo()
        for link in self:
            summary = ""
            if link.analytic_distribution_snapshot:
                try:
                    distribution = json.loads(link.analytic_distribution_snapshot)
                except (TypeError, ValueError):
                    distribution = {}
                account_ids = set()
                for key in distribution:
                    account_ids.update(
                        int(item)
                        for item in str(key).split(",")
                        if item and item.isdigit()
                    )
                accounts = AnalyticAccount.browse(list(account_ids)).exists()
                summary = " + ".join(accounts.mapped("display_name"))
            link.analytic_summary = summary

    @api.constrains("source_model", "source_res_id", "cost_type", "company_id", "state")
    def _check_single_active_link(self):
        for link in self.filtered(lambda item: item.state == "active"):
            duplicate = self.search(
                [
                    ("id", "!=", link.id),
                    ("source_model", "=", link.source_model),
                    ("source_res_id", "=", link.source_res_id),
                    ("cost_type", "=", link.cost_type),
                    ("company_id", "=", link.company_id.id),
                    ("state", "=", "active"),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("Ya existe un asiento tecnico activo para este origen.")
                )

    @api.model
    def _aunna_generate_pending(self, limit=500):
        result = {"timesheet": 0, "stock": 0, "errors": 0}
        AnalyticLine = self.env["account.analytic.line"]
        if "employee_id" in AnalyticLine._fields:
            lines = AnalyticLine.search(
                [("employee_id", "!=", False), ("amount", "!=", 0)],
                limit=limit,
                order="date asc, id asc",
            )
            for line in lines:
                before = self.search_count(
                    self._aunna_active_link_domain(line, "timesheet")
                )
                link = line._aunna_sync_timesheet_cost_move(
                    allow_no_validation_field=True
                )
                after = self.search_count(
                    self._aunna_active_link_domain(line, "timesheet")
                )
                result["timesheet"] += int(after > before)
                result["errors"] += int(bool(link and link.state == "error"))

        StockMove = self.env["stock.move"]
        if "picking_id" in StockMove._fields:
            moves = StockMove.search(
                [("state", "=", "done"), ("picking_id", "!=", False)],
                limit=limit,
                order="date asc, id asc",
            )
            for move in moves:
                before = self.search_count(
                    self._aunna_active_link_domain(move, "stock_delivery")
                )
                link = move._aunna_sync_stock_delivery_cost_move()
                after = self.search_count(
                    self._aunna_active_link_domain(move, "stock_delivery")
                )
                result["stock"] += int(after > before)
                result["errors"] += int(bool(link and link.state == "error"))
        return result

    @api.model
    def _cron_generate_pending(self):
        self._aunna_generate_pending()
        return True

    @api.model
    def _aunna_active_link_domain(self, source, cost_type):
        company = source.company_id or self.env.company
        return [
            ("source_model", "=", source._name),
            ("source_res_id", "=", source.id),
            ("cost_type", "=", cost_type),
            ("company_id", "=", company.id),
            ("state", "=", "active"),
        ]

    @api.model
    def _aunna_error_link_domain(self, source, cost_type):
        company = source.company_id or self.env.company
        return [
            ("source_model", "=", source._name),
            ("source_res_id", "=", source.id),
            ("cost_type", "=", cost_type),
            ("company_id", "=", company.id),
            ("state", "=", "error"),
        ]

    @api.model
    def _aunna_distribution_snapshot(self, distribution):
        return json.dumps(
            self._aunna_normalize_analytic_distribution(distribution),
            sort_keys=True,
        )

    @api.model
    def _aunna_normalize_analytic_distribution(self, distribution):
        normalized = {}
        for key, value in (distribution or {}).items():
            try:
                percentage = float(value or 0.0)
            except (TypeError, ValueError):
                continue
            if percentage <= 0.0:
                continue
            account_ids = sorted(
                [
                    int(item)
                    for item in str(key).split(",")
                    if item and item.isdigit()
                ]
            )
            if not account_ids:
                continue
            normalized_key = ",".join(str(account_id) for account_id in account_ids)
            normalized[normalized_key] = normalized.get(normalized_key, 0.0) + percentage
        return normalized

    @api.model
    def _aunna_source_hash(self, payload):
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @api.model
    def _aunna_create_or_update(
        self,
        source,
        cost_type,
        amount,
        date,
        analytic_distribution,
        debit_account,
        credit_account,
        journal,
        label,
        auto_post=True,
    ):
        source.ensure_one()
        company = source.company_id or self.env.company
        active_link = self.search(self._aunna_active_link_domain(source, cost_type), limit=1)
        amount = abs(amount or 0.0)
        analytic_distribution = self._aunna_normalize_analytic_distribution(
            analytic_distribution
        )
        if not amount:
            if active_link:
                active_link.action_reverse_technical_move()
            return self.browse()
        if not analytic_distribution:
            if active_link:
                active_link.action_reverse_technical_move()
            return self._aunna_create_error(source, cost_type, date, "Sin distribucion analitica.")
        if not journal or not debit_account or not credit_account:
            if active_link and not self._aunna_link_matches_source(
                active_link,
                amount,
                date,
                analytic_distribution,
            ):
                active_link.action_reverse_technical_move()
            return self._aunna_create_error(
                source,
                cost_type,
                date,
                "Falta diario o cuentas de costes tecnicos.",
            )
        if journal.company_id != company:
            if active_link and not self._aunna_link_matches_source(
                active_link,
                amount,
                date,
                analytic_distribution,
            ):
                active_link.action_reverse_technical_move()
            return self._aunna_create_error(
                source,
                cost_type,
                date,
                "El diario tecnico no pertenece a la compania del origen.",
            )
        for account in debit_account | credit_account:
            if not self._aunna_account_allowed_for_company(account, company):
                if active_link and not self._aunna_link_matches_source(
                    active_link,
                    amount,
                    date,
                    analytic_distribution,
                ):
                    active_link.action_reverse_technical_move()
                return self._aunna_create_error(
                    source,
                    cost_type,
                    date,
                    "Una cuenta tecnica no esta disponible para la compania del origen.",
                )

        payload = {
            "source_model": source._name,
            "source_res_id": source.id,
            "cost_type": cost_type,
            "amount": amount,
            "date": fields.Date.to_date(date),
            "distribution": analytic_distribution,
            "debit_account": debit_account.id,
            "credit_account": credit_account.id,
            "journal": journal.id,
        }
        source_hash = self._aunna_source_hash(payload)
        if active_link and active_link.source_hash == source_hash:
            return active_link
        if active_link:
            active_link.action_reverse_technical_move()
        self.search(self._aunna_error_link_domain(source, cost_type)).write(
            {"state": "cancelled"}
        )

        ref = "%s - %s" % (label, source.display_name)
        move_vals = {
            "move_type": "entry",
            "journal_id": journal.id,
            "date": fields.Date.to_date(date),
            "ref": ref,
            "company_id": company.id,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "name": ref,
                        "account_id": debit_account.id,
                        "debit": amount,
                        "credit": 0.0,
                        "analytic_distribution": analytic_distribution,
                    },
                ),
                (
                    0,
                    0,
                    {
                        "name": _("Compensacion %s") % ref,
                        "account_id": credit_account.id,
                        "debit": 0.0,
                        "credit": amount,
                    },
                ),
            ],
        }
        move = (
            self.env["account.move"]
            .with_context(aunna_skip_project_cost_moves=True)
            .with_company(company)
            .create(move_vals)
        )
        if auto_post:
            move.with_context(aunna_skip_project_cost_moves=True).action_post()
        return self.create(
            {
                "name": ref,
                "source_model": source._name,
                "source_res_id": source.id,
                "source_display_name": source.display_name,
                "cost_type": cost_type,
                "move_id": move.id,
                "company_id": company.id,
                "amount": amount,
                "date": fields.Date.to_date(date),
                "analytic_distribution_snapshot": self._aunna_distribution_snapshot(
                    analytic_distribution
                ),
                "source_hash": source_hash,
                "state": "active",
            }
        )

    @api.model
    def _aunna_link_matches_source(self, link, amount, date, analytic_distribution):
        currency = link.currency_id or link.company_id.currency_id
        same_amount = currency.compare_amounts(link.amount, abs(amount or 0.0)) == 0
        analytic_distribution = self._aunna_normalize_analytic_distribution(
            analytic_distribution
        )
        return (
            same_amount
            and link.date == fields.Date.to_date(date)
            and link.analytic_distribution_snapshot
            == self._aunna_distribution_snapshot(analytic_distribution)
        )

    @api.model
    def _aunna_account_allowed_for_company(self, account, company):
        if not account or not company:
            return False
        if "company_ids" in account._fields:
            allowed_companies = account.sudo().company_ids
            if not allowed_companies:
                return True
            return bool(
                self.env["res.company"].sudo().search(
                    [
                        ("id", "=", company.id),
                        ("id", "child_of", allowed_companies.ids),
                    ],
                    limit=1,
                )
            )
        if "company_id" in account._fields and account.company_id:
            return account.company_id == company
        return True

    @api.model
    def _aunna_create_error(self, source, cost_type, date, message):
        _logger.info(
            "No se genera coste tecnico %s para %s/%s: %s",
            cost_type,
            source._name,
            source.id,
            message,
        )
        company = source.company_id or self.env.company
        vals = {
            "name": "%s - ERROR - %s" % (cost_type, source.display_name),
            "source_model": source._name,
            "source_res_id": source.id,
            "source_display_name": source.display_name,
            "cost_type": cost_type,
            "company_id": company.id,
            "date": fields.Date.to_date(date) or fields.Date.context_today(source),
            "state": "error",
            "error_message": message,
        }
        link = self.search(self._aunna_error_link_domain(source, cost_type), limit=1)
        if link:
            link.write(vals)
            return link
        return self.create(vals)

    def action_reverse_technical_move(self):
        for link in self.filtered(lambda item: item.state == "active"):
            reversed_move = self.env["account.move"]
            if link.move_id and link.move_id.state == "posted":
                reversed_move = link.move_id.with_context(
                    aunna_skip_project_cost_moves=True
                )._reverse_moves(
                    default_values_list=[
                        {
                            "date": fields.Date.context_today(link),
                            "ref": _("Reversion de %s") % (link.move_id.name or link.name),
                        }
                    ],
                    cancel=False,
                )
                reversed_move.with_context(
                    aunna_skip_project_cost_moves=True
                ).action_post()
            elif link.move_id and link.move_id.state == "draft" and hasattr(link.move_id, "button_cancel"):
                link.move_id.with_context(
                    aunna_skip_project_cost_moves=True
                ).button_cancel()
            link.write(
                {
                    "state": "reversed" if reversed_move else "cancelled",
                    "reversed_move_id": reversed_move.id if reversed_move else False,
                }
            )
        return True

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("Este enlace no tiene asiento."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Asiento tecnico"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }

    def action_open_source(self):
        self.ensure_one()
        source = self.env[self.source_model].browse(self.source_res_id).exists()
        if not source:
            raise UserError(_("El origen ya no existe."))
        return {
            "type": "ir.actions.act_window",
            "name": source.display_name,
            "res_model": source._name,
            "view_mode": "form",
            "res_id": source.id,
        }

    def action_recalculate_technical_move(self):
        for link in self:
            source = self.env[link.source_model].browse(link.source_res_id).exists()
            if not source:
                link.write(
                    {
                        "state": "error",
                        "error_message": _("El origen ya no existe."),
                    }
                )
                continue
            if link.state == "active":
                link.action_reverse_technical_move()
            if link.cost_type == "timesheet":
                source._aunna_sync_timesheet_cost_move(
                    allow_no_validation_field=True
                )
            elif link.cost_type == "stock_delivery":
                source._aunna_sync_stock_delivery_cost_move()
        return True
