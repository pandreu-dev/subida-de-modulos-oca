# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Marcadores para trazar y NO duplicar los asientos del cierre mensual.
    x_zambudio_month_close = fields.Boolean(
        string="Asiento de cierre mensual",
        copy=False,
        index=True,
    )
    x_zambudio_month_close_period = fields.Date(
        string="Periodo cierre mensual",
        copy=False,
        help="Mes (dia 1) al que corresponde este asiento de cierre mensual.",
    )
    x_zambudio_month_close_project_id = fields.Many2one(
        "project.project",
        string="Proyecto cierre mensual",
        copy=False,
        index=True,
    )
    x_zambudio_month_close_test = fields.Boolean(
        string="Cierre mensual en modo prueba",
        copy=False,
        index=True,
        help="Asiento generado en 'Modo prueba' (desde previsión, no confirmado). "
        "Se deja en borrador y marcado como PRUEBA.",
    )
