# -*- coding: utf-8 -*-
"""Inicializa la «memoria» del TCV aplicado.

Desde 1.2.0 el reparto del ingreso se rehace solo cuando el TCV efectivo
(ficha `tcv_amount` o, si no, el manual) difiere del TCV con el que se repartió
la última vez (`produccion_tcv_aplicado`). Como ese campo nace vacío, sin esta
inicialización TODOS los proyectos con planificación se repartirían de nuevo en
el primer cron/apertura, pisando ingresos ya cargados a mano (p. ej. proyectos
cerrados sin costes previstos quedarían a 0). Aquí se deja constancia de que el
estado actual ya está «aplicado» con el TCV vigente: solo un cambio REAL de TCV
a partir de ahora rehará el reparto.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'project_project' AND column_name = 'tcv_amount'
    """)
    hay_ficha = bool(cr.fetchone())
    expr = ("COALESCE(NULLIF(tcv_amount, 0), tcv, 0)" if hay_ficha
            else "COALESCE(tcv, 0)")
    cr.execute("""
        UPDATE project_project p
           SET produccion_tcv_aplicado = %s
         WHERE EXISTS (SELECT 1 FROM produccion_plan_linea l WHERE l.project_id = p.id)
    """ % expr)
    print("aunna_produccion_borrar: TCV aplicado inicializado en %s proyecto(s) "
          "con planificación (fuente: %s)" % (cr.rowcount, "ficha/manual" if hay_ficha else "manual"))
