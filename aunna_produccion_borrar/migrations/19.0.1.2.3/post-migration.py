# -*- coding: utf-8 -*-
"""Recalcula tipo_produccion / produccion_fecha_inicio / produccion_fecha_fin
en TODOS los proyectos.

Desde 1.1.0 esos tres campos se CALCULAN desde la ficha (zambudio_project_type,
date_start, date). Pero Odoo solo recalcula un campo almacenado en la
actualización cuando la columna es nueva; como ya existía (en 1.0 eran campos
normales), se quedaban con el valor viejo hasta que alguien tocara la ficha:
la pestaña podía decir «Proyecto cerrado» con la ficha en «Recurrente» (o
vacía) y el reparto usar el tipo viejo. Este script los pone al día de una vez.

No dispara _recalcular_ingresos: no toca ningún importe planificado.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'project_project' AND column_name = 'zambudio_project_type'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE project_project
               SET tipo_produccion = CASE zambudio_project_type
                        WHEN 'closed' THEN 'cerrado'
                        WHEN 'time_materials' THEN 'tm'
                        WHEN 'recurring' THEN 'recurrente'
                        ELSE NULL END
        """)
        tipos = cr.rowcount
    else:
        tipos = 0
    cr.execute("""
        UPDATE project_project
           SET produccion_fecha_inicio = date_start,
               produccion_fecha_fin = date
    """)
    print("aunna_produccion_borrar: tipo/fechas de la pestaña sincronizados con la ficha "
          "en %s / %s proyectos" % (tipos, cr.rowcount))
