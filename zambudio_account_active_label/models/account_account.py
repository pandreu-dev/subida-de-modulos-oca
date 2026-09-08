# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    # El campo ESTANDAR `active` (archivar/desarchivar la cuenta) aparecia rotulado
    # "Obsoleto", que se lee AL REVES respecto a su valor: active=True significa que
    # la cuenta esta ACTIVA/usable, no obsoleta. En el codigo oficial de Odoo 19 este
    # campo no define `string`, por lo que su etiqueta por defecto es "Active".
    #
    # Aqui solo sobreescribimos la ETIQUETA (string) para dejarla coherente con su
    # significado. No se toca el comportamiento del campo (default=True, tracking, el
    # archivado nativo) ni ningun dato: es puramente la etiqueta.
    #
    # IMPORTANTE: esta etiqueta enganosa fue el origen del incidente al importar el
    # plan de cuentas (la columna "obsoleta" se mapeo contra este campo `active`,
    # invirtiendo el estado y archivando cuentas en uso). La correccion de los DATOS
    # (reactivar las cuentas mal archivadas) es una tarea aparte de este modulo.
    active = fields.Boolean(string="Activo")
