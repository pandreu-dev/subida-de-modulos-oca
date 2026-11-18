"""19.0.3.2.0: los servicios con pedido cuentan al CONFIRMAR el pedido, no al
facturar (Laura, 18/11/2026, «corrige el histórico»). Recalcula los reales de
todo el periodo de cada proyecto con planificación para que los meses pasados
sigan el criterio nuevo; el cron diario solo repasa los dos últimos meses.

Es «end-» y no «post-»: tiene que correr con TODOS los módulos cargados. En
«post-» aún no está el analytic_distribution de stock.move que añaden módulos
posteriores, y las herramientas al 0 % se contaban enteras (ensayo 18/11/2026)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {"tz": "Europe/Madrid"})
    proyectos = env["project.project"].with_context(active_test=False).search(
        [("produccion_linea_ids", "!=", False)])
    motor = env["produccion.real.motor"]
    hechos = 0
    for project in proyectos:
        try:
            with cr.savepoint():
                motor.recalcular_proyectos(project)
            hechos += 1
        except Exception:
            # el cron lo volverá a intentar; no bloquea la actualización
            _logger.exception("Producción: no se pudo recalcular «%s»", project.display_name)
    _logger.info(
        "zambudio_produccion_real_new_version: %s de %s proyectos con planificación "
        "recalculados (servicios al confirmar el pedido)", hechos, len(proyectos))
