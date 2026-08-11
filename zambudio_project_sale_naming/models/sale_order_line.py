from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _zambudio_project_name(self):
        """Nombre del proyecto (y de su cuenta analitica) creado desde este pedido:
        "<numero de pedido> - <Descripcion del pedido>".

        La descripcion sale del campo `zambudio_description` del PEDIDO (no de la linea
        ni del producto). Si esta vacia, se devuelve "" para NO renombrar: el proyecto
        conserva el nombre nativo que crea Odoo.
        """
        self.ensure_one()
        order = self.order_id
        order_name = (order.name or "").strip()
        description = (order.zambudio_description or "").strip()
        if not description:
            return ""
        if order_name:
            return "%s - %s" % (order_name, description)
        return description

    def _timesheet_create_project(self):
        # Respaldo por si este metodo es el que crea el proyecto en esta version: el
        # renombrado real lo hace project.project.create (mas robusto). Es idempotente.
        project = super()._timesheet_create_project()
        if project:
            project._zambudio_apply_sale_line_naming()
        return project
