# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    # El campo estandar `active` salia rotulado "Obsoleto" (se lee al reves).
    active = fields.Boolean(string="Activo")
