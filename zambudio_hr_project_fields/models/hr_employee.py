# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # Definiciones EXACTAS (tipo/relacion) segun la foto de PRE, para adoptar sin
    # tocar las columnas. Las relaciones apuntan a los maestros ya migrados.
    x_studio_tipo_empleado_1 = fields.Many2one(
        "x_tipo_empleado", string="Tipo empleado"
    )
    x_studio_subtipo_empleado = fields.Many2one(
        "x_subtipo_empleado", string="Subtipo empleado"
    )
    x_studio_tipo_de_personal_1 = fields.Many2one(
        "x_tipo_de_personal", string="Tipo personal"
    )
    x_studio_fecha_de_alta_1 = fields.Date(string="Fecha de alta")
