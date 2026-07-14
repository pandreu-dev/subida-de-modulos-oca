from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    zambudio_project_type = fields.Selection(
        selection=[
            ("closed", "Proyecto cerrado"),
            ("time_materials", "Tiempo & Materiales"),
            ("recurring", "Recurrente"),
        ],
        string="Tipo de proyecto",
    )
