import base64
from datetime import date, timedelta
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
    ("services_income", "Venta de servicios", 10),
    ("products_income", "Venta de productos", 20),
    ("internal_hours", "Horas internas", 30),
    ("external_hours", "Horas externas", 40),
    ("purchase_costs", "Pedidos", 50),
    ("materials", "Stock interno", 60),
    ("expenses", "Gastos", 70),
    ("invoice", "Facturacion", 80),
    ("real_wip", "WIP", 90),
]

# Metricas cuyo valor es un ACUMULADO (no se suman: el Total muestra el ultimo mes).
ACCUMULATED_METRICS = {"real_wip"}

# Cuentas analiticas de coste de horas: las asigna la automatizacion
# "Horas internas/externas Apuntes analiticos" a cada parte de horas segun el
# Tipo empleado (Interno/Externo). Si en Odoo se llaman distinto, ajustar aqui.
INTERNAL_HOURS_ACCOUNT_NAME = "Horas internas"
EXTERNAL_HOURS_ACCOUNT_NAME = "Horas externas"

# Estados de gasto que cuentan como coste real (panel de Rentabilidad del proyecto).
EXPENSE_COST_STATES = ["posted", "in_payment", "paid"]
METRIC_LABELS = {metric: label for metric, label, _sequence in METRICS}
METRIC_SEQUENCE = {metric: sequence for metric, _label, sequence in METRICS}

# Estructura visual (agrupada por secciones) de la "Vista horizontal", pensada para
# parecerse al cuadro de referencia (Ingresos / Costes / PM / WIP).
#
# Cada fila apunta a un "metric" con dato calculado (services_income, invoice,
# real_wip) o a None cuando su fuente todavia no esta definida (Venta de productos,
# lineas de Costes y PM): esas se muestran en la estructura pero en blanco, para que
# se vea el formato sin numeros enganosos hasta que se definan.
REPORT_GROUPS = [
    {
        "label": "Avance",
        "css": "income",
        "rows": [
            {"label": "Venta de servicios", "metric": "services_income"},
            {"label": "Venta de productos", "metric": "products_income"},
        ],
        "total_label": "Total avance",
    },
    {
        "label": "Costes",
        "css": "cost",
        "rows": [
            {"label": "Horas internas", "metric": "internal_hours"},
            {"label": "Horas externas", "metric": "external_hours"},
            # "Pedidos" = total; en la vista horizontal se despliega en una sub-fila
            # por cada Tipo de pedido con datos (ver _build_purchase_type_rows).
            {"label": "Pedidos", "metric": "purchase_costs"},
            {"label": "Stock interno", "metric": "materials"},
            {"label": "Gastos", "metric": "expenses"},
        ],
        "total_label": "Total costes",
    },
    {
        "label": "PM",
        "css": "pm",
        "rows": [
            {"label": "PM (Rentabilidad)", "kind": "pm"},
            {"label": "%PM", "kind": "pm_pct"},
            {"label": "%PM (Acumulado)", "kind": "pm_pct_acc"},
        ],
        "total_label": None,
    },
    {
        "label": "WIP",
        "css": "wip",
        "rows": [
            {"label": "Facturacion", "metric": "invoice"},
            {"label": "WIP", "metric": "real_wip"},
        ],
        "total_label": None,
    },
]

MONTH_AMOUNT_DEPENDS = [
    "%s_%s_amount" % (month_key, amount_type)
    for month_key, _month_label, _month_number in MONTHS
    for amount_type in ("prev", "real")
]


