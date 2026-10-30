# -*- coding: utf-8 -*-
"""Vuelca a la ficha del proyecto los datos que hasta ahora vivían en la pestaña.

Indicación de Laura (14/08/2026): el Tipo de proyecto y las fechas de
planificación se toman del proyecto; en las pestañas son informativos.

A partir de esta versión, `tipo_produccion`, `produccion_fecha_inicio` y
`produccion_fecha_fin` se CALCULAN desde `zambudio_project_type`, `date_start` y
`date`. Como en los proyectos ya cargados esos campos de la ficha están vacíos,
hay que copiarles antes el valor que teníamos: si no, al recalcularse se
quedarían sin tipo ni fechas y dejarían de generar planificación.

Solo se rellena lo que está vacío: nunca se pisa un dato ya informado en la ficha.

IMPORTANTE: solo se tocan los proyectos que REALMENTE usan la planificación (los
que tienen líneas de producción). El campo antiguo tenía «cerrado» por defecto en
todos los proyectos aunque nadie lo hubiera elegido, así que volcarlo sin filtrar
marcaría cientos de proyectos como «Proyecto cerrado» sin que sea verdad.
"""
MAPEO_TIPO_INVERSO = {
    "cerrado": "closed",
    "tm": "time_materials",
    "recurrente": "recurring",
}


def migrate(cr, version):
    if not version:
        return

    # El módulo del tipo de proyecto podría no estar aún: si no está la columna,
    # no hay nada que volcar (el depends la creará y quedará vacía).
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'project_project'
           AND column_name = 'zambudio_project_type'
    """)
    hay_columna = bool(cr.fetchone())

    # Solo los proyectos que de verdad tienen producción cargada.
    USA_PRODUCCION = ("EXISTS (SELECT 1 FROM produccion_plan_linea l "
                      "WHERE l.project_id = project_project.id)")

    tipos = 0
    if hay_columna:
        for nuestro, suyo in MAPEO_TIPO_INVERSO.items():
            cr.execute("""
                UPDATE project_project
                   SET zambudio_project_type = %%s
                 WHERE tipo_produccion = %%s
                   AND zambudio_project_type IS NULL
                   AND %s
            """ % USA_PRODUCCION, (suyo, nuestro))
            tipos += cr.rowcount

    cr.execute("""
        UPDATE project_project
           SET date_start = produccion_fecha_inicio
         WHERE produccion_fecha_inicio IS NOT NULL
           AND date_start IS NULL
           AND %s
    """ % USA_PRODUCCION)
    inicios = cr.rowcount

    cr.execute("""
        UPDATE project_project
           SET date = produccion_fecha_fin
         WHERE produccion_fecha_fin IS NOT NULL
           AND date IS NULL
           AND %s
    """ % USA_PRODUCCION)
    fines = cr.rowcount

    # Aviso de lo que queda cojo: proyectos CON planificación pero sin los datos
    # en la ficha. Esos hay que completarlos a mano o no calcularán.
    cr.execute("""
        SELECT p.id, p.name->>'en_US'
          FROM project_project p
         WHERE EXISTS (SELECT 1 FROM produccion_plan_linea l WHERE l.project_id = p.id)
           AND (p.date_start IS NULL OR p.date IS NULL
                OR (%s AND p.zambudio_project_type IS NULL))
         ORDER BY p.id
    """, (hay_columna,))
    incompletos = cr.fetchall()

    print("aunna_produccion: volcados a la ficha del proyecto — "
          "%s tipos, %s fechas de inicio, %s fechas de fin" % (tipos, inicios, fines))
    if incompletos:
        print("aunna_produccion: AVISO — %s proyecto(s) con planificación "
              "siguen sin tipo o sin fecha en la ficha; hay que completarlos:"
              % len(incompletos))
        for pid, nombre in incompletos:
            print("    - [%s] %s" % (pid, nombre))
