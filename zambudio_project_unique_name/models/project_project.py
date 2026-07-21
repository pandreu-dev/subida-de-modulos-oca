from odoo import _, api, models
from odoo.exceptions import ValidationError


class ProjectProject(models.Model):
    _inherit = "project.project"

    @api.constrains("name", "company_id")
    def _zambudio_check_unique_name(self):
        """No se puede crear (ni renombrar) un proyecto con un nombre identico al de
        otro. La comparacion ignora mayusculas/minusculas y espacios al principio/final,
        para pillar duplicados reales (p.ej. 'Proyecto A' vs 'proyecto a ').

        Ambito: dentro de la MISMA compania (dos companias distintas si pueden repetir
        nombre). Se usa `sudo()` en la busqueda para que el control no dependa de lo que
        el usuario pueda ver por reglas de acceso."""
        has_template = "is_template" in self._fields
        for project in self:
            # Las PLANTILLAS de proyecto quedan fuera del control: Odoo crea la plantilla
            # COPIANDO un proyecto existente (con el mismo nombre), asi que exigir nombre
            # unico romperia la funcionalidad estandar de "crear plantilla desde
            # proyecto". Solo se controla la unicidad entre proyectos reales.
            if has_template and project.is_template:
                continue
            name = (project.name or "").strip()
            if not name:
                continue
            key = name.casefold()
            domain = [("id", "!=", project.id)]
            if has_template:
                # No dejar que una plantilla bloquee a un proyecto real con ese nombre.
                domain.append(("is_template", "=", False))
            if "company_id" in project._fields:
                domain.append(("company_id", "=", project.company_id.id))
            others = self.sudo().search(domain)
            if any((other.name or "").strip().casefold() == key for other in others):
                raise ValidationError(
                    _(
                        "Ya existe un proyecto con el nombre '%s'. El nombre del "
                        "proyecto debe ser unico."
                    )
                    % project.name
                )
