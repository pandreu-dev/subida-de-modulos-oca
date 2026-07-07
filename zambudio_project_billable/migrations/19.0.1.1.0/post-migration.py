"""Migracion 19.0.1.1.0

Elimina el valor por defecto GUARDADO en base de datos (ir.default, el cuadro
"Informacion guardada" con la X que aparece en el desplegable) del campo
Productividad en project.project.

El valor por defecto de Productividad se sigue aportando por CODIGO
(default_get en models/project_project.py), que no genera ese cuadro. Asi el
proyecto nuevo sigue teniendo "Actividad facturable" por defecto, pero sin el
desplegable de "Informacion guardada".
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

PRODUCTIVITY_FIELD = "x_studio_selection_field_3ib_1j1am422d"


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    defaults = env["ir.default"].sudo().search(
        [
            ("field_id.model", "=", "project.project"),
            ("field_id.name", "=", PRODUCTIVITY_FIELD),
        ]
    )
    if defaults:
        _logger.info(
            "Zambudio: eliminando %s valor(es) por defecto guardado(s) (ir.default) "
            "del campo Productividad.",
            len(defaults),
        )
        defaults.unlink()
