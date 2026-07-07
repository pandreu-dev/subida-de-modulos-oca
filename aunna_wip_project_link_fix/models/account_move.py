import logging

from odoo import fields, models


_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    aunna_wip_calculation_line_id = fields.Many2one(
        "aunna.wip.calculation.line",
        string="Linea calculo WIP",
        copy=False,
        index=True,
        ondelete="set null",
    )
    aunna_wip_project_id = fields.Many2one(
        "project.project",
        string="Proyecto WIP",
        copy=False,
        index=True,
        ondelete="set null",
    )

    def _aunna_wip_distribution_differs(self, desired):
        """Compara la distribucion analitica actual con la esperada, normalizando
        claves a texto y descartando porcentajes <= 0."""
        self.ensure_one()

        def _normalize(distribution):
            normalized = {}
            for key, value in (distribution or {}).items():
                try:
                    percentage = round(float(value or 0.0), 6)
                except (TypeError, ValueError):
                    percentage = 0.0
                if percentage > 0.0:
                    normalized[str(key)] = percentage
            return normalized

        return _normalize(self.analytic_distribution) != _normalize(desired)


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    aunna_wip_calculation_line_id = fields.Many2one(
        "aunna.wip.calculation.line",
        string="Linea calculo WIP",
        copy=False,
        index=True,
        ondelete="set null",
    )
    aunna_wip_project_id = fields.Many2one(
        "project.project",
        string="Proyecto WIP",
        copy=False,
        index=True,
        ondelete="set null",
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted._aunna_wip_link_analytic_lines_to_projects()
        return posted

    def _aunna_wip_analytic_account_for(self, move_line):
        """Cuenta analitica de una linea de ingreso WIP.

        Se deriva igual que en el modulo base (``_aunna_wip_line_analytic_account``)
        para que en el flujo normal coincida exactamente con la distribucion que ya
        dejo el base y la autorreparacion no la reescriba en vano."""
        calc_line = move_line.aunna_wip_calculation_line_id
        calculation = calc_line.calculation_id
        if calculation and hasattr(calculation, "_aunna_wip_line_analytic_account"):
            account = calculation._aunna_wip_line_analytic_account(calc_line)
            if account:
                return account
        if calc_line.analytic_account_id:
            return calc_line.analytic_account_id
        project = move_line.aunna_wip_project_id
        if project and "account_id" in project._fields and project.account_id:
            return project.account_id
        return self.env["account.analytic.account"]

    def _aunna_wip_link_analytic_lines_to_projects(self):
        """Enlaza con su proyecto los apuntes analiticos que Odoo genera de forma
        NATIVA para las lineas de ingreso WIP.

        En Odoo 19:

        - ``analytic_distribution`` la deja el modulo base al 100% con la cuenta
          analitica del proyecto. Aqui solo se re-asegura de forma idempotente por
          si otro proceso la hubiera vaciado (autorreparacion). Si ya es correcta,
          NO se reescribe (evita disparar en vano el ``inverse`` nativo, que borra y
          recrea los apuntes analiticos).
        - El nucleo crea el apunte analitico correcto (cuenta e importe) al postear.
          Este metodo solo lo enriquece con el proyecto para poder agruparlo por
          proyecto: escribe ``project_id`` (campo de ``hr_timesheet``) SIN tocar
          ``analytic_distribution`` ni borrar/recrear apuntes. Escribir el proyecto
          es el ultimo paso, porque volver a escribir la distribucion despues lo
          borraria.
        """
        AnalyticLine = self.env["account.analytic.line"]
        has_project_field = "project_id" in AnalyticLine._fields
        for move in self:
            wip_move_lines = move.line_ids.filtered("aunna_wip_calculation_line_id")
            if not wip_move_lines:
                continue
            try:
                move._aunna_wip_link_move_analytic_lines(
                    wip_move_lines, has_project_field
                )
            except Exception:
                _logger.exception(
                    "No se pudieron enlazar los apuntes analiticos WIP de %s con su proyecto",
                    move.display_name,
                )
        return True

    def _aunna_wip_link_move_analytic_lines(self, wip_move_lines, has_project_field):
        self.ensure_one()
        for move_line in wip_move_lines:
            # 1) Autorreparacion: garantizar la distribucion analitica correcta.
            account = self._aunna_wip_analytic_account_for(move_line)
            if account:
                desired = {str(account.id): 100.0}
                if move_line._aunna_wip_distribution_differs(desired):
                    move_line.sudo().with_context(
                        check_move_validity=False,
                    ).write({"analytic_distribution": desired})
            # 2) Enriquecer los apuntes analiticos nativos con el proyecto.
            project = move_line.aunna_wip_project_id
            calc_line = move_line.aunna_wip_calculation_line_id
            for analytic_line in move_line.analytic_line_ids:
                vals = {}
                if analytic_line.aunna_wip_calculation_line_id != calc_line:
                    vals["aunna_wip_calculation_line_id"] = calc_line.id
                if analytic_line.aunna_wip_project_id != project:
                    vals["aunna_wip_project_id"] = project.id or False
                if project and has_project_field and analytic_line.project_id != project:
                    vals["project_id"] = project.id
                if vals:
                    analytic_line.sudo().with_context(
                        aunna_skip_project_cost_moves=True,
                        skip_analytic_sync=True,
                    ).write(vals)
        return True
