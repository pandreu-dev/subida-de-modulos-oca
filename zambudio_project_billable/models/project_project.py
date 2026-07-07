from odoo import api, fields, models


# Campo "Productividad" (creado con Studio) en project.project y valor de la
# seleccion que representa una actividad facturable.
#
# Si en el futuro Studio recrea el campo con otro nombre tecnico, o cambia la
# etiqueta/valor de "Actividad facturable", basta con ajustar estas dos constantes.
PRODUCTIVITY_FIELD = "x_studio_selection_field_3ib_1j1am422d"
BILLABLE_ACTIVITY = "Actividad facturable"


class ProjectProject(models.Model):
    _inherit = "project.project"

    # 1) Por defecto, los proyectos se crean como Facturables.
    allow_billable = fields.Boolean(default=True)

    @api.model
    def default_get(self, fields_list):
        """Por defecto, un proyecto nuevo tiene Productividad = "Actividad
        facturable" (coherente con que se cree Facturable por defecto).

        No se redefine el campo de Studio; solo se aporta su valor por defecto de
        forma segura y solo si no viene ya informado por otra via.
        """
        defaults = super().default_get(fields_list)
        if PRODUCTIVITY_FIELD in self._fields and not defaults.get(PRODUCTIVITY_FIELD):
            defaults[PRODUCTIVITY_FIELD] = BILLABLE_ACTIVITY
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        projects._zambudio_sync_billable_from_productivity()
        return projects

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("zambudio_skip_billable_sync"):
            self._zambudio_sync_billable_from_productivity()
        return result

    def _zambudio_sync_billable_from_productivity(self):
        """Sincroniza el check Facturable con el campo Productividad.

        Regla (solo desmarcar): al guardar, si el proyecto tiene una Productividad
        informada y distinta de "Actividad facturable", se quita el check
        Facturable. No se vuelve a marcar de forma automatica: si un proyecto pasa a
        ser facturable, se marca a mano.

        Un proyecto sin Productividad informada conserva el check (por defecto viene
        marcado); solo se desmarca cuando se le asigna una actividad no facturable.
        """
        if PRODUCTIVITY_FIELD not in self._fields:
            # El campo de Studio no esta disponible: no hay nada que sincronizar.
            return True
        for project in self:
            productivity = project[PRODUCTIVITY_FIELD]
            if (
                project.allow_billable
                and productivity
                and productivity != BILLABLE_ACTIVITY
            ):
                project.with_context(
                    zambudio_skip_billable_sync=True
                ).allow_billable = False
        return True
