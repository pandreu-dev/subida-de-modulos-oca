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
# Prevision/plan: importe del avance ANTES de confirmar (lo que se ve en la
# pestaña 'Seguimiento economico'). El nombre real puede variar entre despliegues;
# se resuelve por el PRIMERO que exista en el modelo. Si ninguno casa, el modo
# prueba avisa para ajustarlo aqui en una linea. SOLO se usa en modo prueba.
F_AMOUNT_PLAN_CANDIDATES = (
    "importe_previsto",
    "importe_prevision",
    "importe_plan",
    "importe_planificado",
    "importe_avance",
    "importe",
)
F_STATE = "estado"
STATE_CONFIRMED = "confirmado"
F_PROJECT = "project_id"          # many2one project.project


class ZambudioMonthCloseWizard(models.TransientModel):
    _name = "zambudio.month.close.wizard"
    _description = (
        "Cierre mensual: genera un asiento de ingreso reconocido por proyecto"
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
    modo_prueba = fields.Boolean(
        string="Modo prueba (usar previsión, no el confirmado)",
        help=(
            "SOLO PARA PRUEBAS. Genera el asiento desde la cifra de avance que se ve en la "
            "pestaña 'Seguimiento económico', aunque el mes NO esté confirmado. Los asientos "
            "salen MARCADOS como PRUEBA y en BORRADOR (sin contabilizar). En uso real, dejar "
            "SIN marcar (solo cuenta con avances confirmados)."
        ),
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

    def _close_settings(self):
        """Ajustes contables (diario / cuentas / auto_post) reutilizados de aunna_wip_accounting."""
        calc = self.env["aunna.wip.calculation"]
        settings = calc._aunna_wip_accounting_settings(self.company_id)
        missing = [
            label
            for key, label in (
                ("journal", _("Diario")),
                ("income_account", _("Cuenta ingreso avance")),
                ("deferred_account", _("Cuenta ingresos anticipados")),
            )
            if not settings.get(key)
        ]
        if missing:
            raise UserError(
                _(
                    "Faltan datos de configuracion de avance en la compania %s: %s.\n"
                    "Configuralos en Contabilidad > Ajustes > Avance."
                )
                % (self.company_id.display_name, ", ".join(missing))
            )
        return settings

    def _avances_acumulados(self, first_day, test, plan_field):
        """Avance ACUMULADO por proyecto: suma de los avances con fecha_mes <= mes de
        cierre (desde el INICIO DEL PROYECTO). Devuelve {project: importe}.

        Cada mes se reconoce el acumulado y se revierte al dia siguiente; con la
        reversion del mes anterior, el neto contable del mes es el avance incremental
        (p. ej. mes 1 = 1000 y mes 2 = 1500 -> en el mes 2: -1000 de la reversion del
        mes 1 + 1500 del reconocimiento = 500).
        """
        Avance = self.env[AVANCE_MODEL].sudo()
        # Filtramos por compania (campo related stored = project_id.company_id) para no
        # procesar proyectos de otra compania ni duplicar el ingreso en multi-compania.
        domain = [
            (F_PERIOD, "<=", first_day),
            ("company_id", "=", self.company_id.id),
        ]
        # Uso real: SOLO avances confirmados. Modo prueba: cualquier estado.
        if not test:
            domain.append((F_STATE, "=", STATE_CONFIRMED))
        acumulados = {}
        for r in Avance.search(domain):
            project = r[F_PROJECT]
            if not project:
                continue
            if test:
                importe = (r[plan_field] if plan_field else 0.0) or r[F_AMOUNT] or 0.0
            else:
                importe = r[F_AMOUNT] or 0.0
            acumulados[project] = acumulados.get(project, 0.0) + (importe or 0.0)
        return acumulados

    def _plan_amount_field(self):
        """Campo de importe de PREVISION en el propio modelo de avance, si existe.

        Devuelve el primero de F_AMOUNT_PLAN_CANDIDATES presente en el modelo, o
        None si ninguno casa (entonces el modo prueba cae a importe_confirmado,
        sin romper).

        NOTA: en este despliegue la PREVISION real vive en OTRO modelo
        ('produccion.plan.linea.importe_previsto'); su integracion (join por
        proyecto + mes) queda pendiente de confirmar el esquema exacto en PRE.
        """
        Avance = self.env[AVANCE_MODEL]
        for fname in F_AMOUNT_PLAN_CANDIDATES:
            if fname in Avance._fields:
                return fname
        return None

    def _existing_close_move(self, project, first_day, test):
        """Evita duplicar: ¿ya hay asiento de cierre (real o de prueba) para ese proyecto y mes?"""
        return (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("x_zambudio_month_close", "=", True),
                    ("x_zambudio_month_close_test", "=", test),
                    ("x_zambudio_month_close_project_id", "=", project.id),
                    ("x_zambudio_month_close_period", "=", first_day),
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
        settings = self._close_settings()
        calc = self.env["aunna.wip.calculation"]
        today = fields.Date.context_today(self)

        test = self.modo_prueba
        # En modo prueba NUNCA se contabiliza: los asientos quedan en BORRADOR.
        post = settings["auto_post"] and not test
        # En modo prueba el importe sale de la PREVISION (el confirmado esta a 0
        # mientras el mes no se confirma); en uso real, del confirmado.
        plan_field = self._plan_amount_field() if test else None
        # ACUMULADO desde el inicio del proyecto (peticion de Laura/Manuel): el asiento
        # y su reversion se generan por el avance acumulado hasta el mes de cierre.
        acumulados = self._avances_acumulados(first_day, test, plan_field)

        created_moves = self.env["account.move"]
        skipped = []

        for project, amount in acumulados.items():
            if not project:
                continue
            if project.company_id and project.company_id != company:
                continue
            # Solo el ingreso reconocido (positivo). En ese modelo los costes van en negativo.
            if amount <= 0:
                continue
            if self._existing_close_move(project, first_day, test):
                skipped.append((project, _("ya tenia asiento de cierre para el mes")))
                continue

            analytic = self._project_analytic_account(project)
            if not analytic:
                skipped.append((project, _("proyecto sin cuenta analitica")))
                continue

            analytic_distribution = {str(analytic.id): 100.0}
            line_name = _("Avance acumulado reconocido a %s - %s") % (
                self._month_label(),
                project.display_name,
            )
            # Mismo asiento que el de hoy: Debe ingresos anticipados / Haber 705
            # (con analitica del proyecto). Reutilizamos el helper de aunna_wip_accounting.
            lines = [
                (
                    0,
                    0,
                    calc._aunna_wip_move_line_vals(
                        settings["deferred_account"], amount, 0.0, line_name
                    ),
                ),
                (
                    0,
                    0,
                    calc._aunna_wip_move_line_vals(
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
                        "ref": (_("PRUEBA - ") if test else "")
                        + _("Cierre mensual %s-%02d - %s")
                        % (self.year, int(self.month), project.display_name),
                        "company_id": company.id,
                        "x_zambudio_month_close": True,
                        "x_zambudio_month_close_test": test,
                        "x_zambudio_month_close_period": first_day,
                        "x_zambudio_month_close_project_id": project.id,
                        "line_ids": lines,
                    }
                )
            )
            # Re-forzar la analitica en la linea de ingreso (705) tras crear.
            self._force_income_analytic(
                move, settings["income_account"], analytic_distribution
            )
            if post:
                move.action_post()
                # ...y tambien tras postear (el recalculo puede ocurrir al publicar).
                self._force_income_analytic(
                    move, settings["income_account"], analytic_distribution
                )

            # Reversion al dia 1 del mes siguiente (misma logica que la del asiento actual).
            reversal = move.with_company(company)._reverse_moves(
                default_values_list=[
                    {
                        "date": reversal_date,
                        "ref": _("Reversion de: %s") % (move.ref or move.name),
                        "x_zambudio_month_close": True,
                        "x_zambudio_month_close_test": test,
                        "x_zambudio_month_close_period": first_day,
                        "x_zambudio_month_close_project_id": project.id,
                    }
                ],
                cancel=False,
            )
            self._force_income_analytic(
                reversal, settings["income_account"], analytic_distribution
            )
            if post:
                if reversal_date <= today:
                    reversal.action_post()
                    self._force_income_analytic(
                        reversal, settings["income_account"], analytic_distribution
                    )
                else:
                    reversal.write({"auto_post": "at_date"})

            created_moves |= move

        return self._result(created_moves, skipped, len(acumulados))

    def _result(self, created_moves, skipped, n_encontrados):
        if skipped:
            _logger.info(
                "Cierre mensual %s (%s): %s proyectos omitidos: %s",
                self._month_label(),
                self.company_id.display_name,
                len(skipped),
                "; ".join(
                    "%s (%s)" % (project.display_name, reason)
                    for project, reason in skipped
                ),
            )

        if not created_moves:
            if self.modo_prueba:
                raise UserError(
                    _(
                        "No se ha generado ningun asiento (MODO PRUEBA) para %s.\n\n"
                        "- Avances encontrados: %s\n"
                        "- Omitidos: %s\n\n"
                        "Revisa que los proyectos tengan una cifra de avance/prevision ese "
                        "mes (pestaña 'Seguimiento economico') y cuenta analitica."
                    )
                    % (self._month_label(), n_encontrados, len(skipped))
                )
            raise UserError(
                _(
                    "No se ha generado ningun asiento para %s.\n\n"
                    "- Avances confirmados encontrados: %s\n"
                    "- Omitidos: %s\n\n"
                    "Si esperabas asientos, revisa que los proyectos tengan el avance "
                    "CONFIRMADO ese mes (ejecuta antes 'Recalcular datos reales' si hace "
                    "falta) y que tengan cuenta analitica.\n\n"
                    "Para probar sin esperar a fin de mes, marca 'Modo prueba'."
                )
                % (self._month_label(), n_encontrados, len(skipped))
            )

        nombre = (
            _("Asientos de cierre mensual (PRUEBA - borrador)")
            if self.modo_prueba
            else _("Asientos de cierre mensual")
        )
        # Vista de lista propia (con columna Proyecto). Si por lo que sea no
        # existiese, se cae con elegancia a la lista por defecto de account.move.
        list_view = self.env.ref(
            "zambudio_cierre_mensual.view_month_close_move_list",
            raise_if_not_found=False,
        )
        views = (
            [(list_view.id, "list"), (False, "form")]
            if list_view
            else [(False, "list"), (False, "form")]
        )
        return {
            "type": "ir.actions.act_window",
            "name": "%s - %s" % (nombre, self._month_label()),
            "res_model": "account.move",
            "domain": [("id", "in", created_moves.ids)],
            "views": views,
            "view_mode": "list,form",
            "context": {"create": False},
        }
