from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _zambudio_project_name(self):
        """Nombre del proyecto (y de su cuenta analitica) creados desde esta linea de
        pedido de venta: "<numero de pedido> - <descripcion de la linea>".

        Odoo suele anteponer el nombre del producto a la descripcion de la linea; en
        ese caso se descarta ese prefijo y se usa el texto que anadio el usuario. Si no
        hubiera descripcion, se cae al nombre del producto.
        """
        self.ensure_one()
        order_name = (self.order_id.name or "").strip()
        description = (self.name or "").strip()
        # La descripcion (name) se computa en el idioma del CLIENTE y suele traer delante
        # el nombre del producto (a veces con la referencia interna: "[COD] ..."). Se
        # quita ese prefijo comparando con display_name y name EN EL IDIOMA DEL CLIENTE,
        # para quedarse con el texto que escribio el usuario.
        partner = self.order_id.partner_id
        lang = (partner.lang if partner else False) or self.env.lang
        product = self.product_id.with_context(lang=lang) if self.product_id else False
        prefixes = (product.display_name, product.name) if product else ()
        for prefix in prefixes:
            prefix = (prefix or "").strip()
            if prefix and description.startswith(prefix):
                description = description[len(prefix):].strip(" \n\t-:·").strip()
                break
        description = description.split("\n")[0].strip() if description else ""
        if not description:
            description = (self.product_id.display_name or "") if self.product_id else ""
        if order_name and description:
            return "%s - %s" % (order_name, description)
        return order_name or description

    def _timesheet_create_project(self):
        # Respaldo por si este metodo es el que crea el proyecto en esta version: el
        # renombrado real lo hace project.project.create (mas robusto). Es idempotente.
        project = super()._timesheet_create_project()
        if project:
            project._zambudio_apply_sale_line_naming()
        return project
