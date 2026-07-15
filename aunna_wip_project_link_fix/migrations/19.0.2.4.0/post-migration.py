import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Repara los asientos WIP ya existentes para poner unit_amount=0 en sus apuntes
    analiticos de ingreso reconocido (que hasta ahora heredaban 1 hora y se contaban
    como partes de horas en el tablero/Rentabilidad del proyecto).

    Reutiliza la reparacion idempotente del modulo (_aunna_wip_repair_existing ->
    _aunna_wip_link_move_analytic_lines), que ahora fija las horas a 0 y restaura el
    importe contable. Solo toca los apuntes WIP; no altera debe/haber/saldo."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    calcs = env["aunna.wip.calculation"].search([])
    if not calcs:
        return
    moves = calcs.mapped("move_id") | calcs.mapped("reversal_move_id")
    if not moves:
        return
    try:
        calcs._aunna_wip_repair_existing(moves)
        _logger.info(
            "aunna_wip_project_link_fix: reparados %s asiento(s) WIP (horas a 0).",
            len(moves),
        )
    except Exception:
        _logger.exception(
            "No se pudieron reparar las horas de los apuntes WIP existentes."
        )
