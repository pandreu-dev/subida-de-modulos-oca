import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Opcion B: limpia el `project_id` estandar de los apuntes analiticos de ingreso
    reconocido WIP ya existentes, para que Odoo deje de tratarlos como partes de horas
    (dejaban de contarse como horas pero seguian apareciendo como registros en las
    listas de partes / tablero del proyecto).

    Reutiliza la reparacion idempotente del modulo (_aunna_wip_repair_existing ->
    _aunna_wip_link_move_analytic_lines), que desde esta version pone project_id=False.
    No toca partes de horas reales ni debe/haber/saldo; el vinculo al proyecto se
    conserva por la cuenta analitica y por aunna_wip_project_id."""
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
            "aunna_wip_project_link_fix: %s asiento(s) WIP normalizados "
            "(project_id retirado de sus apuntes analiticos).",
            len(moves),
        )
    except Exception:
        _logger.exception(
            "No se pudo retirar el project_id de los apuntes WIP existentes."
        )
