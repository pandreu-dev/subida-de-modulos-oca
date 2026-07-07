from odoo import api, fields, models


# Campo "Productividad" (creado con Studio) en project.project y valor de la
# seleccion que representa una actividad facturable.
#
# Si en el futuro Studio recrea el campo con otro nombre tecnico, o cambia la
# etiqueta/valor de "Actividad facturable", basta con ajustar estas dos constantes
# (y el nombre del campo en el decorador @api.onchange de mas abajo).
PRODUCTIVITY_FIELD = "x_studio_selection_field_3ib_1j1am422d"
BILLABLE_ACTIVITY = "Actividad facturable"


class ProjectProject(models.Model):
    _inherit = "project.project"

    # Por defecto, los proyectos se crean como Facturables.
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

    @api.onchange("x_studio_selection_field_3ib_1j1am422d")
    def _onchange_zambudio_productividad(self):
        """Sincronizacion al CAMBIAR el campo Productividad:

        - Si Productividad = "Actividad facturable": se marca Facturable (y el
          cliente pasa a ser obligatorio, controlado en la vista).
        - Si Productividad deja de ser "Actividad facturable": se desmarca Facturable
          y se limpia el cliente.
        """
        for project in self:
            if project[PRODUCTIVITY_FIELD] == BILLABLE_ACTIVITY:
                project.allow_billable = True
            else:
                project.allow_billable = False
                project.partner_id = False

    @api.onchange("allow_billable")
    def _onchange_zambudio_allow_billable(self):
        """Sincronizacion al CAMBIAR el check Facturable:

        - Si se desmarca Facturable: se limpia el cliente.
        - Si se marca Facturable: el cliente es obligatorio (controlado en la vista).
        """
        for project in self:
            if not project.allow_billable:
                project.partner_id = False
