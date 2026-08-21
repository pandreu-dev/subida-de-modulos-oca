# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MONTHS = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# --- Modelo/campos de la app de produccion (Veronica), definidos como constantes
# para poder ajustarlos EN UNA LINEA si el nombre real difiere. Confirmado por su
# equipo; pendiente de contrastar contra el codigo de zambudio_produccion_real
# (find/grep en PRE) antes de usarlo en produccion.
AVANCE_MODEL = "produccion.avance.mes"
F_PERIOD = "fecha_mes"            # Date, dia 1 del mes
F_AMOUNT = "importe_confirmado"   # ingreso reconocido confirmado (EUR, positivo)
F_STATE = "estado"
STATE_CONFIRMED = "confirmado"
F_PROJECT = "project_id"          # many2one project.project


class ZambudioWipMonthCloseWizard(models.TransientModel):
    _name = "zambudio.wip.month.close.wizard"
    _description = (
        "Cierre mensual WIP: genera un asiento de ingreso reconocido por proyecto"
    )

    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        required=True,
        default=lambda self: self.env.company,
    )
    year = fields.Integer(
        string="Ano",
        required=True,
        default=lambda self: fields.Date.context_today(self).year,
    )
    month = fields.Selection(
        selection=[(str(i + 1), MONTHS[i]) for i in range(12)],
        string="Mes",
        required=True,
        default=lambda self: str(fields.Date.context_today(self).month),
    )

    # ------------------------------------------------------------------ helpers
    def _month_label(self):
        return "%s %s" % (MONTHS[int(self.month) - 1], self.year)

    def _period_dates(self):
        """(primer_dia, ultimo_dia_del_mes, fecha_reversion=dia 1 del mes siguiente)."""
        first_day = date(self.year, int(self.month), 1)
        last_day = first_day + relativedelta(day=31)
        reversal_date = last_day + timedelta(days=1)
        return first_day, last_day, reversal_date

    def _wip_settings(self):
        """Ajustes contables (diario / cuentas / auto_post) reutilizados de aunna_wip_accounting."""
        wip = self.env["aunna.wip.calculation"]
        settings = wip._aunna_wip_accounting_settings(self.company_id)
        missing = [
            label
            for key, label in (
                ("journal", _("Diario WIP")),
                ("income_account", _("Cuenta ingreso avance")),
                ("deferred_account", _("Cuenta ingresos anticipados")),
            )
            if not settings.get(key)
        ]
        if missing:
            raise UserError(
                _(
                    "Faltan datos de configuracion de avance/WIP en la compania %s: %s.\n"
                    "Configuralos en Contabilidad > Ajustes > Avance."
                )
                % (self.company_id.display_name, ", ".join(missing))
            )
        return settings

    def _confirmed_avances(self, first_day):
        Avance = self.env[AVANCE_MODEL].sudo()
        # Filtramos por compania (campo related stored del avance = project_id.company_id).
        # Evita procesar proyectos de OTRA compania y, sobre todo, que un proyecto sin
        # compania (company_id = False) se cierre en cada compania duplicando ingreso.
        return Avance.search(
            [
                (F_PERIOD, "=", first_day),
                (F_STATE, "=", STATE_CONFIRMED),
                ("company_id", "=", self.company_id.id),
            ]
        )

    def _existing_close_move(self, project, first_day):
        """Evita duplicar: ¿ya hay asiento de cierre para ese proyecto y mes?"""
        return (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("x_zambudio_wip_close", "=", True),
                    ("x_zambudio_wip_close_project_id", "=", project.id),
                    ("x_zambudio_wip_close_period", "=", first_day),
                    ("company_id", "=", self.company_id.id),
                    ("state", "!=", "cancel"),
                ],
                limit=1,
            )
        )

    def _project_analytic_account(self, project):
        if "account_id" in project._fields and project.account_id:
            return project.account_id
        return self.env["account.analytic.account"]

    def _force_income_analytic(self, move, income_account, analytic_distribution):
        """Reaplica la distribucion analitica en las lineas de la cuenta de ingreso.

        En este despliegue Odoo 19 un proceso posterior vacia/recalcula la
        analytic_distribution de la 705 al crear/postear el asiento (ver
        aunna_wip_project_link_fix/docs/INCIDENCIA_DISTRIBUCION_ANALITICA_WIP.md).
        Igual que hace el motor de aunna_wip_accounting
        (_aunna_wip_force_move_analytic_distribution), la re-forzamos con
        check_move_validity=False para que valga tambien sobre asientos ya posteados.
        """
        if not analytic_distribution:
            return
        income_lines = move.line_ids.filtered(
            lambda line: line.account_id == income_account
        )
        if income_lines:
            income_lines.sudo().with_context(check_move_validity=False).write(
                {"analytic_distribution": analytic_distribution}
            )

    # ------------------------------------------------------------------- accion
    def action_close_month(self):
        self.ensure_one()
        company = self.company_id
        first_day, last_day, reversal_date = self._period_dates()
        settings = self._wip_settings()
        wip = self.env["aunna.wip.calculation"]
        today = fields.Date.context_today(self)

        avances = self._confirmed_avances(first_day)

        created_moves = self.env["account.move"]
        skipped = []

        for avance in avances:
            project = avance[F_PROJECT]
            amount = avance[F_AMOUNT] or 0.0

            if not project:
                continue
            if project.company_id and project.company_id != company:
                continue
            # Solo el ingreso reconocido (positivo). En ese modelo los costes van en negativo.
            if amount <= 0:
                continue
            if self._existing_close_move(project, first_day):
                skipped.append((project, _("ya tenia asiento de cierre para el mes")))
                continue

            analytic = self._project_analytic_account(project)
            if not analytic:
                skipped.append((project, _("proyecto sin cuenta analitica")))
                continue

            analytic_distribution = {str(analytic.id): 100.0}
            line_name = _("Avance reconocido %s - %s") % (
                self._month_label(),
                project.display_name,
            )
            # Mismo asiento que el WIP de hoy: Debe ingresos anticipados / Haber 705
            # (con analitica del proyecto). Reutilizamos el helper de aunna_wip_accounting.
            lines = [
                (
                    0,
                    0,
                    wip._aunna_wip_move_line_vals(
                        settings["deferred_account"], amount, 0.0, line_name
                    ),
                ),
                (
                    0,
                    0,
                    wip._aunna_wip_move_line_vals(
                        settings["income_account"],
                        0.0,
                        amount,
                        line_name,
                        analytic_distribution,
                    ),
                ),
            ]
            move = (
                self.env["account.move"]
                .with_company(company)
                .create(
                    {
                        "move_type": "entry",
                        "journal_id": settings["journal"].id,
                        "date": last_day,
                        "ref": _("Cierre WIP %s-%02d - %s")
                        % (self.year, int(self.month), project.display_name),
                        "company_id": company.id,
                        "x_zambudio_wip_close": True,
                        "x_zambudio_wip_close_period": first_day,
                        "x_zambudio_wip_close_project_id": project.id,
                        "line_ids": lines,
                    }
                )
            )
            # Re-forzar la analitica en la linea de ingreso (705) tras crear.
            self._force_income_analytic(
                move, settings["income_account"], analytic_distribution
            )
            if settings["auto_post"]:
                move.action_post()
                # ...y tambien tras postear (el recalculo puede ocurrir al publicar).
                self._force_income_analytic(
                    move, settings["income_account"], analytic_distribution
                )

            # Reversion al dia 1 del mes siguiente (misma logica que el WIP actual).
            reversal = move.with_company(company)._reverse_moves(
                default_values_list=[
                    {
                        "date": reversal_date,
                        "ref": _("Reversion de: %s") % (move.name or move.ref),
                        "x_zambudio_wip_close": True,
                        "x_zambudio_wip_close_period": first_day,
                        "x_zambudio_wip_close_project_id": project.id,
                    }
                ],
                cancel=False,
            )
            self._force_income_analytic(
                reversal, settings["income_account"], analytic_distribution
            )
            if settings["auto_post"]:
                if reversal_date <= today:
                    reversal.action_post()
                    self._force_income_analytic(
                        reversal, settings["income_account"], analytic_distribution
                    )
                else:
                    reversal.write({"auto_post": "at_date"})

            created_moves |= move

        return self._result(created_moves, skipped, avances)

    def _result(self, created_moves, skipped, avances):
        if skipped:
            _logger.info(
                "Cierre WIP %s (%s): %s proyectos omitidos: %s",
                self._month_label(),
                self.company_id.display_name,
                len(skipped),
                "; ".join(
                    "%s (%s)" % (project.display_name, reason)
                    for project, reason in skipped
                ),
            )

        if not created_moves:
            raise UserError(
                _(
                    "No se ha generado ningun asiento para %s.\n\n"
                    "- Avances confirmados encontrados: %s\n"
                    "- Omitidos: %s\n\n"
                    "Si esperabas asientos, revisa que los proyectos tengan el avance "
                    "CONFIRMADO ese mes (ejecuta antes 'Recalcular datos reales' si hace "
                    "falta) y que tengan cuenta analitica."
                )
                % (self._month_label(), len(avances), len(skipped))
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Asientos de cierre WIP - %s") % self._month_label(),
            "res_model": "account.move",
            "domain": [("id", "in", created_moves.ids)],
            "view_mode": "list,form",
            "context": {"create": False},
        }
