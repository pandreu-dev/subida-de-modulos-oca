from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    aunna_negative_stock_control_enabled = fields.Boolean(
        string="Activar control de stock negativo",
        config_parameter="aunna_stock_negative_control.enabled",
        help=(
            "Si esta marcado, bloquea cualquier operacion que dejaria stock "
            "negativo salvo reglas de permiso."
        ),
    )
