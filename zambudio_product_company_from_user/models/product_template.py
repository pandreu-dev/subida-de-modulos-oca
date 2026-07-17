from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _zambudio_single_user_company(self):
        """Devuelve la compania del usuario SOLO si pertenece a una unica compania.
        Si el usuario es multi-compania (o superusuario/procesos de sistema), devuelve
        un recordset vacio: a esos NO se les fuerza compania."""
        companies = self.env.user.company_ids
        if len(companies) == 1:
            return companies
        return self.env["res.company"].browse()

    @api.model
    def default_get(self, fields_list):
        """UX: si el usuario es de una sola compania, el formulario de producto ya
        propone esa compania."""
        defaults = super().default_get(fields_list)
        company = self._zambudio_single_user_company()
        if company and "company_id" in self._fields and not defaults.get("company_id"):
            defaults["company_id"] = company.id
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        """Si el usuario pertenece a una sola compania, el producto se crea en esa
        compania sin preguntar (aunque el formulario venga sin compania). Los usuarios
        multi-compania eligen libremente (incluido dejarlo sin compania = compartido)."""
        company = self._zambudio_single_user_company()
        if company and "company_id" in self._fields:
            for vals in vals_list:
                if not vals.get("company_id"):
                    vals["company_id"] = company.id
        return super().create(vals_list)
