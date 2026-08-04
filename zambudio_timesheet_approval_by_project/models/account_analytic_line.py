from odoo import models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    # ------------------------------------------------------------------
    # Peticion de negocio (ago-2026): la validacion de partes de horas debe
    # funcionar COMO ODOO DE SERIE, anadiendo una sola condicion: el RESPONSABLE
    # del proyecto puede validar los partes de SU proyecto (aunque no sea aprobador
    # nativo de partes de horas). Ya NO se restringe a nadie: quien Odoo deja
    # validar, valida; y ademas el jefe del proyecto puede con lo suyo.
    # ------------------------------------------------------------------
    def _zambudio_is_project_manager(self):
        """True si el usuario actual es el RESPONSABLE (``project_id.user_id``) del
        proyecto de esta linea."""
        self.ensure_one()
        return bool(
            self.project_id
            and self.project_id.user_id
            and self.project_id.user_id == self.env.user
        )

    def _zambudio_split_pm_lines(self):
        """Parte el recordset en (lineas de MIS proyectos, resto)."""
        pm_lines = self.filtered(lambda line: line._zambudio_is_project_manager())
        return pm_lines, (self - pm_lines)

    def action_validate_timesheet(self, *args, **kwargs):
        """Validacion nativa de Odoo + el responsable del proyecto valida lo suyo.

        - Las lineas de las que el usuario NO es responsable se validan con el flujo
          nativo y sus permisos de siempre (aprobador del empleado / administrador de
          partes): tal cual funciona Odoo.
        - Las lineas de proyectos de los que el usuario ES responsable se validan
          elevando privilegio solo para ese subconjunto (tiene derecho a validar lo
          suyo aunque no sea aprobador nativo de partes).
        """
        if self.env.su:
            return super().action_validate_timesheet(*args, **kwargs)
        pm_lines, rest = self._zambudio_split_pm_lines()
        result = True
        if rest:
            result = super(AccountAnalyticLine, rest).action_validate_timesheet(
                *args, **kwargs
            )
        if pm_lines:
            result = (
                super(
                    AccountAnalyticLine, pm_lines.sudo()
                ).action_validate_timesheet(*args, **kwargs)
                or result
            )
        return result

    def action_invalidate_timesheet(self, *args, **kwargs):
        """Igual que la validacion: flujo nativo + el responsable del proyecto puede
        des-validar los partes de SU proyecto."""
        if self.env.su:
            return super().action_invalidate_timesheet(*args, **kwargs)
        pm_lines, rest = self._zambudio_split_pm_lines()
        result = True
        if rest:
            result = super(AccountAnalyticLine, rest).action_invalidate_timesheet(
                *args, **kwargs
            )
        if pm_lines:
            result = (
                super(
                    AccountAnalyticLine, pm_lines.sudo()
                ).action_invalidate_timesheet(*args, **kwargs)
                or result
            )
        return result
