from odoo import models


class ProjectProject(models.Model):
    _inherit = "project.project"

    def action_project_timesheets(self):
        """El boton "Partes de horas" del tablero del proyecto abre una lista de partes
        cuyo dominio filtra por el proyecto (montado sobre una act_window nativa). Se
        reinyecta el marcador seguro para ocultar los apuntes generados desde asientos
        (ingreso reconocido WIP): tienen project_id pero NO son partes reales -> nunca
        tienen `move_line_id`. Cubre list/grid/pivot de esa accion. No oculta ningun
        parte real ni toca los computos (totales, tiempo extra, Rentabilidad)."""
        action = super().action_project_timesheets()
        if not isinstance(action, dict):
            return action
        if action.get("res_model") != "account.analytic.line":
            return action
        if "move_line_id" not in self.env["account.analytic.line"]._fields:
            return action
        domain = action.get("domain")
        if isinstance(domain, str) and domain.strip():
            # La act_window trae el dominio como texto (con active_id): su unico criterio
            # es el proyecto, asi que se reconstruye concreto y se le anade el marcador.
            domain = [("project_id", "in", self.ids)]
        elif isinstance(domain, (list, tuple)):
            domain = list(domain)
        else:
            domain = []
        if not any(
            isinstance(leaf, (list, tuple)) and leaf and leaf[0] == "move_line_id"
            for leaf in domain
        ):
            domain = domain + [("move_line_id", "=", False)]
        action["domain"] = domain
        return action
