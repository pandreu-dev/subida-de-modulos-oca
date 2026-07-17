import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Se anade al dominio de las acciones de "A validar" (las que filtran partes por
# `validated`) para que cada usuario solo vea en esa vista los partes de SUS proyectos.
_PROJECT_MANAGER_LEAF = "('project_id.user_id', '=', uid)"


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    @api.model
    def _zambudio_scope_validation_to_project_manager(self):
        """Filtra las acciones de "A validar" de Partes de horas por responsable del
        proyecto: cada usuario ve en esa vista SOLO los partes sin validar de los
        proyectos de los que es responsable.

        - Solo toca acciones sobre ``account.analytic.line`` cuyo dominio filtra por
          ``validated`` (asi es como se distingue la vista "A validar" de las demas
          listas de partes). Las vistas normales de Partes de horas NO se tocan.
        - Es idempotente (no re-anade si ya esta) y se ejecuta en cada instalacion/
          actualizacion via ``<function>``.
        - No puede saltarse la restriccion de quien valida: aunque un usuario viese un
          parte ajeno, el override de ``action_validate_timesheet`` lo impide.
        """
        actions = self.sudo().search([("res_model", "=", "account.analytic.line")])
        patched = 0
        for action in actions:
            domain = (action.domain or "").strip()
            if "validated" not in domain:
                continue  # no es la vista "A validar"
            if "project_id.user_id" in domain:
                continue  # ya filtrada
            if not domain.endswith("]"):
                continue
            inner = domain[:-1].rstrip()
            if inner.endswith("["):
                new_domain = inner + _PROJECT_MANAGER_LEAF + "]"
            else:
                if not inner.endswith(","):
                    inner += ","
                new_domain = inner + " " + _PROJECT_MANAGER_LEAF + "]"
            action.sudo().write({"domain": new_domain})
            patched += 1
        if patched:
            _logger.info(
                "zambudio_timesheet_approval_by_project: %s accion(es) 'A validar' "
                "filtradas por responsable de proyecto.",
                patched,
            )
        return True
