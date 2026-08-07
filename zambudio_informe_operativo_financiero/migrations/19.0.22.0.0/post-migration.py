"""Migracion 19.0.22.0.0

Reforma del bloque de Costes: se sustituyen las tipologias antiguas
(``purchase_costs`` "Pedidos", ``materials`` "Stock interno", ``expenses`` "Gastos")
por las nuevas tipologias por TIPO de pedido (regla de Laura: la forma de calcular no
cambia, solo se REAGRUPA el coste de pedidos por tipologia):

- ``contratas_fix``       Contratas (Fix price)
- ``contratas_admin``     Contratas (Por administracion)
- ``materiales``          Materiales (pedidos de material + Stock interno)
- ``gastos_viaje``        Gastos de Viaje (pedidos de viaje + gastos Kilometraje/Dietas)
- ``licencias_software``  Licencias software
- ``otros``               Otros (catch-all)

Esta migracion adapta los informes ya existentes:

1. Elimina las lineas de los conceptos obsoletos (``purchase_costs``, ``materials``,
   ``expenses``). Los importes ``Prev.`` de esas filas ya no aplican al nuevo esquema.
2. Regenera las lineas de metrica/mensuales y la vista horizontal. Los importes reales
   de las nuevas tipologias se rellenan al pulsar "Recalcular reales".
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OBSOLETE_METRICS = ("purchase_costs", "materials", "expenses")


def migrate(cr, version):
    if not version:
        return

    # 1) Eliminar los conceptos obsoletos de Costes.
    cr.execute(
        "DELETE FROM aunna_wip_annual_report_line WHERE metric IN %s",
        (OBSOLETE_METRICS,),
    )
    cr.execute(
        "DELETE FROM aunna_wip_annual_report_period_line WHERE metric IN %s",
        (OBSOLETE_METRICS,),
    )

    # 2) Crear las lineas de las nuevas tipologias y regenerar la vista horizontal.
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        reports = env["aunna.wip.annual.report"].search([])
        if reports:
            reports._ensure_metric_lines()
            reports._ensure_period_lines()
            reports._update_horizontal_summary_html()
    except Exception:
        _logger.exception(
            "No se pudo regenerar el informe operativo durante la migracion; se "
            "regenerara al abrir o recalcular cada informe."
        )
