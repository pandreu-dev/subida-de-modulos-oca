import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Las devoluciones ya hechas sumaban coste: se regeneran sus apuntes para que
    resten (Laura, 11/11/2026). Solo se tocan devoluciones; el resto de apuntes no
    cambia. El apunte regenerado lleva la fecha del movimiento."""
    # Empresa en España: la fecha del apunte se calcula con la hora de Madrid,
    # igual que cuando lo crea un usuario al validar.
    env = api.Environment(cr, SUPERUSER_ID, {"tz": "Europe/Madrid"})
    returns = env["stock.move"].search([
        ("state", "=", "done"),
        ("origin_returned_move_id", "!=", False),
        ("picking_id.picking_type_code", "in",
         env["stock.picking"]._get_project_delivery_picking_type_codes()),
    ])
    candidates = returns.filtered(lambda move: move._is_manual_project_delivery_move())
    candidates._sync_project_delivery_analytic_lines()
    _logger.info(
        "project_delivery_analytic_valuation: %s devoluciones con proyecto regeneradas para que resten",
        len(candidates),
    )
