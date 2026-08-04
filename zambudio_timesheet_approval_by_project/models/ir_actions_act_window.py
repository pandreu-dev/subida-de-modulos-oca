import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Leaf que versiones anteriores del modulo anadian al dominio de las acciones
# "A validar" para limitar la vista a los proyectos del usuario. Ahora se REVIERTE
# (la validacion funciona como Odoo nativo), asi que se elimina si aun esta presente.
_PROJECT_MANAGER_LEAF = "('project_id.user_id', '=', uid)"


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    @api.model
    def _zambudio_unscope_validation_from_project_manager(self):
        """Revierte el filtrado por responsable de proyecto en las acciones "A validar"
        de Partes de horas que anadian versiones previas del modulo, para dejar la
        vista COMO ODOO NATIVO. Idempotente (si el leaf no esta, no hace nada)."""
        actions = self.sudo().search([("res_model", "=", "account.analytic.line")])
        restored = 0
        for action in actions:
            domain = action.domain or ""
            if _PROJECT_MANAGER_LEAF not in domain:
                continue
            new_domain = (
                domain.replace(", " + _PROJECT_MANAGER_LEAF, "")
                .replace(_PROJECT_MANAGER_LEAF + ", ", "")
                .replace(_PROJECT_MANAGER_LEAF, "")
            )
            action.sudo().write({"domain": new_domain})
            restored += 1
        if restored:
            _logger.info(
                "zambudio_timesheet_approval_by_project: revertido el filtrado por "
                "responsable de proyecto en %s accion(es) 'A validar'.",
                restored,
            )
        return True
