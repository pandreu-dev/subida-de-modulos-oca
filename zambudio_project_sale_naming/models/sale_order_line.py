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
        # La descripcion (name) se computa en el idioma del CLIENTE y Odoo le antepone el
        # nombre del producto (a veces con la referencia interna: "[COD] ..."). Se compara
        # en ese mismo idioma para poder descartarlo y quedarse con lo que escribio el
        # usuario.
        partner = self.order_id.partner_id
        lang = (partner.lang if partner else False) or self.env.lang
        product = self.product_id.with_context(lang=lang) if self.product_id else False
        product_names = []
        if product:
            # Se comparan los nombres en el idioma del cliente Y en el del usuario: si la
            # linea se escribio con un idioma y se evalua con otro, aun asi se reconoce.
            candidates = (
                product.display_name,
                product.name,
                self.product_id.display_name,
                self.product_id.name,
            )
            for candidate in candidates:
                candidate = (candidate or "").strip()
                if candidate and candidate not in product_names:
                    product_names.append(candidate)

        description = (self.name or "").strip()
        # 1) El usuario escribio su texto DETRAS del nombre del producto, en la misma linea.
        for prefix in product_names:
            if description.startswith(prefix):
                description = description[len(prefix):].strip(" \n\t-:·").strip()
                break
        # 2) Primera linea con contenido que NO sea el nombre del producto. Es el caso
        #    habitual: el usuario escribe su texto en una linea nueva, debajo del producto.
        #    Este paso es el que evita quedarse con el nombre del producto cuando el
        #    prefijo del paso 1 no casa exactamente.
        chosen = ""
        for row in description.split("\n"):
            row = row.strip().lstrip("-:·").strip()
            if row and row not in product_names:
                chosen = row
                break
        # 3) La linea no tiene descripcion propia: se cae al nombre del producto.
        if not chosen and product:
            chosen = (product.display_name or "").strip()

        if order_name and chosen:
            return "%s - %s" % (order_name, chosen)
        return order_name or chosen

    def _timesheet_create_project(self):
        # Respaldo por si este metodo es el que crea el proyecto en esta version: el
        # renombrado real lo hace project.project.create (mas robusto). Es idempotente.
        project = super()._timesheet_create_project()
        if project:
            project._zambudio_apply_sale_line_naming()
        return project
