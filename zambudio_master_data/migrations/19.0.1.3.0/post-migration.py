# -*- coding: utf-8 -*-
"""Actualizacion: reponer los ACL de los maestros que falten.

El post_init_hook NO se ejecuta en un `-u`, asi que algun permiso pudo quedar
sin crear (caso real: x_tipo_de_personal, que daba "Error de acceso" al abrir la
ficha de empleado). Reaplicamos la concesion de permisos, que es idempotente.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.zambudio_master_data import _grant_master_permissions


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _grant_master_permissions(env)
