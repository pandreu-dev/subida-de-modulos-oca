from odoo import fields, models


class AunnaStockDepartment(models.Model):
    _name = "aunna.stock.department"
    _description = "Departamento BR"
    _order = "sequence, name"

    name = fields.Char(
        string="Nombre",
        required=True,
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )
    active = fields.Boolean(
        default=True,
    )

    _sql_constraints = [
        (
            "name_unique",
            "unique(name)",
            "Ya existe un departamento BR con este nombre.",
        ),
    ]
