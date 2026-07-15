from odoo import _, models
from odoo.exceptions import UserError

# Grupo "administrador de partes de horas": puede validar CUALQUIER parte (bypass de
# la restriccion por proyecto).
_MANAGER_GROUP_XMLIDS = ("hr_timesheet.group_timesheet_manager",)


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _zambudio_user_is_timesheet_manager(self):
        """True si el usuario es Administrador de partes de horas (puede validar
        todo). Robusto ante xmlid inexistente (no rompe si cambia el nombre)."""
        user = self.env.user
        for xmlid in _MANAGER_GROUP_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group and user in group.sudo().users:
                return True
        return False

    def action_zambudio_validate_project_timesheets(self):
        """Valida (``validated=True``) los partes de horas seleccionados que
        pertenezcan a proyectos de los que el usuario actual es RESPONSABLE
        (``project_id.user_id``). Un Administrador de partes de horas valida
        cualquiera.

        NO toca el flujo nativo de validacion de timesheet_grid: es una via paralela
        para que el jefe de proyecto apruebe lo suyo. El campo ``validated`` es el
        mismo de siempre; solo cambia QUIEN lo marca.
        """
        if "validated" not in self._fields:
            raise UserError(
                _("La validacion de partes de horas (timesheet_grid) no esta disponible.")
            )
        user = self.env.user
        is_manager = self._zambudio_user_is_timesheet_manager()
        # Solo partes de horas (con proyecto) que aun no esten validados. Se excluyen
        # de forma defensiva los partes generados por el puente de festivos: si un PM
        # los validara quedarian bloqueados e impedirian su re-sincronizacion. El
        # getattr protege si ese modulo no esta instalado.
        candidates = self.filtered(
            lambda line: line.project_id
            and not line.validated
            # Excluir apuntes generados desde asientos (ingreso reconocido WIP): tienen
            # project_id pero NO son partes de horas reales (nunca tienen move_line_id).
            and not (("move_line_id" in line._fields) and line.move_line_id)
            and not getattr(line, "x_generated_by_public_holiday_bridge", False)
        )
        if is_manager:
            allowed = candidates
        else:
            allowed = candidates.filtered(
                lambda line: line.project_id.user_id == user
            )
        skipped = self - allowed
        if allowed:
            # sudo: el jefe de proyecto no es necesariamente aprobador de timesheets a
            # nivel de empleado. La restriccion real (solo SUS proyectos) ya se ha
            # comprobado arriba por project_id.user_id, asi que el sudo solo sirve para
            # poder escribir la marca, no para saltarse el control de acceso funcional.
            allowed.sudo().write({"validated": True})
        return self._zambudio_validation_notification(len(allowed), len(skipped))

    def _zambudio_validation_notification(self, validated_count, skipped_count):
        if validated_count and not skipped_count:
            message = _("%s parte(s) de horas validado(s).") % validated_count
            kind = "success"
        elif validated_count and skipped_count:
            message = _(
                "%(ok)s validado(s). %(ko)s omitido(s) (ya validados o de proyectos "
                "que no gestionas)."
            ) % {"ok": validated_count, "ko": skipped_count}
            kind = "warning"
        else:
            message = _(
                "No se ha validado nada. Selecciona partes de horas de proyectos que "
                "gestionas (y que no esten ya validados)."
            )
            kind = "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": kind, "sticky": False},
        }
