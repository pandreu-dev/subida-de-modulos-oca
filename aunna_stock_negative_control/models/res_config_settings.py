from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    aunna_negative_stock_control_enabled = fields.Boolean(
        string="Activar control de stock negativo",
        config_parameter="aunna_stock_negative_control.enabled",
        help="Activa el bloqueo de operaciones que dejarian stock negativo.",
    )
    aunna_negative_stock_block_all = fields.Boolean(
        string="Bloquear stock negativo por defecto",
        config_parameter="aunna_stock_negative_control.block_all",
        help=(
            "Si esta marcado, se bloquea cualquier stock negativo salvo reglas "
            "de permiso. Si no esta marcado, solo se bloquean los casos cubiertos "
            "por reglas de bloqueo."
        ),
    )
