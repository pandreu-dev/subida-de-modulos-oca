# -*- coding: utf-8 -*-
"""Asignación inicial del grupo de la «puerta de atrás».

Laura (18/08/2026): las personas del grupo «Producción: carga inicial y
corrección de meses cerrados» son los usuarios «Laura Moreno Alonso» y
«Desarrollo Odoo». Se buscan por nombre (y por login, por si el nombre del
usuario técnico cambia) y se les añade el grupo. Idempotente: si ya lo tienen,
no hace nada; si un usuario no existe en la base, avisa y sigue. Cualquier
otro usuario se añade a mano desde Ajustes → Usuarios.
"""
import logging

_logger = logging.getLogger(__name__)

USUARIOS_CARGA_INICIAL = (
    # (nombre del usuario, patrón de login alternativo)
    ("Laura Moreno Alonso", "lmoreno@"),
    ("Desarrollo Odoo", "desarrollo.odoo@"),
)


def asignar_grupo_carga_inicial(env):
    grupo = env.ref("aunna_produccion.group_produccion_carga_inicial", raise_if_not_found=False)
    if not grupo:
        return
    Users = env["res.users"].sudo()
    for nombre, login in USUARIOS_CARGA_INICIAL:
        usuarios = Users.search([
            "|", ("name", "=ilike", nombre), ("login", "=ilike", login + "%"),
        ])
        usuarios = usuarios.filtered(lambda u: u.active) or usuarios
        if not usuarios:
            _logger.warning("aunna_produccion: no encuentro al usuario «%s» (%s…) para "
                            "darle el grupo de carga inicial; asignarlo a mano.", nombre, login)
            continue
        for u in usuarios:
            if grupo not in u.group_ids:
                u.write({"group_ids": [(4, grupo.id)]})
                _logger.info("aunna_produccion: grupo de carga inicial asignado a %s (%s)",
                             u.name, u.login)


def post_init_hook(env):
    asignar_grupo_carga_inicial(env)
