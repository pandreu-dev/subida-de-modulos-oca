{
    "name": "Zambudio - Datos maestros (Studio a codigo)",
    "summary": "Pasa a codigo los 5 maestros de Studio: tipo/subtipo empleado, tipo personal, sector y practica CRM",
    "version": "19.0.1.2.0",
    "category": "Technical",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        "mail",
    ],
    "data": [
        "views/master_data_views.xml",
    ],
    # Adopcion de los maestros de Studio (state=base + propiedad del modulo):
    #   - pre_init_hook  -> instalacion NUEVA (p.ej. PRO): adopta antes de reflejar.
    #   - migrations/19.0.1.1.0/pre-migration.py -> ruta de ACTUALIZACION (p.ej. PRE).
    # Los permisos NO van por CSV (el xmlid model_x_... no queda bajo este modulo
    # al ser modelos adoptados); se crean en post_init_hook por nombre.
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
