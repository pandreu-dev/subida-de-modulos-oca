"""Migracion 19.0.8.0.0

Reforma del bloque de Ingresos y WIP segun la definicion funcional:

- Se separa el ingreso en "Venta de servicios" (cuentas 705) y "Venta de productos"
  (resto del grupo 70).
- Se retira el concepto "Ingreso reconocido" (queda incluido en Venta de servicios,
  ya que 705001 es una cuenta 705).
- El WIP pasa a calcularse como acumulado de (Total ingresos - Facturacion).

Esta migracion adapta los informes ya existentes:

1. Elimina las lineas del concepto obsoleto ``recognized_income``.
2. Reajusta la secuencia de los conceptos restantes.
3. Crea las lineas del nuevo concepto ``products_income`` y regenera la vista
   horizontal. Los importes reales se rellenan al pulsar "Recalcular reales".
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

NEW_SEQUENCES = {
    "services_income": 10,
    "products_income": 20,
    "invoice": 80,
    "real_wip": 90,
}


def migrate(cr, version):
    if not version:
        return

    # 1) Eliminar el concepto obsoleto "Ingreso reconocido".
    cr.execute(
        "DELETE FROM aunna_wip_annual_report_line WHERE metric = 'recognized_income'"
    )
    cr.execute(
        "DELETE FROM aunna_wip_annual_report_period_line WHERE metric = 'recognized_income'"
    )

    # 2) Reajustar la secuencia de los conceptos restantes.
    for metric, sequence in NEW_SEQUENCES.items():
        cr.execute(
            "UPDATE aunna_wip_annual_report_line SET sequence = %s WHERE metric = %s",
            (sequence, metric),
        )
        cr.execute(
            "UPDATE aunna_wip_annual_report_period_line SET sequence = %s WHERE metric = %s",
            (sequence, metric),
        )

    # 3) Crear las lineas del nuevo concepto y regenerar la vista horizontal.
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        reports = env["aunna.wip.annual.report"].search([])
        if reports:
            reports._ensure_metric_lines()
            reports._ensure_period_lines()
            reports._update_horizontal_summary_html()
    except Exception:
        _logger.exception(
            "No se pudo regenerar el informe WIP durante la migracion; se regenerara "
            "al abrir o recalcular cada informe."
        )
