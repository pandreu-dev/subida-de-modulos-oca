from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    aunna_department_in_id = fields.Many2one(
        "aunna.stock.department",
        string="Departamento de entrada",
    )

    def _prepare_picking(self):
        vals = super()._prepare_picking()
        if self.aunna_department_in_id:
            vals["aunna_department_in_id"] = self.aunna_department_in_id.id
        return vals
