from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    oca_git_branch = fields.Char(
        string="Rama OCA por defecto",
        config_parameter="instalador_modulos_github_v19.oca_git_branch",
        default="19.0",
    )
    oca_clone_root = fields.Char(
        string="Carpeta donde clonar repositorios",
        config_parameter="instalador_modulos_github_v19.oca_clone_root",
        default="/opt/odoo19/addons/oca/repositories",
    )
    oca_shared_addons_path = fields.Char(
        string="Carpeta OCA visible por Odoo",
        config_parameter="instalador_modulos_github_v19.oca_shared_addons_path",
        default="/opt/odoo19/addons/oca",
    )
    oca_path_strategy = fields.Selection(
        [
            ("symlink", "Enlaces simbolicos"),
            ("copy", "Copiar addons"),
        ],
        string="Como exponer los addons",
        config_parameter="instalador_modulos_github_v19.oca_path_strategy",
        default="symlink",
    )
    oca_persist_addons_path_to_config = fields.Boolean(
        string="Persistir addons_path en el fichero de configuracion",
        config_parameter="instalador_modulos_github_v19.oca_persist_addons_path_to_config",
        default=True,
    )
    oca_odoo_config_path = fields.Char(
        string="Fichero de configuracion de Odoo",
        config_parameter="instalador_modulos_github_v19.oca_odoo_config_path",
        default="/etc/odoo19.conf",
    )
    oca_auto_install_python_deps = fields.Boolean(
        string="Instalar automaticamente dependencias Python",
        config_parameter="instalador_modulos_github_v19.oca_auto_install_python_deps",
        default=False,
    )
    oca_auto_install_binary_deps = fields.Boolean(
        string="Instalar automaticamente dependencias del sistema",
        config_parameter="instalador_modulos_github_v19.oca_auto_install_binary_deps",
        default=False,
    )
    oca_python_install_command = fields.Char(
        string="Comando para instalar dependencias Python",
        config_parameter="instalador_modulos_github_v19.oca_python_install_command",
        default="",
    )
    oca_binary_install_command = fields.Char(
        string="Comando para instalar dependencias del sistema",
        config_parameter="instalador_modulos_github_v19.oca_binary_install_command",
        default="",
    )
