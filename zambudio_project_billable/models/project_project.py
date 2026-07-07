from odoo import api, fields, models


# Campo "Productividad" (creado con Studio) en project.project y valor de la
# seleccion que representa una actividad facturable.
#
# Si en el futuro Studio recrea el campo con otro nombre tecnico, o cambia la
# etiqueta de "Actividad facturable", basta con ajustar estas dos constantes
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
        """
        defaults = super().default_get(fields_list)
        if PRODUCTIVITY_FIELD in self._fields and not defaults.get(PRODUCTIVITY_FIELD):
            billable_values = self._zambudio_billable_values()
            defaults[PRODUCTIVITY_FIELD] = (
                next(iter(billable_values), False) or BILLABLE_ACTIVITY
            )
        return defaults

    def _zambudio_billable_values(self):
        """Valores tecnicos de Productividad cuya opcion es "Actividad facturable".

        Se compara por VALOR y por ETIQUETA (sin distinguir mayusculas/espacios), de
        forma que funcione aunque Studio haya guardado un valor tecnico distinto de la
        etiqueta visible.
        """
        if PRODUCTIVITY_FIELD not in self._fields:
            return set()
        field_info = self.fields_get([PRODUCTIVITY_FIELD]).get(PRODUCTIVITY_FIELD, {})
        selection = field_info.get("selection") or []
        target = BILLABLE_ACTIVITY.strip().casefold()
        values = {
            value
            for value, label in selection
            if str(value).strip().casefold() == target
            or str(label or "").strip().casefold() == target
        }
        return values or {BILLABLE_ACTIVITY}

    @api.onchange("x_studio_selection_field_3ib_1j1am422d")
    def _onchange_zambudio_productividad(self):
        """Sincronizacion al CAMBIAR el campo Productividad:

        - Si Productividad = "Actividad facturable": se marca Facturable (y el
          cliente pasa a ser obligatorio, controlado en la vista).
        - Si Productividad deja de ser "Actividad facturable": se desmarca Facturable
          y se limpia el cliente.
        """
        billable_values = self._zambudio_billable_values()
        for project in self:
            if project[PRODUCTIVITY_FIELD] in billable_values:
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
