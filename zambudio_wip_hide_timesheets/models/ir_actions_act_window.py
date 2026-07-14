import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Termino que se anade al dominio de las acciones de Partes de horas. Un parte de
# horas REAL nunca se genera desde un asiento contable, por lo que su `move_line_id`
# siempre esta vacio. Los apuntes analiticos generados desde asientos (p.ej. el
# ingreso reconocido WIP de la cuenta 705, que aunna_wip_project_link_fix enlaza al
# proyecto para poder agruparlo en Apuntes analiticos) SI llevan `move_line_id`, y son
# justo los que ensucian la vista de Partes de horas.
_EXCLUDE_TERM = "('move_line_id', '=', False)"


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    @api.model
    def _zambudio_hide_move_lines_from_timesheets(self):
        """Anade ``('move_line_id','=',False)`` al dominio de las acciones de Partes de
        horas, para que los apuntes analiticos generados desde asientos (ingreso
        reconocido WIP, etc.) dejen de mostrarse como partes de horas.

        - Solo toca acciones sobre ``account.analytic.line`` cuyo dominio ya filtra por
          ``project_id`` (asi es como Odoo define un parte de horas). La vista de
          **Apuntes analiticos** (dominio sin ``project_id``) NO se toca, de modo que
          las lineas WIP siguen visibles ahi, agrupadas por su proyecto.
        - Es idempotente: si el dominio ya contiene ``move_line_id`` no se vuelve a
          tocar. Se ejecuta en cada instalacion/actualizacion del modulo (via
          ``<function>``), por si una actualizacion de hr_timesheet repusiera el
          dominio original.
        - No puede ocultar ningun parte real: estos nunca tienen ``move_line_id``.
        """
        actions = self.sudo().search([("res_model", "=", "account.analytic.line")])
        patched = 0
        for action in actions:
            domain = (action.domain or "").strip()
            # Solo acciones tipo "parte de horas" (filtran por project_id).
            if "project_id" not in domain:
                continue
            if "move_line_id" in domain:
                continue  # ya parcheada
            if not domain.endswith("]"):
                continue
            inner = domain[:-1].rstrip()
            if inner.endswith("["):
                new_domain = inner + _EXCLUDE_TERM + "]"
            else:
                if not inner.endswith(","):
                    inner += ","
                new_domain = inner + " " + _EXCLUDE_TERM + "]"
            action.sudo().write({"domain": new_domain})
            patched += 1
        if patched:
            _logger.info(
                "zambudio_wip_hide_timesheets: %s accion(es) de partes de horas "
                "filtradas para ocultar apuntes de asiento (WIP).",
                patched,
            )
        return True
