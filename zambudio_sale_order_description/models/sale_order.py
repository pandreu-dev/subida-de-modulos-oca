from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    zambudio_description = fields.Char(
        string="Descripción",
        help=(
            "Descripcion del pedido para identificarlo y localizarlo mejor. Si se "
            "rellena, alimenta el nombre del proyecto que se cree desde el pedido "
            "(<numero de pedido> - <Descripcion>). No se oculta al confirmar el "
            "presupuesto: queda como descripcion del pedido."
        ),
    )