class AunnaWipAnnualReport(models.Model):
    _name = "aunna.wip.annual.report"
    _description = "Informe operativo financiero por proyecto o cuenta analitica"
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
    visible_period_line_ids = fields.One2many(
        "aunna.wip.annual.report.period.line",
        "report_id",
        string="Detalle mensual visible",
        domain=[("in_report_range", "=", True)],
        copy=False,
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
            report.name = _("Informe operativo financiero - %(target)s") % {
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
        period_fields = {
            "date_from",
            "date_to",
            "period_line_ids",
            "visible_period_line_ids",
        }
        if period_fields.intersection(vals):
            self._refresh_period_line_flags()
        self._update_horizontal_summary_html()
        return result

    def _ensure_metric_lines(self):
        """Crea las lineas de concepto que falten, elimina las obsoletas (conceptos
        que ya no existen en METRICS, p.ej. ER/OE) y resincroniza la secuencia para
        respetar el orden definido en METRICS."""
        Line = self.env["aunna.wip.annual.report.line"]
        valid_metrics = {metric for metric, _label, _sequence in METRICS}
        for report in self:
            obsolete = report.line_ids.filtered(
                lambda line: line.metric not in valid_metrics
            )
            if obsolete:
                obsolete.unlink()
            existing = {line.metric: line for line in report.line_ids}
            commands = []
            for metric, _label, sequence in METRICS:
                line = existing.get(metric)
                if line is None:
                    commands.append(
                        {
                            "report_id": report.id,
                            "metric": metric,
                            "sequence": sequence,
                        }
                    )
                elif line.sequence != sequence:
                    line.sequence = sequence
            if commands:
                Line.create(commands)

    def _ensure_period_lines(self):
        """Crea las lineas mensuales que falten, elimina las obsoletas y resincroniza
        la secuencia para respetar el orden definido en METRICS."""
        PeriodLine = self.env["aunna.wip.annual.report.period.line"]
        valid_metrics = {metric for metric, _label, _sequence in METRICS}
        for report in self:
            obsolete = report.period_line_ids.filtered(
                lambda line: line.metric not in valid_metrics
            )
            if obsolete:
                obsolete.with_context(skip_wip_horizontal_update=True).unlink()
            existing = {
                (line.month_start, line.metric): line
                for line in report.period_line_ids
            }
            to_create = []
            for month_start in report._iter_month_starts():
                for metric, _label, sequence in METRICS:
                    line = existing.get((month_start, metric))
                    if line is None:
                        to_create.append(
                            {
                                "report_id": report.id,
                                "month_start": month_start,
                                "metric": metric,
                                "sequence": sequence,
                            }
                        )
                    elif line.sequence != sequence:
                        line.with_context(
                            skip_wip_horizontal_update=True
                        ).sequence = sequence
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
                period_line.real_amount = period_values.get(
                    (period_line.month_start, period_line.metric), 0.0
                )
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
            "name": _("Detalle mensual"),
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

        filename = "%s.xlsx" % self._xlsx_safe_filename(self.name or _("Informe operativo financiero"))
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
        lines = self.env["aunna.wip.annual.report.period.line"].with_context(
            skip_wip_horizontal_update=True
        ).search(
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

    @api.onchange("period_line_ids", "visible_period_line_ids")
    def _onchange_period_line_ids_refresh_horizontal_summary(self):
        for report in self:
            report.horizontal_summary_html = report._build_horizontal_summary_html(
                use_unsaved_lines=True
            )

    def _build_calculation_note(self):
        self.ensure_one()
        notes = [
            _(
                "Ingresos (Venta de servicios = 705 / Venta de productos = resto del 70): "
                "se alimentan de los ASIENTOS WIP (ingreso reconocido), NO de las facturas."
            ),
            _(
                "Facturacion: facturas/abonos de cliente en cuentas del grupo 70."
            ),
            _(
                "WIP: ingreso reconocido acumulado - facturacion acumulada. Sube con los "
                "asientos WIP y baja al facturar; queda a 0 cuando lo facturado alcanza lo "
                "reconocido (y negativo si se factura de mas). El primer mes arrastra el "
                "saldo anterior al rango."
            ),
        ]
        return "\n".join(notes) or False

    def _build_horizontal_summary_html(self, use_unsaved_lines=False):
        self.ensure_one()
        months = list(self._iter_month_starts())
        active_lines = self._get_horizontal_period_lines(
            use_unsaved_lines=use_unsaved_lines
        )
        visible_months = self._get_horizontal_visible_months(months, active_lines)
        # Sub-filas dinamicas de coste por Tipo de pedido (una por tipo con datos).
        purchase_type_rows = self._build_purchase_type_rows(visible_months)

        lines_by_key = {
            (fields.Date.to_date(line.month_start), line.metric): line
            for line in active_lines
        }
        month_labels = {
            month_number: month_label
            for _month_key, month_label, month_number in MONTHS
        }

        def month_pair(metric, month):
            line = lines_by_key.get((month, metric)) if metric else None
            return (
                (line.prev_amount if line else 0.0),
                (line.real_amount if line else 0.0),
            )

        def cells(prev, real, blank=False, pct=False):
            if blank:
                return (
                    "<td class='wv-prev'></td>"
                    "<td class='wv-real'></td>"
                    "<td class='wv-diff'></td>"
                )
            fmt = self._format_horizontal_pct if pct else self._format_horizontal_amount
            diff = real - prev
            return (
                "<td class='wv-prev'>%s</td>"
                "<td class='wv-real'>%s</td>"
                "<td class='wv-diff %s'>%s</td>"
            ) % (
                fmt(prev),
                fmt(real),
                self._horizontal_amount_class(diff),
                fmt(diff),
            )

        # --- PM: Ingresos - Costes; %PM; %PM acumulado ---
        income_metrics = [
            row["metric"]
            for group in REPORT_GROUPS
            if group["css"] == "income"
            for row in group["rows"]
            if row.get("metric")
        ]
        cost_metrics = [
            row["metric"]
            for group in REPORT_GROUPS
            if group["css"] == "cost"
            for row in group["rows"]
            if row.get("metric")
        ]

        def month_totals(metrics, month):
            prev = real = 0.0
            for metric in metrics:
                metric_prev, metric_real = month_pair(metric, month)
                prev += metric_prev
                real += metric_real
            return prev, real

        # Los costes vienen en negativo, asi que PM = Ingresos + Costes.
        pm_by_month = {}
        cum_pm_prev = cum_pm_real = cum_inc_prev = cum_inc_real = 0.0
        for month in visible_months:
            inc_prev, inc_real = month_totals(income_metrics, month)
            cost_prev, cost_real = month_totals(cost_metrics, month)
            pm_prev = inc_prev + cost_prev
            pm_real = inc_real + cost_real
            cum_pm_prev += pm_prev
            cum_pm_real += pm_real
            cum_inc_prev += inc_prev
            cum_inc_real += inc_real
            pm_by_month[month] = {
                "pm": (pm_prev, pm_real),
                "pm_pct": (
                    100.0 * pm_prev / inc_prev if inc_prev else 0.0,
                    100.0 * pm_real / inc_real if inc_real else 0.0,
                ),
                "pm_pct_acc": (
                    100.0 * cum_pm_prev / cum_inc_prev if cum_inc_prev else 0.0,
                    100.0 * cum_pm_real / cum_inc_real if cum_inc_real else 0.0,
                ),
            }
        last_month = visible_months[-1] if visible_months else None
        pm_total = {
            "pm": (cum_pm_prev, cum_pm_real),
            "pm_pct": (
                100.0 * cum_pm_prev / cum_inc_prev if cum_inc_prev else 0.0,
                100.0 * cum_pm_real / cum_inc_real if cum_inc_real else 0.0,
            ),
            "pm_pct_acc": (
                pm_by_month[last_month]["pm_pct_acc"] if last_month else (0.0, 0.0)
            ),
        }

        html = [
            "<style>",
            ".o_aunna_wip_horizontal_wrap{overflow:auto;max-width:100%;border:1px solid #d8dee6;border-radius:4px;}",
            ".o_aunna_wip_horizontal{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%;font-size:14px;line-height:1.35;}",
            ".o_aunna_wip_horizontal th,.o_aunna_wip_horizontal td{border-right:1px solid #e6e9ed;border-bottom:1px solid #e6e9ed;padding:7px 12px;white-space:nowrap;text-align:right;}",
            ".o_aunna_wip_horizontal thead th{position:sticky;top:0;background:#f6f7f8;z-index:3;font-weight:600;text-align:center;}",
            ".wv-grp{position:sticky;left:0;z-index:4;min-width:105px;max-width:105px;text-align:center;font-weight:700;color:#fff;vertical-align:middle;}",
            ".o_aunna_wip_horizontal thead .wv-grp{background:#3c4043;z-index:6;}",
            ".wv-concept{position:sticky;left:105px;z-index:4;background:#fff;text-align:left;min-width:210px;font-weight:600;box-shadow:1px 0 0 #d8dee6;}",
            ".o_aunna_wip_horizontal thead .wv-concept{background:#f6f7f8;z-index:6;}",
            ".wv-prev{background:#f7fbff;}",
            ".wv-real{background:#f7fff9;}",
            ".wv-diff{background:#fffaf4;}",
            ".o_aunna_wip_negative{color:#b42318;font-weight:600;}",
            ".o_aunna_wip_positive{color:#067647;font-weight:600;}",
            ".wv-totcol{font-weight:700;background:#eef0f2;}",
            ".wv-grp-income{background:#1f4e79;}.wv-grp-cost{background:#843c39;}"
            ".wv-grp-pm{background:#375623;}.wv-grp-wip{background:#bf6000;}",
            ".wv-concept-income{background:#dae3f3;}.wv-concept-cost{background:#f2dcdb;}"
            ".wv-concept-pm{background:#e2efda;}.wv-concept-wip{background:#fce4d6;}",
            # Sub-filas de coste por tipo de pedido: color mas claro que Costes.
            ".wv-concept-cost-sub{background:#faf0ef;font-weight:500;padding-left:28px;}",
            # Desplegable de "Pedidos" (CSS puro; si el navegador no soporta :has,"
            # se ven siempre desplegadas).
            ".wv-ped-cb{position:absolute;opacity:0;width:0;height:0;}",
            ".wv-ped-lbl{cursor:pointer;}",
            ".wv-ped-lbl::before{content:'\\25BE  ';color:#843c39;font-size:11px;}",
            ".o_aunna_wip_horizontal tbody tr:has(.wv-ped-cb:not(:checked)) .wv-ped-lbl::before{content:'\\25B8  ';}",
            ".o_aunna_wip_horizontal tbody tr:has(.wv-ped-cb:not(:checked)) ~ tr.wv-type-row{display:none;}",
            ".wv-total-row{font-weight:700;}",
            ".wv-total-income{background:#1f4e79;color:#fff;}"
            ".wv-total-cost{background:#843c39;color:#fff;}",
            "</style>",
            "<div class='o_aunna_wip_horizontal_wrap'>",
            "<table class='o_aunna_wip_horizontal'>",
            "<thead><tr>",
            "<th class='wv-grp' rowspan='2'></th>",
            "<th class='wv-concept' rowspan='2'>Concepto</th>",
        ]
        for month in visible_months:
            label = "%s %s" % (month_labels.get(month.month, month.month), month.year)
            html.append("<th colspan='3'>%s</th>" % escape(str(label)))
        html.append("<th class='wv-totcol' colspan='3'>Total</th>")
        html.append("</tr><tr>")
        for _month in visible_months:
            html.append(
                "<th class='wv-prev'>Prev.</th>"
                "<th class='wv-real'>Real</th>"
                "<th class='wv-diff'>Dif.</th>"
            )
        html.append(
            "<th class='wv-totcol'>Prev.</th>"
            "<th class='wv-totcol'>Real</th>"
            "<th class='wv-totcol'>Dif.</th>"
        )
        html.append("</tr></thead><tbody>")

        for group in REPORT_GROUPS:
            css = group["css"]
            data_metrics = [row["metric"] for row in group["rows"] if row.get("metric")]
            span = len(group["rows"]) + (1 if group.get("total_label") else 0)
            # El grupo Costes incluye las sub-filas dinamicas por tipo de pedido.
            if css == "cost":
                span += len(purchase_type_rows)
            first = True
            for row in group["rows"]:
                metric = row.get("metric")
                kind = row.get("kind")
                is_accumulated = metric in ACCUMULATED_METRICS
                is_pct = kind in ("pm_pct", "pm_pct_acc")
                html.append("<tr>")
                if first:
                    html.append(
                        "<td class='wv-grp wv-grp-%s' rowspan='%d'>%s</td>"
                        % (css, span, escape(group["label"]))
                    )
                    first = False
                if metric == "purchase_costs" and purchase_type_rows:
                    # "Pedidos" con desglose: celda concepto con toggle (desplegable).
                    html.append(
                        "<td class='wv-concept wv-concept-%s'>"
                        "<input type='checkbox' class='wv-ped-cb' id='wv_ped_cb' checked/>"
                        "<label class='wv-ped-lbl' for='wv_ped_cb'>%s</label></td>"
                        % (css, escape(row["label"]))
                    )
                else:
                    html.append(
                        "<td class='wv-concept wv-concept-%s'>%s</td>"
                        % (css, escape(row["label"]))
                    )
                total_prev = total_real = 0.0
                for month in visible_months:
                    if kind:
                        prev, real = pm_by_month[month][kind]
                        html.append(cells(prev, real, pct=is_pct))
                    elif metric:
                        prev, real = month_pair(metric, month)
                        if is_accumulated:
                            total_prev, total_real = prev, real
                        else:
                            total_prev += prev
                            total_real += real
                        html.append(cells(prev, real))
                    else:
                        html.append(cells(0.0, 0.0, blank=True))
                if kind:
                    tprev, treal = pm_total[kind]
                    html.append(cells(tprev, treal, pct=is_pct))
                elif metric:
                    html.append(cells(total_prev, total_real))
                else:
                    html.append(cells(0.0, 0.0, blank=True))
                html.append("</tr>")
                # Sub-filas por tipo de pedido, justo debajo de "Pedidos".
                if metric == "purchase_costs" and purchase_type_rows:
                    for trow in purchase_type_rows:
                        html.append("<tr class='wv-type-row'>")
                        html.append(
                            "<td class='wv-concept wv-concept-cost-sub'>%s</td>"
                            % escape(trow["label"])
                        )
                        for month in visible_months:
                            html.append(
                                cells(0.0, trow["real_by_month"].get(month, 0.0))
                            )
                        html.append(cells(0.0, trow["total_real"]))
                        html.append("</tr>")
            if group.get("total_label"):
                html.append("<tr class='wv-total-row'>")
                html.append(
                    "<td class='wv-concept wv-total-%s'>%s</td>"
                    % (css, escape(group["total_label"]))
                )
                grand_prev = grand_real = 0.0
                if data_metrics:
                    for month in visible_months:
                        month_prev = sum(month_pair(m, month)[0] for m in data_metrics)
                        month_real = sum(month_pair(m, month)[1] for m in data_metrics)
                        grand_prev += month_prev
                        grand_real += month_real
                        html.append(cells(month_prev, month_real))
                    html.append(cells(grand_prev, grand_real))
                else:
                    for _month in visible_months:
                        html.append(cells(0.0, 0.0, blank=True))
                    html.append(cells(0.0, 0.0, blank=True))
                html.append("</tr>")

        html.append("</tbody></table></div>")
        return "".join(html)

    def _write_horizontal_xlsx_workbook(self, workbook):
        self.ensure_one()
        worksheet = workbook.add_worksheet(_("Informe operativo financiero")[:31])
        months = list(self._iter_month_starts())
        active_lines = self._get_horizontal_period_lines()
        visible_months = self._get_horizontal_visible_months(months, active_lines)
        # Sub-filas por Tipo de pedido, desplegables bajo "Pedidos" (outline de Excel:
        # symbols_below=False -> el control +/- queda en la fila resumen "Pedidos").
        purchase_type_rows = self._build_purchase_type_rows(visible_months)
        worksheet.outline_settings(True, False, True, False)
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
        subconcept_format = workbook.add_format(
            {"italic": True, "bg_color": "#FFFFFF", "border": 1, "indent": 1}
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
            # Desglose desplegable por Tipo de pedido, justo debajo de "Pedidos".
            if metric == "purchase_costs" and purchase_type_rows:
                for trow in purchase_type_rows:
                    worksheet.write(row, 0, trow["label"], subconcept_format)
                    column = 1
                    for month in visible_months:
                        real_amount = trow["real_by_month"].get(month, 0.0)
                        worksheet.write_number(row, column, 0.0, prev_format)
                        worksheet.write_number(
                            row, column + 1, real_amount, real_format
                        )
                        worksheet.write_number(
                            row,
                            column + 2,
                            real_amount,
                            negative_format if real_amount < 0 else diff_format,
                        )
                        column += 3
                    type_total = trow["total_real"]
                    worksheet.write_number(row, column, 0.0, total_format)
                    worksheet.write_number(row, column + 1, type_total, total_format)
                    worksheet.write_number(
                        row,
                        column + 2,
                        type_total,
                        negative_format if type_total < 0 else total_format,
                    )
                    worksheet.set_row(row, None, None, {"level": 1})
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
        # Se muestran TODOS los meses del rango del informe, aunque no tengan datos,
        # para no crear confusion (p.ej. que no falte marzo entre febrero y abril).
        return months

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
        if metric in ACCUMULATED_METRICS:
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

    def _format_horizontal_pct(self, value):
        return "%s%%" % self._format_horizontal_amount(value)

    def _xlsx_safe_filename(self, filename):
        invalid_chars = '<>:"/\\|?*'
        safe = "".join("_" if char in invalid_chars else char for char in filename)
        return safe.strip().strip(".") or "Informe operativo financiero"

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
            services = self._amount_income_by_code(
                analytic_account, start_date, end_date, "705%"
            )
            total_income = self._amount_income_by_code(
                analytic_account, start_date, end_date, "70%"
            )
            invoice_amount = self._amount_invoices(
                analytic_account, start_date, end_date
            )
            # WIP = ingreso reconocido acumulado - facturacion acumulada. El ingreso
            # reconocido (asientos WIP) es bruto (no descuenta la factura); al facturar
            # baja el WIP, y queda a 0 cuando lo facturado alcanza lo reconocido.
            running_wip += total_income - invoice_amount
            values["services_income"][month_key] = services
            values["products_income"][month_key] = total_income - services
            values["internal_hours"][month_key] = self._amount_timesheet_cost(
                start_date, end_date, INTERNAL_HOURS_ACCOUNT_NAME
            )
            values["external_hours"][month_key] = self._amount_timesheet_cost(
                start_date, end_date, EXTERNAL_HOURS_ACCOUNT_NAME
            )
            values["purchase_costs"][month_key] = self._amount_purchase_costs(
                analytic_account, start_date, end_date
            )
            values["materials"][month_key] = self._amount_materials(
                analytic_account, start_date, end_date
            )
            values["expenses"][month_key] = self._amount_expenses(
                analytic_account, start_date, end_date
            )
            values["invoice"][month_key] = invoice_amount
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
        # Saldo WIP inicial = (ingreso reconocido acumulado - facturacion acumulada)
        # anterior al rango.
        running_wip = self._amount_income_by_code_before(
            analytic_account, first_month_start, "70%"
        ) - self._amount_invoices_before(analytic_account, first_month_start)
        for month_start in self._iter_month_starts():
            next_start = month_start + relativedelta(months=1)
            month_end = next_start - timedelta(days=1)
            services = self._amount_income_by_code(
                analytic_account, month_start, month_end, "705%"
            )
            total_income = self._amount_income_by_code(
                analytic_account, month_start, month_end, "70%"
            )
            invoice_amount = self._amount_invoices(
                analytic_account, month_start, month_end
            )
            # WIP = ingreso reconocido acumulado - facturacion acumulada.
            running_wip += total_income - invoice_amount
            values[(month_start, "services_income")] = services
            values[(month_start, "products_income")] = total_income - services
            values[(month_start, "internal_hours")] = self._amount_timesheet_cost(
                month_start, month_end, INTERNAL_HOURS_ACCOUNT_NAME
            )
            values[(month_start, "external_hours")] = self._amount_timesheet_cost(
                month_start, month_end, EXTERNAL_HOURS_ACCOUNT_NAME
            )
            values[(month_start, "purchase_costs")] = self._amount_purchase_costs(
                analytic_account, month_start, month_end
            )
            values[(month_start, "materials")] = self._amount_materials(
                analytic_account, month_start, month_end
            )
            values[(month_start, "expenses")] = self._amount_expenses(
                analytic_account, month_start, month_end
            )
            values[(month_start, "invoice")] = invoice_amount
            values[(month_start, "real_wip")] = running_wip
        return values

    def _month_period(self, month_number):
        start_date = date(self.year, month_number, 1)
        next_start_date = start_date + relativedelta(months=1)
        end_date = next_start_date - timedelta(days=1)
        return start_date, end_date, next_start_date

    def _amount_timesheet_cost(self, start_date, end_date, account_name):
        """Coste de horas del proyecto del informe en el mes (parte de horas).

        Los partes de horas son apuntes analiticos (`account.analytic.line`) con el
        `project_id` del informe. Una automatizacion les asigna, en un **plan
        analitico aparte (P&L)**, la cuenta "Horas internas" / "Horas externas"
        segun el Tipo empleado. Esa cuenta **NO es** la cuenta analitica principal
        de la linea (`account_id`, que es la del proyecto), sino **otra columna de
        plan**; por eso se busca en **cualquier** columna de cuenta analitica de la
        linea. Se suma su **Importe** (`amount`, el coste, en negativo), igual que
        el panel de Rentabilidad del proyecto.
        """
        AAL = self.env["account.analytic.line"].sudo()
        project = self.project_id
        if not project or "project_id" not in AAL._fields:
            return 0.0
        # Columnas de la linea que apuntan a una cuenta analitica: una por plan
        # (Proyecto, P&L, Departamento, Division...). La clasificacion Horas
        # internas/externas vive en el plan P&L, no en `account_id`.
        plan_fields = [
            name
            for name, field in AAL._fields.items()
            if field.type == "many2one"
            and field.comodel_name == "account.analytic.account"
        ]
        lines = AAL.search(
            [
                ("project_id", "=", project.id),
                ("date", ">=", start_date),
                ("date", "<=", end_date),
            ]
        )
        total = 0.0
        for line in lines:
            # Solo se imputan los partes de horas VALIDADOS (peticion de negocio: un
            # parte en borrador no debe reflejarse en el informe). Mismo criterio que
            # aunna_project_cost_account_moves para que el informe y el asiento de
            # coste (COSTE TH) cuenten lo mismo.
            if not self._is_timesheet_line_validated(line):
                continue
            if any(line[name].name == account_name for name in plan_fields):
                total += line.amount
        return total

    def _is_timesheet_line_validated(self, line):
        """True si el parte de horas esta validado. Replica el criterio de
        ``aunna_project_cost_account_moves._aunna_timesheet_is_validated``: campo
        estandar ``validated`` (hr_timesheet) en Odoo 19; si no existe, ``state``; y
        si no hay ninguno (validacion no instalada), no filtra (cuenta todo)."""
        for field_name in ("validated", "is_validated", "timesheet_validated"):
            if field_name in line._fields:
                return bool(line[field_name])
        if "state" in line._fields and line.state:
            return line.state in ("validated", "approved", "done", "posted")
        return True

    def _amount_materials(self, analytic_account, start_date, end_date):
        """Materiales: coste de material de entrega (albaran) imputado a la cuenta
        analitica del proyecto, en el mes, igual que la fila "Materiales" del panel de
        Rentabilidad.

        Un mismo movimiento fisico de entrega genera VARIOS apuntes analiticos: la
        linea manual canonica (SIN ``move_line_id``, fechada en la fecha EFECTIVA de
        validacion del albaran) y, ademas, con ``move_line_id``, la de la valoracion
        de stock nativa (fechada en la fecha contable/prevista) y la del asiento
        tecnico COSTE STOCK. Sumarlas todas duplicaba el coste y lo imputaba tambien
        en la fecha prevista. Se replica la deduplicacion del panel nativo
        (``_get_domain_aal_with_no_move_line``): contar SOLO las lineas SIN
        ``move_line_id``. Eso ademas subsume el capado de cuentas de INGRESO (esos
        apuntes siempre llevan ``move_line_id``) y las exclusiones de gasto/compra.
        """
        AAL = self.env["account.analytic.line"].sudo()
        if "timesheet_invoice_type" not in AAL._fields:
            return 0.0
        domain = [
            ("account_id", "=", analytic_account.id),
            ("company_id", "=", self.company_id.id),
            ("timesheet_invoice_type", "=", "other_costs"),
            ("amount", "<", 0),
            ("date", ">=", start_date),
            ("date", "<=", end_date),
        ]
        if "category" in AAL._fields:
            domain.append(("category", "!=", "vendor_bill"))
        # Deduplicacion (clave del arreglo): del mismo movimiento de entrega solo se
        # cuenta la linea manual SIN move_line_id (fecha efectiva de validacion). Las
        # lineas CON move_line_id (valoracion de stock en fecha prevista y asiento
        # tecnico COSTE STOCK) son el MISMO coste fisico -> se descartan, como en el
        # panel de Rentabilidad.
        if "move_line_id" in AAL._fields:
            domain.append(("move_line_id", "=", False))
        return sum(AAL.search(domain).mapped("amount"))

    def _amount_expenses(self, analytic_account, start_date, end_date):
        """Gastos: gastos de empleado (`hr.expense`) imputados a la cuenta analitica
        del proyecto, en negativo (panel de Rentabilidad). No se pondera por el % de
        distribucion analitica (el panel toma el importe integro)."""
        if "hr.expense" not in self.env:
            return 0.0
        Expense = self.env["hr.expense"].sudo()
        if "analytic_distribution" not in Expense._fields:
            return 0.0
        amount_field = (
            "untaxed_amount_currency"
            if "untaxed_amount_currency" in Expense._fields
            else "total_amount"
        )
        expenses = Expense.search(
            [
                ("state", "in", EXPENSE_COST_STATES),
                ("company_id", "=", self.company_id.id),
                ("analytic_distribution", "in", [analytic_account.id]),
                ("date", ">=", start_date),
                ("date", "<=", end_date),
            ]
        )
        company = self.company_id
        company_currency = company.currency_id
        # `untaxed_amount_currency` va en la divisa del gasto (hay que convertir);
        # el fallback `total_amount` ya va en divisa de compania (no se convierte).
        needs_convert = amount_field == "untaxed_amount_currency"
        total = 0.0
        for expense in expenses:
            amount = expense[amount_field] or 0.0
            currency = expense.currency_id
            if needs_convert and currency and company_currency and currency != company_currency:
                amount = currency._convert(
                    amount, company_currency, company, expense.date or start_date
                )
            total += amount
        return -total

    def _purchase_order_costs_by_type(self, analytic_account, start_date, end_date):
        """Coste de pedidos de compra CONFIRMADOS (aceptados) imputados a la cuenta
        analitica del informe, agrupado por Tipo de pedido.

        A diferencia de la version anterior (que tiraba de facturas de proveedor),
        el coste sale del **pedido de compra aceptado aunque no este facturado**
        (como el panel de Rentabilidad del proyecto): en cuanto se confirma un
        pedido, su coste ya aparece. La **fecha de referencia** es la de
        **confirmacion del pedido** (`date_approve`, o `date_order` si falta). El
        importe es el subtotal sin impuestos de cada linea, ponderado por su % de
        distribucion analitica y en negativo (coste).

        Devuelve un dict ``{type_id (o False si el pedido no tiene tipo): importe}``.
        """
        if "purchase.order.line" not in self.env:
            return {}
        POL = self.env["purchase.order.line"].sudo()
        if "analytic_distribution" not in POL._fields:
            return {}
        lines = POL.search(
            [
                ("order_id.state", "in", ["purchase", "done"]),
                ("company_id", "=", self.company_id.id),
                ("analytic_distribution", "in", [analytic_account.id]),
            ]
        )
        result = {}
        for line in lines:
            order = line.order_id
            ref = order.date_approve or order.date_order
            ref_date = fields.Date.to_date(ref) if ref else False
            if not ref_date or ref_date < start_date or ref_date > end_date:
                continue
            ratio = self._analytic_distribution_ratio(
                line.analytic_distribution, analytic_account
            )
            if not ratio:
                continue
            amount = -(line.price_subtotal or 0.0) * ratio
            if not amount:
                continue
            type_id = (
                order.aunna_purchase_order_type_id.id
                if "aunna_purchase_order_type_id" in order._fields
                else False
            )
            result[type_id] = result.get(type_id, 0.0) + amount
        return result

    def _amount_purchase_costs(self, analytic_account, start_date, end_date):
        """Pedidos: coste total de pedidos de compra confirmados en el mes = suma de
        todos los tipos (ver ``_purchase_order_costs_by_type``)."""
        return sum(
            self._purchase_order_costs_by_type(
                analytic_account, start_date, end_date
            ).values()
        )

    def _build_purchase_type_rows(self, visible_months):
        """Sub-filas dinamicas de coste por Tipo de pedido para la vista horizontal.

        Una fila por cada tipo de pedido que tenga datos en los meses visibles
        (solo tipos con registros; los pedidos **sin tipo** se agregan en el total
        "Pedidos" pero no generan sub-fila). Se calcula en vivo (no se guarda como
        metrica). Devuelve una lista de dicts ordenada por nombre de tipo, con
        ``{"label", "real_by_month": {month: importe}, "total_real"}``.
        """
        self.ensure_one()
        analytic = self._get_filter_analytic_account()
        if not analytic or not visible_months:
            return []
        by_month = {}
        type_ids = set()
        for month in visible_months:
            month_end = month + relativedelta(months=1) - timedelta(days=1)
            amounts = self._purchase_order_costs_by_type(analytic, month, month_end)
            by_month[month] = amounts
            type_ids.update(type_id for type_id in amounts if type_id)
        if not type_ids:
            return []
        types = (
            self.env["aunna.purchase.order.type"]
            .sudo()
            .browse(sorted(type_ids))
            .exists()
            .sorted(lambda ptype: (ptype.name or "").lower())
        )
        rows = []
        for ptype in types:
            real_by_month = {
                month: by_month[month].get(ptype.id, 0.0) for month in visible_months
            }
            if not any(real_by_month.values()):
                continue
            rows.append(
                {
                    "label": ptype.name or _("Sin nombre"),
                    "real_by_month": real_by_month,
                    "total_real": sum(real_by_month.values()),
                }
            )
        return rows

    def _amount_income_by_code(self, analytic_account, start_date, end_date, code_like):
        """Ingreso (grupo 70) imputado a la cuenta analitica del informe, en el mes,
        cuya cuenta contable tiene un codigo que empieza por `code_like`.

        - ``"705%"`` -> Venta de servicios (incluye 705000 servicios facturados y
          705001 ingreso reconocido del WIP).
        - ``"70%"``  -> Total del grupo Ingreso (servicios + productos); coincide con
          la fila "Ingreso" del informe de Perdidas y Ganancias filtrado por el
          proyecto / cuenta analitica.

        **EXCLUYE las facturas/abonos de cliente**: los Ingresos se alimentan solo de
        los **asientos WIP** (ingreso reconocido, 705001) y de otros apuntes que NO
        sean facturas. Lo facturado se ve en la fila "Facturacion".
        """
        # En Odoo 19 el codigo de cuenta es dependiente de compania: se resuelve en la
        # compania DEL INFORME (no en la activa del usuario), para que el filtro por
        # codigo (7xx) funcione tenga la compania que tenga activa el usuario.
        MoveLine = self.env["account.move.line"].with_company(self.company_id).sudo()
        domain = [
            ("date", ">=", start_date),
            ("date", "<=", end_date),
            ("company_id", "=", self.company_id.id),
            ("analytic_distribution", "!=", False),
            ("account_id.code", "=like", code_like),
        ]
        domain = expression.AND(
            [
                domain,
                self._posted_move_line_domain(MoveLine),
                self._non_customer_invoice_domain(),
                self._exclude_deferred_move_domain(),
                self._display_type_domain(MoveLine),
            ]
        )
        return self._sum_move_lines(MoveLine.search(domain), analytic_account)

    def _amount_income_by_code_before(self, analytic_account, before_date, code_like):
        """Igual que ``_amount_income_by_code`` pero acumulado hasta antes de una
        fecha (saldo inicial para el WIP acumulado)."""
        # En Odoo 19 el codigo de cuenta es dependiente de compania: se resuelve en la
        # compania DEL INFORME (no en la activa del usuario), para que el filtro por
        # codigo (7xx) funcione tenga la compania que tenga activa el usuario.
        MoveLine = self.env["account.move.line"].with_company(self.company_id).sudo()
        domain = [
            ("date", "<", before_date),
            ("company_id", "=", self.company_id.id),
            ("analytic_distribution", "!=", False),
            ("account_id.code", "=like", code_like),
        ]
        domain = expression.AND(
            [
                domain,
                self._posted_move_line_domain(MoveLine),
                self._non_customer_invoice_domain(),
                self._exclude_deferred_move_domain(),
                self._display_type_domain(MoveLine),
            ]
        )
        return self._sum_move_lines(MoveLine.search(domain), analytic_account)

    def _non_customer_invoice_domain(self):
        """Excluye facturas/abonos de cliente (los Ingresos = asientos WIP, no
        facturas)."""
        Move = self.env["account.move"]
        if "move_type" not in Move._fields:
            return []
        return [("move_id.move_type", "not in", ["out_invoice", "out_refund"])]

    def _exclude_deferred_move_domain(self):
        """Excluye los asientos generados por el motor de INGRESO DIFERIDO nativo de
        Odoo (el asiento de diferimiento y sus reconocimientos mensuales). Son
        `move_type='entry'` (no factura, por eso no los filtra `_non_customer_invoice_domain`),
        tocan cuentas 70x con distribucion analitica y meterian importes negativos que
        NO son ingreso reconocido del WIP (contaminaban "Venta de productos"/WIP). Se
        identifican por el campo nativo `deferred_original_move_ids`, poblado solo en
        esos asientos. El reconocimiento de ingreso del informe va por los asientos WIP
        (705), no por el diferido nativo."""
        Move = self.env["account.move"]
        if "deferred_original_move_ids" not in Move._fields:
            return []
        return [("move_id.deferred_original_move_ids", "=", False)]

    def _amount_invoices(self, analytic_account, start_date, end_date):
        """Facturacion: facturas/abonos de cliente en cuentas del grupo 70 (700 y
        705.0) imputados a la cuenta analitica del informe, en el mes."""
        # En Odoo 19 el codigo de cuenta es dependiente de compania: se resuelve en la
        # compania DEL INFORME (no en la activa del usuario), para que el filtro por
        # codigo (7xx) funcione tenga la compania que tenga activa el usuario.
        MoveLine = self.env["account.move.line"].with_company(self.company_id).sudo()
        domain = [
            ("date", ">=", start_date),
            ("date", "<=", end_date),
            ("company_id", "=", self.company_id.id),
            ("analytic_distribution", "!=", False),
            ("account_id.code", "=like", "70%"),
        ]
        domain = expression.AND(
            [
                domain,
                self._posted_move_line_domain(MoveLine),
                self._customer_invoice_domain(),
                self._display_type_domain(MoveLine),
            ]
        )
        return self._sum_move_lines(MoveLine.search(domain), analytic_account)

    def _amount_invoices_before(self, analytic_account, before_date):
        # En Odoo 19 el codigo de cuenta es dependiente de compania: se resuelve en la
        # compania DEL INFORME (no en la activa del usuario), para que el filtro por
        # codigo (7xx) funcione tenga la compania que tenga activa el usuario.
        MoveLine = self.env["account.move.line"].with_company(self.company_id).sudo()
        domain = [
            ("date", "<", before_date),
            ("company_id", "=", self.company_id.id),
            ("analytic_distribution", "!=", False),
            ("account_id.code", "=like", "70%"),
        ]
        domain = expression.AND(
            [
                domain,
                self._posted_move_line_domain(MoveLine),
                self._customer_invoice_domain(),
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

    def _is_income_account(self, account):
        """True si la cuenta contable es de INGRESO (grupo 7 / naturaleza ingreso).

        Se usa para **capar los costes**: un apunte imputado a una cuenta de ingreso
        (7xx) no es un coste, es "menos venta" (ya lo recoge Facturacion), asi que no
        debe sumar en Materiales/costes.
        """
        if not account:
            return False
        if "account_type" in account._fields and account.account_type in (
            "income",
            "income_other",
        ):
            return True
        # Fallback por codigo: en Odoo 19 el codigo es dependiente de compania, se
        # resuelve en la compania del informe (no en la activa del usuario).
        if "code" not in account._fields:
            return False
        code = account.with_company(self.company_id).code
        return bool(code) and str(code).startswith("7")

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
    _description = "Linea informe operativo financiero"
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
    _description = "Detalle mensual informe operativo financiero"
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
