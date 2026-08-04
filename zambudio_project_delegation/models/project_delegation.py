from odoo import fields, models


class ZambudioProjectDelegation(models.Model):
    _name = "zambudio.project.delegation"
    _description = "Delegacion"
    _order = "sequence, name, id"

    name = fields.Char(string="Delegacion", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "Ya existe una delegacion con ese nombre.",
        ),
    ]
