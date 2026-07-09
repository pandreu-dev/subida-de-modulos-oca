"""Migracion 19.0.7.0.0

Cambios funcionales:

- Se elimina el concepto ER/OE (ordenes de venta) del informe WIP.
- El nuevo orden de conceptos es: Ingreso reconocido, Facturacion, WIP real
  acumulado.

Esta migracion adapta los informes ya existentes:

1. Borra las lineas (concepto y mensual) del concepto obsoleto ``er``.
2. Reajusta la secuencia de los conceptos restantes al nuevo orden.
3. Regenera la vista horizontal (HTML) para que no siga mostrando ER/OE.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Nuevo orden de conceptos (debe coincidir con METRICS en el modelo).
NEW_SEQUENCES = {
    "recognized_income": 10,
    "invoice": 20,
    "real_wip": 30,
}


def migrate(cr, version):
    if not version:
        # Instalacion nueva: no hay datos que adaptar.
        return

    # 1) Eliminar el concepto obsoleto ER/OE.
    cr.execute("DELETE FROM aunna_wip_annual_report_line WHERE metric = 'er'")
    cr.execute("DELETE FROM aunna_wip_annual_report_period_line WHERE metric = 'er'")

    # 2) Reajustar la secuencia de los conceptos restantes al nuevo orden.
    for metric, sequence in NEW_SEQUENCES.items():
        cr.execute(
            "UPDATE aunna_wip_annual_report_line SET sequence = %s WHERE metric = %s",
            (sequence, metric),
        )
        cr.execute(
            "UPDATE aunna_wip_annual_report_period_line SET sequence = %s WHERE metric = %s",
            (sequence, metric),
        )

    # 3) Regenerar la vista horizontal de los informes existentes.
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        reports = env["aunna.wip.annual.report"].search([])
        if reports:
            reports._update_horizontal_summary_html()
    except Exception:
        # La vista horizontal se regenera igualmente al abrir o recalcular el
        # informe; no bloqueamos la actualizacion del modulo por esto.
        _logger.exception(
            "No se pudo regenerar la vista horizontal WIP durante la migracion; "
            "se regenerara al abrir o recalcular cada informe."
        )
