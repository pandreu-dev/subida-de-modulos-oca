{
    "name": "Zambudio - Datos maestros (Studio a codigo)",
    "summary": "Pasa a codigo los 5 maestros de Studio: tipo/subtipo empleado, tipo personal, sector y practica CRM",
    "version": "19.0.1.1.0",
    "category": "Technical",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        "mail",
    ],
    "data": [
        "views/master_data_views.xml",
    ],
    # Los permisos NO van por CSV: como los modelos ya existian como "manual"
    # de Studio, su xmlid no queda bajo este modulo y model_id:id no resuelve.
    # Se crean por hook buscando el modelo por nombre (ver __init__.py).
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
