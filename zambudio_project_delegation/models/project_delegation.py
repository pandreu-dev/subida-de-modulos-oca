from odoo import api, fields, models


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

    @api.model
    def _get_default_murcia_delegation(self):
        return self.with_context(active_test=False).search(
            [("name", "=ilike", "Murcia")],
            limit=1,
        )

    @api.model
    def _ensure_murcia_delegation(self):
        delegation = self._get_default_murcia_delegation()
        if not delegation:
            delegation = self.create({"name": "Murcia", "sequence": 20})
        elif not delegation.active:
            delegation.active = True
        return delegation
