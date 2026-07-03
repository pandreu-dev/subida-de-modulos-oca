import base64
from datetime import date, datetime, time, timedelta
from html import escape
from io import BytesIO

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
METRIC_LABELS = {metric: label for metric, label, _sequence in METRICS}
METRIC_SEQUENCE = {metric: sequence for metric, _label, sequence in METRICS}

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
    date_from = fields.Date(
        string="Desde",
        required=True,
        default=lambda self: date(fields.Date.context_today(self).year, 1, 1),
    )
    date_to = fields.Date(
        string="Hasta",
        required=True,
        default=lambda self: date(fields.Date.context_today(self).year, 12, 31),
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
    period_line_ids = fields.One2many(
        "aunna.wip.annual.report.period.line",
        "report_id",
        string="Detalle mensual",
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
    horizontal_summary_html = fields.Html(
        string="Vista horizontal",
        sanitize=False,
        readonly=True,
        copy=False,
    )

    @api.depends("year", "date_from", "date_to", "company_id", "project_id", "analytic_account_id")
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

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for report in self:
            if report.date_from and report.date_to and report.date_from > report.date_to:
                raise ValidationError(_("La fecha desde no puede ser posterior a la fecha hasta."))

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

    @api.onchange("year")
    def _onchange_year(self):
        for report in self:
            if report.year:
                report.date_from = date(report.year, 1, 1)
                report.date_to = date(report.year, 12, 31)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            year = int(vals.get("year") or fields.Date.context_today(self).year)
            vals.setdefault("date_from", date(year, 1, 1))
            vals.setdefault("date_to", date(year, 12, 31))
            project_id = vals.get("project_id")
            if project_id and not vals.get("analytic_account_id"):
                analytic_account = self._get_project_analytic_account(
                    self.env["project.project"].browse(project_id)
                )
                if analytic_account:
                    vals["analytic_account_id"] = analytic_account.id
        records = super().create(vals_list)
        records._ensure_metric_lines()
        records._ensure_period_lines()
        records._refresh_period_line_flags()
        records._update_horizontal_summary_html()
        return records

    def write(self, vals):
        if self.env.context.get("skip_wip_horizontal_update"):
            return super().write(vals)
        if vals.get("year") and "date_from" not in vals and "date_to" not in vals:
            year = int(vals["year"])
            vals = dict(vals, date_from=date(year, 1, 1), date_to=date(year, 12, 31))
        if vals.get("project_id") and "analytic_account_id" not in vals:
            analytic_account = self._get_project_analytic_account(
                self.env["project.project"].browse(vals["project_id"])
            )
            if analytic_account:
                vals = dict(vals, analytic_account_id=analytic_account.id)
        result = super().write(vals)
        self._ensure_metric_lines()
        if {"date_from", "date_to"}.intersection(vals):
            self._ensure_period_lines()
        if {"date_from", "date_to", "period_line_ids"}.intersection(vals):
            self._refresh_period_line_flags()
        self._update_horizontal_summary_html()
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

    def _ensure_period_lines(self):
        PeriodLine = self.env["aunna.wip.annual.report.period.line"]
        for report in self:
            existing = {
                (line.month_start, line.metric): line
                for line in report.period_line_ids
            }
            to_create = []
            for month_start in report._iter_month_starts():
                for metric, _label, sequence in METRICS:
                    if (month_start, metric) in existing:
                        continue
                    to_create.append(
                        {
                            "report_id": report.id,
                            "month_start": month_start,
                            "metric": metric,
                            "sequence": sequence,
                        }
                    )
            if to_create:
                PeriodLine.create(to_create)

    def _iter_month_starts(self):
        self.ensure_one()
        current = self._month_start(self._get_report_date_from())
        last = self._month_start(self._get_report_date_to())
        while current <= last:
            yield current
            current += relativedelta(months=1)

    def _get_report_date_from(self):
        self.ensure_one()
        return fields.Date.to_date(self.date_from) or date(self.year, 1, 1)

    def _get_report_date_to(self):
        self.ensure_one()
        return fields.Date.to_date(self.date_to) or date(self.year, 12, 31)

    def _month_start(self, value):
        return date(value.year, value.month, 1)

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
            report._ensure_period_lines()
            period_values = report._collect_period_real_values()
            for period_line in report.period_line_ids.filtered("in_report_range"):
                period_line.real_amount = period_values[
                    (period_line.month_start, period_line.metric)
                ]
            report.write(
                {
                    "last_real_update": fields.Datetime.now(),
                    "calculation_note": report._build_calculation_note(),
                }
            )
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_open_period_lines(self):
        self.ensure_one()
        self._ensure_period_lines()
        first_month = self._month_start(self._get_report_date_from())
        last_month = self._month_start(self._get_report_date_to())
        return {
            "type": "ir.actions.act_window",
            "name": _("Detalle WIP mensual"),
            "res_model": "aunna.wip.annual.report.period.line",
            "view_mode": "list,form,pivot",
            "domain": [
                ("report_id", "=", self.id),
                ("month_start", ">=", fields.Date.to_string(first_month)),
                ("month_start", "<=", fields.Date.to_string(last_month)),
            ],
            "context": {"default_report_id": self.id},
        }

    def action_refresh_horizontal_summary(self):
        self._ensure_period_lines()
        self._refresh_period_line_flags()
        self._update_horizontal_summary_html()
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_export_horizontal_xlsx(self):
        self.ensure_one()
        self._ensure_period_lines()
        self._refresh_period_line_flags()
        try:
            import xlsxwriter
        except ImportError as error:
            raise UserError(
                _("No se puede generar el Excel porque falta la libreria xlsxwriter.")
            ) from error

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        self._write_horizontal_xlsx_workbook(workbook)
        workbook.close()
        output.seek(0)

        filename = "%s.xlsx" % self._xlsx_safe_filename(self.name or _("Informe WIP"))
        attachment = self.env["ir.attachment"].sudo().create(
            {
                "name": filename,
                "type": "binary",
                "datas": base64.b64encode(output.read()).decode(),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }

    def _refresh_period_line_flags(self):
        lines = self.env["aunna.wip.annual.report.period.line"].search(
            [("report_id", "in", self.ids)]
        )
        lines._compute_diff_amount()
        lines._compute_is_empty()
        lines._compute_in_report_range()
        lines._compute_amount_flags()

    def _update_horizontal_summary_html(self):
        for report in self:
            html = report._build_horizontal_summary_html()
            if report.id:
                report.with_context(skip_wip_horizontal_update=True).write(
                    {"horizontal_summary_html": html}
                )
            else:
                report.horizontal_summary_html = html

    @api.onchange("period_line_ids")
    def _onchange_period_line_ids_refresh_horizontal_summary(self):
        for report in self:
            report.horizontal_summary_html = report._build_horizontal_summary_html(
                use_unsaved_lines=True
            )

    def _build_calculation_note(self):
        self.ensure_one()
        notes = []
        if not self.company_id.aunnna_wip_income_account_id:
            notes.append(
                _(
                    "Ingreso reconocido: no hay cuenta ingreso WIP configurada en la compania."
                )
            )
        notes.append(
            _(
                "WIP real acumulado: incluye el saldo anterior al primer mes visible."
            )
        )
        return "\n".join(notes) or False

    def _build_horizontal_summary_html(self, use_unsaved_lines=False):
        self.ensure_one()
        months = list(self._iter_month_starts())
        active_lines = self._get_horizontal_period_lines(
            use_unsaved_lines=use_unsaved_lines
        )
        visible_months = self._get_horizontal_visible_months(months, active_lines)

        lines_by_key = {
            (fields.Date.to_date(line.month_start), line.metric): line
            for line in active_lines
        }
        month_labels = {
            month_number: month_label
            for _month_key, month_label, month_number in MONTHS
        }

        html = [
            "<style>",
            ".o_aunna_wip_horizontal_wrap{overflow:auto;max-width:100%;border:1px solid #d8dee6;border-radius:4px;}",
            ".o_aunna_wip_horizontal{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%;font-size:15px;line-height:1.4;}",
            ".o_aunna_wip_horizontal th,.o_aunna_wip_horizontal td{border-right:1px solid #e6e9ed;border-bottom:1px solid #e6e9ed;padding:10px 14px;white-space:nowrap;text-align:right;}",
            ".o_aunna_wip_horizontal thead th{position:sticky;top:0;background:#f6f7f8;z-index:2;font-weight:600;text-align:center;}",
            ".o_aunna_wip_horizontal .o_aunna_wip_sticky{position:sticky;left:0;background:#fff;z-index:3;text-align:left;min-width:240px;font-weight:600;box-shadow:1px 0 0 #d8dee6;}",
            ".o_aunna_wip_horizontal thead .o_aunna_wip_sticky{background:#f6f7f8;z-index:4;}",
            ".o_aunna_wip_prev{background:#f7fbff;}",
            ".o_aunna_wip_real{background:#f7fff9;}",
            ".o_aunna_wip_diff{background:#fffaf4;}",
            ".o_aunna_wip_negative{color:#b42318;font-weight:600;}",
            ".o_aunna_wip_positive{color:#067647;font-weight:600;}",
            ".o_aunna_wip_total{font-weight:700;background:#f3f4f6;}",
            "</style>",
            "<div class='o_aunna_wip_horizontal_wrap'>",
            "<table class='o_aunna_wip_horizontal'>",
            "<thead>",
            "<tr>",
            "<th class='o_aunna_wip_sticky' rowspan='2'>Concepto</th>",
        ]
        for month in visible_months:
            label = "%s %s" % (month_labels.get(month.month, month.month), month.year)
            html.append("<th colspan='3'>%s</th>" % escape(str(label)))
        html.append("<th class='o_aunna_wip_total' colspan='3'>Total</th>")
        html.extend(["</tr>", "<tr>"])
        for _month in visible_months:
            html.extend(
                [
                    "<th class='o_aunna_wip_prev'>Prev.</th>",
                    "<th class='o_aunna_wip_real'>Real</th>",
                    "<th class='o_aunna_wip_diff'>Dif.</th>",
                ]
            )
        html.extend(
            [
                "<th class='o_aunna_wip_total'>Prev.</th>",
                "<th class='o_aunna_wip_total'>Real</th>",
                "<th class='o_aunna_wip_total'>Dif.</th>",
                "</tr>",
                "</thead>",
                "<tbody>",
            ]
        )

        for metric, label, _sequence in METRICS:
            prev_values = []
            real_values = []
            html.append("<tr>")
            html.append(
                "<td class='o_aunna_wip_sticky'>%s</td>" % escape(str(label))
            )
            for month in visible_months:
                line = lines_by_key.get((month, metric))
                prev_amount = line.prev_amount if line else 0.0
                real_amount = line.real_amount if line else 0.0
                diff_amount = line.diff_amount if line else real_amount - prev_amount
                prev_values.append(prev_amount)
                real_values.append(real_amount)
                html.append(
                    "<td class='o_aunna_wip_prev'>%s</td>"
                    % self._format_horizontal_amount(prev_amount)
                )
                html.append(
                    "<td class='o_aunna_wip_real'>%s</td>"
                    % self._format_horizontal_amount(real_amount)
                )
                html.append(
                    "<td class='o_aunna_wip_diff %s'>%s</td>"
                    % (
                        self._horizontal_amount_class(diff_amount),
                        self._format_horizontal_amount(diff_amount),
                    )
                )
            total_prev, total_real = self._horizontal_metric_totals(
                metric,
                prev_values,
                real_values,
            )
            total_diff = total_real - total_prev
            html.append(
                "<td class='o_aunna_wip_total'>%s</td>"
                % self._format_horizontal_amount(total_prev)
            )
            html.append(
                "<td class='o_aunna_wip_total'>%s</td>"
                % self._format_horizontal_amount(total_real)
            )
            html.append(
                "<td class='o_aunna_wip_total %s'>%s</td>"
                % (
                    self._horizontal_amount_class(total_diff),
                    self._format_horizontal_amount(total_diff),
                )
            )
            html.append("</tr>")

        html.extend(["</tbody>", "</table>", "</div>"])
        return "".join(html)

    def _write_horizontal_xlsx_workbook(self, workbook):
        self.ensure_one()
        worksheet = workbook.add_worksheet(_("Informe WIP")[:31])
        months = list(self._iter_month_starts())
        active_lines = self._get_horizontal_period_lines()
        visible_months = self._get_horizontal_visible_months(months, active_lines)
        lines_by_key = {
            (fields.Date.to_date(line.month_start), line.metric): line
            for line in active_lines
        }
        month_labels = {
            month_number: month_label
            for _month_key, month_label, month_number in MONTHS
        }

        title_format = workbook.add_format(
            {"bold": True, "font_size": 16, "bottom": 1}
        )
        label_format = workbook.add_format({"bold": True})
        header_format = workbook.add_format(
            {
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#F3F4F6",
                "border": 1,
            }
        )
        concept_format = workbook.add_format(
            {"bold": True, "bg_color": "#FFFFFF", "border": 1}
        )
        prev_format = workbook.add_format(
            {"num_format": "#,##0.00", "bg_color": "#F7FBFF", "border": 1}
        )
        real_format = workbook.add_format(
            {"num_format": "#,##0.00", "bg_color": "#F7FFF9", "border": 1}
        )
        diff_format = workbook.add_format(
            {"num_format": "#,##0.00", "bg_color": "#FFFAF4", "border": 1}
        )
        total_format = workbook.add_format(
            {"bold": True, "num_format": "#,##0.00", "bg_color": "#F3F4F6", "border": 1}
        )
        negative_format = workbook.add_format(
            {
                "num_format": "#,##0.00",
                "bg_color": "#FFFAF4",
                "font_color": "#B42318",
                "bold": True,
                "border": 1,
            }
        )

        total_columns = 1 + (len(visible_months) * 3) + 3
        worksheet.merge_range(0, 0, 0, total_columns - 1, self.name or "", title_format)
        worksheet.write(2, 0, _("Ejercicio"), label_format)
        worksheet.write(2, 1, self.year)
        worksheet.write(3, 0, _("Desde"), label_format)
        worksheet.write(3, 1, fields.Date.to_string(self._get_report_date_from()))
        worksheet.write(4, 0, _("Hasta"), label_format)
        worksheet.write(4, 1, fields.Date.to_string(self._get_report_date_to()))
        worksheet.write(2, 3, _("Compania"), label_format)
        worksheet.write(2, 4, self.company_id.display_name or "")
        worksheet.write(3, 3, _("Proyecto"), label_format)
        worksheet.write(3, 4, self.project_id.display_name or "")
        worksheet.write(4, 3, _("Cuenta analitica"), label_format)
        worksheet.write(4, 4, self.analytic_account_id.display_name or "")
        worksheet.write(5, 3, _("Ultimo recalculo"), label_format)
        worksheet.write(5, 4, fields.Datetime.to_string(self.last_real_update) if self.last_real_update else "")

        start_row = 7
        worksheet.merge_range(start_row, 0, start_row + 1, 0, _("Concepto"), header_format)
        column = 1
        for month in visible_months:
            label = "%s %s" % (month_labels.get(month.month, month.month), month.year)
            worksheet.merge_range(start_row, column, start_row, column + 2, label, header_format)
            worksheet.write(start_row + 1, column, _("Prev."), header_format)
            worksheet.write(start_row + 1, column + 1, _("Real"), header_format)
            worksheet.write(start_row + 1, column + 2, _("Dif."), header_format)
            column += 3
        worksheet.merge_range(start_row, column, start_row, column + 2, _("Total"), header_format)
        worksheet.write(start_row + 1, column, _("Prev."), header_format)
        worksheet.write(start_row + 1, column + 1, _("Real"), header_format)
        worksheet.write(start_row + 1, column + 2, _("Dif."), header_format)

        row = start_row + 2
        for metric, label, _sequence in METRICS:
            prev_values = []
            real_values = []
            worksheet.write(row, 0, label, concept_format)
            column = 1
            for month in visible_months:
                line = lines_by_key.get((month, metric))
                prev_amount = line.prev_amount if line else 0.0
                real_amount = line.real_amount if line else 0.0
                diff_amount = line.diff_amount if line else real_amount - prev_amount
                prev_values.append(prev_amount)
                real_values.append(real_amount)
                worksheet.write_number(row, column, prev_amount, prev_format)
                worksheet.write_number(row, column + 1, real_amount, real_format)
                worksheet.write_number(
                    row,
                    column + 2,
                    diff_amount,
                    negative_format if diff_amount < 0 else diff_format,
                )
                column += 3
            total_prev, total_real = self._horizontal_metric_totals(
                metric,
                prev_values,
                real_values,
            )
            total_diff = total_real - total_prev
            worksheet.write_number(row, column, total_prev, total_format)
            worksheet.write_number(row, column + 1, total_real, total_format)
            worksheet.write_number(
                row,
                column + 2,
                total_diff,
                negative_format if total_diff < 0 else total_format,
            )
            row += 1

        worksheet.freeze_panes(start_row + 2, 1)
        worksheet.set_column(0, 0, 28)
        worksheet.set_column(1, total_columns - 1, 13)
        worksheet.autofilter(start_row + 1, 0, row - 1, total_columns - 1)
        worksheet.repeat_rows(start_row, start_row + 1)
        worksheet.set_landscape()
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(left=0.3, right=0.3, top=0.5, bottom=0.5)

    def _get_horizontal_visible_months(self, months, active_lines):
        non_empty_months = {
            fields.Date.to_date(line.month_start)
            for line in active_lines
            if not self._horizontal_line_is_empty(line)
        }
        visible_months = [month for month in months if month in non_empty_months]
        return visible_months or months

    def _get_horizontal_period_lines(self, use_unsaved_lines=False):
        self.ensure_one()
        first_month = self._month_start(self._get_report_date_from())
        last_month = self._month_start(self._get_report_date_to())
        report_id = self._origin.id or self.id
        if use_unsaved_lines or not report_id:
            return self.period_line_ids.filtered(
                lambda line: line.month_start
                and first_month <= fields.Date.to_date(line.month_start) <= last_month
            )
        domain = [
            ("report_id", "=", report_id),
            ("month_start", ">=", first_month),
            ("month_start", "<=", last_month),
        ]
        return self.env["aunna.wip.annual.report.period.line"].search(
            domain,
            order="month_start, sequence, id",
        )

    def _horizontal_line_is_empty(self, line):
        prev_amount = line.prev_amount or 0.0
        real_amount = line.real_amount or 0.0
        diff_amount = real_amount - prev_amount
        currency = line.currency_id or line.company_id.currency_id or self.currency_id
        if currency:
            return (
                currency.is_zero(prev_amount)
                and currency.is_zero(real_amount)
                and currency.is_zero(diff_amount)
            )
        return not any([prev_amount, real_amount, diff_amount])

    def _horizontal_metric_totals(self, metric, prev_values, real_values):
        if metric == "real_wip":
            return (
                prev_values[-1] if prev_values else 0.0,
                real_values[-1] if real_values else 0.0,
            )
        return sum(prev_values), sum(real_values)

    def _horizontal_amount_class(self, amount):
        currency = self.currency_id or self.company_id.currency_id
        if currency and currency.is_zero(amount):
            return ""
        if amount > 0:
            return "o_aunna_wip_positive"
        if amount < 0:
            return "o_aunna_wip_negative"
        return ""

    def _format_horizontal_amount(self, amount):
        value = "%.2f" % (amount or 0.0)
        integer, decimals = value.split(".")
        sign = ""
        if integer.startswith("-"):
            sign = "-"
            integer = integer[1:]
        groups = []
        while integer:
            groups.insert(0, integer[-3:])
            integer = integer[:-3]
        return "%s%s,%s" % (sign, ".".join(groups or ["0"]), decimals)

    def _xlsx_safe_filename(self, filename):
        invalid_chars = '<>:"/\\|?*'
        safe = "".join("_" if char in invalid_chars else char for char in filename)
        return safe.strip().strip(".") or "Informe WIP"

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

    def _collect_period_real_values(self):
        self.ensure_one()
        analytic_account = self._get_filter_analytic_account()
        if not analytic_account:
            raise UserError(
                _("Selecciona una cuenta analitica o un proyecto con cuenta analitica.")
            )

        values = {}
        first_month_start = self._month_start(self._get_report_date_from())
        running_wip = (
            self._amount_recognized_income_before(analytic_account, first_month_start)
            - self._amount_invoices_before(analytic_account, first_month_start)
        )
        for month_start in self._iter_month_starts():
            next_start = month_start + relativedelta(months=1)
            month_end = next_start - timedelta(days=1)
            er_amount = self._amount_sale_orders(
                analytic_account,
                month_start,
                next_start,
            )
            invoice_amount = self._amount_invoices(
                analytic_account,
                month_start,
                month_end,
            )
            recognized_amount = self._amount_recognized_income(
                analytic_account,
                month_start,
                month_end,
            )
            running_wip += recognized_amount - invoice_amount
            values[(month_start, "er")] = er_amount
            values[(month_start, "invoice")] = invoice_amount
            values[(month_start, "recognized_income")] = recognized_amount
            values[(month_start, "real_wip")] = running_wip
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

    def _amount_invoices_before(self, analytic_account, before_date):
        MoveLine = self.env["account.move.line"].sudo()
        domain = [
            ("date", "<", before_date),
            ("company_id", "=", self.company_id.id),
            ("analytic_distribution", "!=", False),
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
        ]
        domain = expression.AND(
            [
                domain,
                self._posted_move_line_domain(MoveLine),
                self._display_type_domain(MoveLine),
            ]
        )
        return self._sum_move_lines(MoveLine.search(domain), analytic_account)

    def _amount_recognized_income_before(self, analytic_account, before_date):
        wip_account = self.company_id.aunnna_wip_income_account_id
        if not wip_account:
            return 0.0

        MoveLine = self.env["account.move.line"].sudo()
        domain = [
            ("date", "<", before_date),
            ("company_id", "=", self.company_id.id),
            ("account_id", "=", wip_account.id),
            ("analytic_distribution", "!=", False),
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


class AunnaWipAnnualReportPeriodLine(models.Model):
    _name = "aunna.wip.annual.report.period.line"
    _description = "Detalle mensual informe WIP"
    _order = "report_id, month_start, sequence, id"

    report_id = fields.Many2one(
        "aunna.wip.annual.report",
        string="Informe",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    month_start = fields.Date(
        string="Periodo",
        required=True,
        index=True,
    )
    period_label = fields.Char(
        string="Periodo",
        compute="_compute_period_fields",
        store=True,
    )
    period_year = fields.Integer(
        string="Ejercicio",
        compute="_compute_period_fields",
        store=True,
        index=True,
    )
    period_month = fields.Selection(
        [(str(month_number), month_label) for _key, month_label, month_number in MONTHS],
        string="Mes",
        compute="_compute_period_fields",
        store=True,
        index=True,
    )
    period_quarter = fields.Selection(
        [
            ("q1", "T1"),
            ("q2", "T2"),
            ("q3", "T3"),
            ("q4", "T4"),
        ],
        string="Trimestre",
        compute="_compute_period_fields",
        store=True,
        index=True,
    )
    metric = fields.Selection(
        [(metric, label) for metric, label, _sequence in METRICS],
        string="Concepto",
        required=True,
        readonly=True,
        index=True,
    )
    metric_label = fields.Char(
        string="Concepto",
        compute="_compute_metric_label",
        store=True,
    )
    company_id = fields.Many2one(
        related="report_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    project_id = fields.Many2one(
        related="report_id.project_id",
        store=True,
        readonly=True,
        index=True,
    )
    analytic_account_id = fields.Many2one(
        related="report_id.analytic_account_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="report_id.currency_id",
        store=True,
        readonly=True,
    )
    prev_amount = fields.Monetary(
        string="Prev.",
        currency_field="currency_id",
    )
    real_amount = fields.Monetary(
        string="Real",
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )
    diff_amount = fields.Monetary(
        string="Dif.",
        currency_field="currency_id",
        compute="_compute_diff_amount",
        store=True,
    )
    is_empty = fields.Boolean(
        string="Sin importes",
        compute="_compute_is_empty",
        store=True,
    )
    in_report_range = fields.Boolean(
        string="En rango",
        compute="_compute_in_report_range",
        store=True,
        index=True,
    )
    has_prev_amount = fields.Boolean(
        string="Con previsto",
        compute="_compute_amount_flags",
        store=True,
        index=True,
    )
    has_real_amount = fields.Boolean(
        string="Con real",
        compute="_compute_amount_flags",
        store=True,
        index=True,
    )
    is_current_year = fields.Boolean(
        string="Ano actual",
        compute="_compute_current_period_flags",
        search="_search_is_current_year",
    )
    is_current_month = fields.Boolean(
        string="Mes actual",
        compute="_compute_current_period_flags",
        search="_search_is_current_month",
    )

    _sql_constraints = [
        (
            "report_month_metric_unique",
            "unique(report_id, month_start, metric)",
            "Cada concepto mensual solo puede aparecer una vez por informe.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("skip_wip_horizontal_update"):
            records._aunna_update_parent_horizontal_summary()
        return records

    def write(self, vals):
        reports = self.mapped("report_id")
        result = super().write(vals)
        if not self.env.context.get("skip_wip_horizontal_update"):
            (reports | self.mapped("report_id"))._refresh_period_line_flags()
            (reports | self.mapped("report_id"))._update_horizontal_summary_html()
        return result

    def unlink(self):
        reports = self.mapped("report_id")
        result = super().unlink()
        if not self.env.context.get("skip_wip_horizontal_update"):
            reports._update_horizontal_summary_html()
        return result

    def _aunna_update_parent_horizontal_summary(self):
        reports = self.mapped("report_id")
        reports._refresh_period_line_flags()
        reports._update_horizontal_summary_html()

    @api.depends("month_start")
    def _compute_period_fields(self):
        labels = {month_number: month_label for _key, month_label, month_number in MONTHS}
        for line in self:
            if not line.month_start:
                line.period_label = False
                line.period_year = False
                line.period_month = False
                line.period_quarter = False
                continue
            month_start = fields.Date.to_date(line.month_start)
            line.period_label = "%s %s" % (
                labels.get(month_start.month, str(month_start.month)),
                month_start.year,
            )
            line.period_year = month_start.year
            line.period_month = str(month_start.month)
            line.period_quarter = "q%s" % (((month_start.month - 1) // 3) + 1)

    @api.depends("metric")
    def _compute_metric_label(self):
        for line in self:
            line.metric_label = METRIC_LABELS.get(line.metric, line.metric or "")

    @api.depends("prev_amount", "real_amount")
    def _compute_diff_amount(self):
        for line in self:
            line.diff_amount = (line.real_amount or 0.0) - (line.prev_amount or 0.0)

    @api.depends("prev_amount", "real_amount", "diff_amount")
    def _compute_is_empty(self):
        for line in self:
            currency = line.currency_id or line.company_id.currency_id
            if currency:
                line.is_empty = (
                    currency.is_zero(line.prev_amount)
                    and currency.is_zero(line.real_amount)
                    and currency.is_zero(line.diff_amount)
                )
            else:
                line.is_empty = not any(
                    [line.prev_amount, line.real_amount, line.diff_amount]
                )

    @api.depends("month_start", "report_id.date_from", "report_id.date_to")
    def _compute_in_report_range(self):
        for line in self:
            if not line.month_start or not line.report_id:
                line.in_report_range = False
                continue
            month_start = fields.Date.to_date(line.month_start)
            first_month = line.report_id._month_start(line.report_id._get_report_date_from())
            last_month = line.report_id._month_start(line.report_id._get_report_date_to())
            line.in_report_range = first_month <= month_start <= last_month

    @api.depends("prev_amount", "real_amount")
    def _compute_amount_flags(self):
        for line in self:
            currency = line.currency_id or line.company_id.currency_id
            if currency:
                line.has_prev_amount = not currency.is_zero(line.prev_amount)
                line.has_real_amount = not currency.is_zero(line.real_amount)
            else:
                line.has_prev_amount = bool(line.prev_amount)
                line.has_real_amount = bool(line.real_amount)

    @api.depends("month_start")
    def _compute_current_period_flags(self):
        today = fields.Date.context_today(self)
        current_month = date(today.year, today.month, 1)
        for line in self:
            month_start = fields.Date.to_date(line.month_start)
            line.is_current_year = bool(month_start and month_start.year == today.year)
            line.is_current_month = month_start == current_month

    def _search_is_current_year(self, operator, value):
        today = fields.Date.context_today(self)
        domain = [("period_year", "=", today.year)]
        return self._boolean_search_domain(domain, operator, value)

    def _search_is_current_month(self, operator, value):
        today = fields.Date.context_today(self)
        current_month = date(today.year, today.month, 1)
        next_month = current_month + relativedelta(months=1)
        domain = [
            ("month_start", ">=", current_month),
            ("month_start", "<", next_month),
        ]
        return self._boolean_search_domain(domain, operator, value)

    def _boolean_search_domain(self, domain, operator, value):
        positive = (operator in ("=", "==") and value) or (
            operator in ("!=", "<>") and not value
        )
        return domain if positive else expression.NOT(domain)

    @api.onchange("metric")
    def _onchange_metric(self):
        for line in self:
            line.sequence = METRIC_SEQUENCE.get(line.metric, line.sequence)
