# -*- coding: utf-8 -*-
"""Normaliza a NEGATIVO los costes de previsión ya cargados.

Criterio de Laura (13/08/2026): los costes se tratan siempre en negativo —en los
actuals Odoo ya los muestra así—, y por coherencia la previsión también. Los
datos anteriores se guardaron en positivo, así que se les cambia el signo una
sola vez. El ingreso no se toca.
"""
CLAVES_COSTE = (
    "horas_internas", "horas_externas", "contratas_fp", "contratas_adm",
    "materiales", "viajes", "riesgos", "rent_lease", "otros", "penalizacion",
    "licencias_software",
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE produccion_plan_linea
           SET importe_previsto = -importe_previsto
         WHERE concepto IN %s
           AND importe_previsto > 0
        """,
        (CLAVES_COSTE,),
    )
    filas = cr.rowcount
    cr.execute(
        """
        UPDATE produccion_plan_linea
           SET importe_real = -importe_real
         WHERE concepto IN %s
           AND importe_real > 0
        """,
        (CLAVES_COSTE,),
    )
    print("aunna_produccion_real_borrar: costes normalizados a negativo — "
          "%s lineas de prevision, %s de real" % (filas, cr.rowcount))
