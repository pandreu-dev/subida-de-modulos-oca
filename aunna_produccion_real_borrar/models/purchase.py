# -*- coding: utf-8 -*-
from odoo import fields, models

from .produccion_real import TIPOS_COMPRA


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    tipo_coste_produccion = fields.Selection(
        TIPOS_COMPRA,
        string="Tipo de coste (producción)",
        help="Clasifica este pedido en la tipología de coste de la declaración "
        "de producción del proyecto. Sin tipo, sus recepciones/facturas cuentan "
        "como «Otros costes».",
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    # Para facturas de proveedor SIN pedido de compra (p. ej. la factura de un
    # subcontratista registrada a mano): sin este dato irían a «Otros costes».
    # Si la factura viene de un pedido, manda el tipo del pedido salvo que aquí
    # se indique otro.
    tipo_coste_produccion = fields.Selection(
        TIPOS_COMPRA,
        string="Tipo de coste (producción)",
        copy=False,
        help="Tipología de coste de producción de esta factura de proveedor "
        "cuando lleva analítica de un proyecto. Si se deja vacío se usa el "
        "tipo del pedido de compra de origen y, si no lo hay, «Otros costes».",
    )
