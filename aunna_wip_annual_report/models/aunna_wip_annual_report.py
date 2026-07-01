from datetime import date, datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


MONTHS = [
    ("jan", "Ene", 1),
    ("feb", "Feb", 2),
    ("mar", "Mar", 3),
    ("apr", "Abr", 4),
    ("may", "May", 5),
    ("jun", "Jun", 6),
    ("jul", "Jul", 7),
    ("aug", "Ago", 8),
    ("sep", "Sep", 9),
    ("oct", "Oct", 10),
    ("nov", "Nov", 11),
    ("dec", "Dic", 12),
]

METRICS = [
    ("er", "ER/OE", 10),
    ("invoice", "Facturacion", 20),
    ("recognized_income", "Ingreso reconocido", 30),
    ("real_wip", "WIP real acumulado", 40),
]

MONTH_AMOUNT_DEPENDS = [
    "%s_%s_amount" % (month_key, amount_type)
    for month_key, _month_label, _month_number in MONTHS
    for amount_type in ("prev", "real")
]


class AunnaWipAnnualReport(models.Model):
    _name = "aunna.wip.annual.report"
    _description = "Informe anual WIP por proyecto o cuenta analitica"
    _order = "year desc, company_id, id desc"
    _rec_name = "name"

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )
    year = fields.Integer(
        string="Ejercicio",
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Proyecto",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Cuenta analitica",
        help="Cuenta analitica usada para filtrar ER, facturacion, ingreso reconocido y WIP real.",
    )
    line_ids = fields.One2many(
        "aunna.wip.annual.report.line",
        "report_id",
        string="Lineas",
        copy=True,
    )
    last_real_update = fields.Datetime(
        string="Ultimo recalculo",
        readonly=True,
        copy=False,
    )
    calculation_note = fields.Text(
        string="Notas de calculo",
        readonly=True,
        copy=False,
    )

    @api.depends("year", "company_id", "project_id", "analytic_account_id")
    def _compute_name(self):
        for report in self:
            target = (
                report.project_id.display_name
                or report.analytic_account_id.display_name
                or _("Sin filtro")
            )
            report.name = _("Informe WIP %(year)s - %(target)s") % {
                "year": report.year,
                "target": target,
            }

    @api.constrains("year")
    def _check_year(self):
        for report in self:
            if report.year < 2000 or report.year > 2100:
                raise ValidationError(_("El ejercicio debe estar entre 2000 y 2100."))

    @api.constrains("project_id", "analytic_account_id")
    def _check_analytic_filter(self):
        for report in self:
            if not report._get_filter_analytic_account():
                raise ValidationError(
                    _("Selecciona una cuenta analitica o un proyecto con cuenta analitica.")
                )

    @api.onchange("project_id")
    def _onchange_project_id(self):
        for report in self:
            if report.project_id:
                analytic_account = report._get_project_analytic_account(report.project_id)
                if analytic_account:
                    report.analytic_account_id = analytic_account

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            project_id = vals.get("project_id")
            if project_id and not vals.get("analytic_account_id"):
                analytic_account = self._get_project_analytic_account(
                    self.env["project.project"].browse(project_id)
                )
                if analytic_account:
                    vals["analytic_account_id"] = analytic_account.id
        records = super().create(vals_list)
        records._ensure_metric_lines()
        return records

    def write(self, vals):
        if vals.get("project_id") and "analytic_account_id" not in vals:
            analytic_account = self._get_project_analytic_account(
                self.env["project.project"].browse(vals["project_id"])
            )
            if analytic_account:
                vals = dict(vals, analytic_account_id=analytic_account.id)
        result = super().write(vals)
        self._ensure_metric_lines()
        return result

    def _ensure_metric_lines(self):
        Line = self.env["aunna.wip.annual.report.line"]
        for report in self:
            existing_metrics = set(report.line_ids.mapped("metric"))
            commands = []
            for metric, _label, sequence in METRICS:
                if metric not in existing_metrics:
                    commands.append(
                        {
                            "report_id": report.id,
                            "metric": metric,
                            "sequence": sequence,
                        }
                    )
            if commands:
                Line.create(commands)

    def _get_filter_analytic_account(self):
        self.ensure_one()
        return self.analytic_account_id or self._get_project_analytic_account(self.project_id)

    def _get_project_analytic_account(self, project):
        if not project:
            return self.env["account.analytic.account"]
        for field_name in ("account_id", "analytic_account_id"):
            field = project._fields.get(field_name)
            if (
                field
                and field.type == "many2one"
                and field.comodel_name == "account.analytic.account"
                and project[field_name]
            ):
                return project[field_name]
        for field_name, field in project._fields.items():
            if (
                field.type == "many2one"
                and field.comodel_name == "account.analytic.account"
                and project[field_name]
            ):
                return project[field_name]
        return self.env["account.analytic.account"]

    def action_recalculate_real_values(self):
        for report in self:
            report._ensure_metric_lines()
            real_values = report._collect_real_values()
            for line in report.line_ids:
                vals = {
                    "%s_real_amount" % month_key: real_values[line.metric][month_key]
                    for month_key, _month_label, _month_number in MONTHS
                }
                line.write(vals)
            report.write(
                {
                    "last_real_update": fields.Datetime.now(),
                    "calculation_note": report._build_calculation_note(),
                }
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Informe WIP anual"),
                "message": _("Datos reales recalculados correctamente."),
                "type": "success",
                "sticky": False,
            },
        }

    def _build_calculation_note(self):
        self.ensure_one()
        notes = []
        if not self.company_id.aunnna_wip_income_account_id:
            notes.append(
                _(
                    "Ingreso reconocido: no hay cuenta ingreso WIP configurada en la compania."
                )
            )
        return "\n".join(notes) or False

    def _collect_real_values(self):
        self.ensure_one()
        analytic_account = self._get_filter_analytic_account()
        if not analytic_account:
            raise UserError(
                _("Selecciona una cuenta analitica o un proyecto con cuenta analitica.")
            )

        values = {
            metric: {month_key: 0.0 for month_key, _label, _number in MONTHS}
            for metric, _label, _sequence in METRICS
        }
        running_wip = 0.0
        for month_key, _month_label, month_number in MONTHS:
            start_date, end_date, next_start_date = self._month_period(month_number)
            values["er"][month_key] = self._amount_sale_orders(
                analytic_account,
                start_date,
                next_start_date,
            )
            values["invoice"][month_key] = self._amount_invoices(
                analytic_account,
                start_date,
                end_date,
            )
            values["recognized_income"][month_key] = self._amount_recognized_income(
                analytic_account,
                start_date,
                end_date,
            )
            running_wip += (
                values["recognized_income"][month_key]
                - values["invoice"][month_key]
            )
            values["real_wip"][month_key] = running_wip
        return values

    def _month_period(self, month_number):
        start_date = date(self.year, month_number, 1)
        next_start_date = start_date + relativedelta(months=1)
        end_date = next_start_date - timedelta(days=1)
        return start_date, end_date, next_start_date

    def _amount_sale_orders(self, analytic_account, start_date, next_start_date):
        if "sale.order.line" not in self.env.registry:
            return 0.0
        SaleLine = self.env["sale.order.line"].sudo()
        if "analytic_distribution" not in SaleLine._fields:
            return 0.0

        date_field = self._sale_order_date_field()
        if not date_field:
            return 0.0

        domain = [
            ("order_id.state", "in", ["sale", "done"]),
            ("order_id.company_id", "=", self.company_id.id),
            ("analytic_distribution", "!=", False),
            ("analytic_distribution", "in", [analytic_account.id]),
        ]
        domain = expression.AND(
            [
                domain,
                self._sale_order_line_date_domain(
                    date_field,
                    start_date,
                    next_start_date,
                ),
                self._display_type_domain(SaleLine),
            ]
        )
        amount = 0.0
        for line in SaleLine.search(domain):
            ratio = self._analytic_distribution_ratio(
                line.analytic_distribution,
                analytic_account,
            )
            if ratio:
                amount += (line.price_subtotal or 0.0) * ratio
        return amount

    def _sale_order_date_field(self):
        SaleOrder = self.env["sale.order"]
        for field_name in ("confirmation_date", "date_order"):
            if field_name in SaleOrder._fields:
                return field_name
        return False

    def _sale_order_line_date_domain(self, date_field, start_date, next_start_date):
        field = self.env["sale.order"]._fields[date_field]
        field_name = "order_id.%s" % date_field
        if field.type == "datetime":
            return [
                (
                    field_name,
                    ">=",
                    fields.Datetime.to_string(
                        datetime.combine(start_date, time.min)
                    ),
                ),
                (
                    field_name,
                    "<",
                    fields.Datetime.to_string(
                        datetime.combine(next_start_date, time.min)
                    ),
                ),
            ]
        return [
            (field_name, ">=", fields.Date.to_string(start_date)),
            (field_name, "<", fields.Date.to_string(next_start_date)),
        ]

    def _amount_invoices(self, analytic_account, start_date, end_date):
        MoveLine = self.env["account.move.line"].sudo()
        domain = [
            ("date", ">=", start_date),
            ("date", "<=", end_date),
            ("company_id", "=", self.company_id.id),
            ("analytic_distribution", "!=", False),
            ("analytic_distribution", "in", [analytic_account.id]),
        ]
        domain = expression.AND(
            [
                domain,
                self._posted_move_line_domain(MoveLine),
                self._customer_invoice_domain(),
                self._income_account_domain(),
                self._display_type_domain(MoveLine),
            ]
        )
        return self._sum_move_lines(MoveLine.search(domain), analytic_account)

    def _amount_recognized_income(self, analytic_account, start_date, end_date):
        wip_account = self.company_id.aunnna_wip_income_account_id
        if not wip_account:
            return 0.0

        MoveLine = self.env["account.move.line"].sudo()
        domain = [
            ("date", ">=", start_date),
            ("date", "<=", end_date),
            ("company_id", "=", self.company_id.id),
            ("account_id", "=", wip_account.id),
            ("analytic_distribution", "!=", False),
            ("analytic_distribution", "in", [analytic_account.id]),
        ]
        domain = expression.AND(
            [
                domain,
                self._posted_move_line_domain(MoveLine),
                self._display_type_domain(MoveLine),
            ]
        )
        return self._sum_move_lines(MoveLine.search(domain), analytic_account)

    def _posted_move_line_domain(self, MoveLine):
        if "parent_state" in MoveLine._fields:
            return [("parent_state", "=", "posted")]
        return [("move_id.state", "=", "posted")]

    def _customer_invoice_domain(self):
        Move = self.env["account.move"]
        if "move_type" not in Move._fields:
            return []
        return [("move_id.move_type", "in", ["out_invoice", "out_refund"])]

    def _income_account_domain(self):
        Account = self.env["account.account"]
        domains = []
        if "account_type" in Account._fields:
            domains.append([("account_id.account_type", "in", ["income", "income_other"])])
        if "code" in Account._fields:
            domains.append([("account_id.code", "=like", "7%")])
        return expression.OR(domains) if domains else []

    def _display_type_domain(self, Model):
        if "display_type" not in Model._fields:
            return []
        return expression.OR(
            [
                [("display_type", "=", False)],
                [("display_type", "not in", ["line_section", "line_note"])],
            ]
        )

    def _sum_move_lines(self, move_lines, analytic_account):
        amount = 0.0
        for line in move_lines:
            ratio = self._analytic_distribution_ratio(
                line.analytic_distribution,
                analytic_account,
            )
            if ratio:
                amount += self._move_line_income_amount(line) * ratio
        return amount

    def _move_line_income_amount(self, move_line):
        if "balance" in move_line._fields:
            return -move_line.balance
        debit = move_line.debit if "debit" in move_line._fields else 0.0
        credit = move_line.credit if "credit" in move_line._fields else 0.0
        return credit - debit

    def _analytic_distribution_ratio(self, distribution, analytic_account):
        if not distribution or not analytic_account:
            return 0.0
        analytic_account_id = str(analytic_account.id)
        percentage = 0.0
        for key, value in distribution.items():
            key_parts = [item for item in str(key).split(",") if item]
            if analytic_account_id in key_parts:
                percentage += self._to_float(value)
        return percentage / 100.0

    def _to_float(self, value):
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0


