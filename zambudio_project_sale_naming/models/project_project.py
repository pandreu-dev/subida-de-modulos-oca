import logging

from odoo import api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = "project.project"

    @api.model_create_multi
    def create(self, vals_list):
        """Al crear un proyecto desde una linea de pedido de venta, se le pone (a el y a
        su cuenta analitica) el nombre "numero de pedido - descripcion de la linea".
        Se engancha en la creacion (no en el metodo interno de sale_project) para que
        funcione sea cual sea la ruta por la que Odoo cree el proyecto."""
        projects = super().create(vals_list)
        projects._zambudio_apply_sale_line_naming()
        return projects

    def _zambudio_apply_sale_line_naming(self):
        """Renombra el proyecto (y su cuenta analitica dedicada) segun la linea de
        pedido de venta que lo origino. Idempotente. Si el nombre chocara con el control
        de nombre unico, NO se bloquea la confirmacion del pedido (se conserva el nombre
        nativo)."""
        for project in self:
            line = project.sale_line_id if "sale_line_id" in project._fields else False
            if not line:
                continue
            name = line._zambudio_project_name()
            if not name:
                continue
            try:
                with project.env.cr.savepoint():
                    if project.name != name:
                        project.sudo().write({"name": name})
                    account = (
                        project.account_id if "account_id" in project._fields else False
                    )
                    # Solo si la cuenta analitica es dedicada a este proyecto (no
                    # compartida por varias lineas/proyectos del pedido).
                    if account and account.name != name:
                        Project = project.env["project.project"].sudo()
                        if Project.search_count([("account_id", "=", account.id)]) <= 1:
                            account.sudo().write({"name": name})
            except ValidationError:
                # Choque de nombre unico: se conserva el nombre nativo, sin abortar la
                # confirmacion del pedido. Se deja traza en el log porque si no, desde la
                # interfaz solo se ve "no ha cogido el nombre" y no hay forma de saber
                # por que. Se limpia la cache tras el rollback del savepoint para no
                # dejar el nombre no persistido en memoria.
                _logger.warning(
                    "zambudio_project_sale_naming: no se pudo renombrar el proyecto %s a "
                    "'%s' (ya existe otro proyecto con ese nombre). Se conserva el "
                    "nombre nativo.",
                    project.id,
                    name,
                )
                project.invalidate_recordset(["name"])
                continue
