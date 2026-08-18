# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    # Campo "Productividad" de Studio. OJO: lo consume ya el modulo
    # zambudio_project_billable; al adoptarlo (mismo nombre) ese modulo sigue
    # funcionando sin cambios. Valores EXACTOS segun la foto de PRE.
    x_studio_selection_field_3ib_1j1am422d = fields.Selection(
        selection=[
            ("Actividad facturable", "Actividad facturable"),
            ("Actividad No facturable", "Actividad No facturable"),
            ("Inactividad", "Inactividad"),
            ("Ausencias", "Ausencias"),
        ],
        string="Productividad",
    )
