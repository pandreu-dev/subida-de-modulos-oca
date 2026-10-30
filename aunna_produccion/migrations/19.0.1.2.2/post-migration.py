# -*- coding: utf-8 -*-
"""Da el grupo de la «puerta de atrás» a los usuarios acordados con Laura
(Laura Moreno Alonso y Desarrollo Odoo). Ver hooks.py."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    from odoo.addons.aunna_produccion.hooks import asignar_grupo_carga_inicial
    asignar_grupo_carga_inicial(api.Environment(cr, SUPERUSER_ID, {}))
