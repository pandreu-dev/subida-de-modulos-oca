# -*- coding: utf-8 -*-
{
    "name": "Zambudio Project Task Auto Tags",
    "version": "19.0.1.0.0",
    "summary": "Propaga automaticamente las etiquetas 'Interno'/'Formacion' del proyecto a la tarea.",
    "description": """
Zambudio Project Task Auto Tags
===============================

Sustituye dos automatizaciones de Odoo Studio (on_create_or_write sobre project.task):

- Si el proyecto de la tarea tiene la etiqueta "Interno", anade esa etiqueta a la tarea.
- Si el proyecto de la tarea tiene la etiqueta "Formacion", anade esa etiqueta a la tarea.

Diferencia importante respecto a Studio: la logica original usaba la operacion m2m "set"
(REEMPLAZAR), que podia borrar el resto de etiquetas de la tarea. Aqui se ANADE la etiqueta
con Command.link, sin tocar las demas.

Toda la logica esta implementada en Python como override de create/write del modelo,
sin usar base.automation ni ir.actions.server.
""",
    "author": "Zambudio",
    "license": "LGPL-3",
    "category": "Project",
    "depends": ["project"],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
