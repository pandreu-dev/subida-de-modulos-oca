# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Marcadores para trazar y NO duplicar los asientos del cierre mensual WIP.
    x_zambudio_wip_close = fields.Boolean(
        string="Asiento de cierre WIP",
        copy=False,
        index=True,
    )
    x_zambudio_wip_close_period = fields.Date(
        string="Periodo cierre WIP",
        copy=False,
        help="Mes (dia 1) al que corresponde este asiento de cierre WIP.",
    )
    x_zambudio_wip_close_project_id = fields.Many2one(
        "project.project",
        string="Proyecto cierre WIP",
        copy=False,
        index=True,
    )
    x_zambudio_wip_close_test = fields.Boolean(
        string="Cierre WIP en modo prueba",
        copy=False,
        index=True,
        help="Asiento generado en 'Modo prueba' (desde previsión, no confirmado). "
        "Se deja en borrador y marcado como PRUEBA.",
    )