class AunnaWipAnnualReportLine(models.Model):
    _name = "aunna.wip.annual.report.line"
    _description = "Linea informe anual WIP"
    _order = "report_id, sequence, id"

    report_id = fields.Many2one(
        "aunna.wip.annual.report",
        string="Informe",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    metric = fields.Selection(
        [(metric, label) for metric, label, _sequence in METRICS],
        string="Concepto",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="report_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="report_id.currency_id",
        store=True,
        readonly=True,
    )

    for month_key, month_label, _month_number in MONTHS:
        locals()["%s_prev_amount" % month_key] = fields.Monetary(
            string="%s Prev." % month_label,
            currency_field="currency_id",
        )
        locals()["%s_real_amount" % month_key] = fields.Monetary(
            string="%s Real" % month_label,
            currency_field="currency_id",
            readonly=True,
            copy=False,
        )
        locals()["%s_diff_amount" % month_key] = fields.Monetary(
            string="%s Dif." % month_label,
            currency_field="currency_id",
            compute="_compute_diff_and_totals",
        )
    del month_key, month_label, _month_number

    total_prev_amount = fields.Monetary(
        string="Total Prev.",
        currency_field="currency_id",
        compute="_compute_diff_and_totals",
    )
    total_real_amount = fields.Monetary(
        string="Total Real",
        currency_field="currency_id",
        compute="_compute_diff_and_totals",
    )
    total_diff_amount = fields.Monetary(
        string="Total Dif.",
        currency_field="currency_id",
        compute="_compute_diff_and_totals",
    )

    _sql_constraints = [
        (
            "report_metric_unique",
            "unique(report_id, metric)",
            "Cada concepto solo puede aparecer una vez por informe.",
        )
    ]

    @api.depends(*MONTH_AMOUNT_DEPENDS)
    def _compute_diff_and_totals(self):
        for line in self:
            total_prev = 0.0
            total_real = 0.0
            for month_key, _month_label, _month_number in MONTHS:
                prev_amount = line["%s_prev_amount" % month_key] or 0.0
                real_amount = line["%s_real_amount" % month_key] or 0.0
                setattr(line, "%s_diff_amount" % month_key, real_amount - prev_amount)
                total_prev += prev_amount
                total_real += real_amount
            line.total_prev_amount = total_prev
            line.total_real_amount = total_real
            line.total_diff_amount = total_real - total_prev
