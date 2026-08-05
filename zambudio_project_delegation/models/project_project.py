from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    zambudio_delegation_id = fields.Many2one(
        comodel_name="zambudio.project.delegation",
        string="Delegacion",
        ondelete="restrict",
        tracking=True,
        default=lambda self: self.env[
            "zambudio.project.delegation"
        ]._get_default_murcia_delegation(),
    )
