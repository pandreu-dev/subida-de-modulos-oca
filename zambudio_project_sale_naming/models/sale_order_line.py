from odoo import models
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _zambudio_project_name(self):
        """Nombre del proyecto (y de su cuenta analitica) creados desde esta linea de
        pedido de venta: "<numero de pedido> - <descripcion de la linea>".

        Se usa la PRIMERA linea de la descripcion (``name``) para evitar nombres con
        saltos de linea/notas; si no hubiera descripcion, cae al nombre del producto.
        """
        self.ensure_one()
        order_name = (self.order_id.name or "").strip()
        description = (self.name or "").split("\n")[0].strip()
        if not description:
            description = self.product_id.display_name or ""
        if order_name and description:
            return "%s - %s" % (order_name, description)
        return order_name or description

    def _timesheet_create_project(self):
        """Tras crear el proyecto de forma nativa, se fuerza el nombre pedido +
        descripcion de la linea, y se renombra su cuenta analitica con el MISMO nombre.

        Se hace sobre el proyecto ya creado (y no solo en los valores de preparacion)
        para cubrir tambien el caso de plantilla de proyecto, que puede alterar el
        nombre despues. Renombrar la cuenta analitica es cosmetico (el WIP y los costes
        la usan por id, no por nombre)."""
        project = super()._timesheet_create_project()
        name = self._zambudio_project_name()
        if not project or not name:
            return project
        # Si el nombre chocara con el control de nombre unico (p.ej. dos lineas del
        # mismo pedido con la misma descripcion), NO se bloquea la confirmacion del
        # pedido: se conserva el nombre nativo. El savepoint evita dejar la transaccion
        # en estado abortado al capturar la ValidationError.
        try:
            with self.env.cr.savepoint():
                if project.name != name:
                    project.sudo().write({"name": name})
                account = (
                    project.account_id if "account_id" in project._fields else False
                )
                # La cuenta analitica se comparte por pedido: solo se renombra si es
                # DEDICADA a este proyecto (no la usan otros proyectos del pedido), para
                # no pisar el nombre de unos con otros.
                if account and account.name != name:
                    Project = self.env["project.project"].sudo()
                    if Project.search_count([("account_id", "=", account.id)]) <= 1:
                        account.sudo().write({"name": name})
        except ValidationError:
            pass
        return project
