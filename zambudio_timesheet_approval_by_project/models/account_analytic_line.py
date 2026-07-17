from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    # ------------------------------------------------------------------
    # Quien puede validar un parte de horas
    # ------------------------------------------------------------------
    def _zambudio_user_can_validate_timesheet(self):
        """True si el usuario actual puede validar ESTE parte de horas:

        - es el RESPONSABLE del proyecto (``project_id.user_id``), o
        - es el aprobador designado del empleado
          (``employee_id.timesheet_manager_id`` -> "si alguien se pone como validador
          es otra historia").

        Peticion de negocio (jul-2026): NADIE mas -ni siquiera un Administrador de
        partes de horas- puede validar partes de proyectos que no son suyos.
        """
        self.ensure_one()
        user = self.env.user
        project = self.project_id
        if project and project.user_id and project.user_id == user:
            return True
        employee = self.employee_id if "employee_id" in self._fields else False
        approver = (
            employee.timesheet_manager_id
            if employee and "timesheet_manager_id" in employee._fields
            else False
        )
        if approver and approver == user:
            return True
        # Valvula de escape SOLO para datos huerfanos: si el proyecto no tiene
        # responsable Y el empleado no tiene aprobador, para no bloquear del todo la
        # validacion la puede hacer un administrador de SISTEMA (no el administrador de
        # partes, que sigue restringido a sus proyectos).
        if not (project and project.user_id) and not approver:
            if user.has_group("base.group_system"):
                return True
        return False

    # ------------------------------------------------------------------
    # 1) Restringir la validacion NATIVA de timesheet_grid
    # ------------------------------------------------------------------
    def _zambudio_forbidden_to_toggle_validation(self):
        """Subconjunto de partes CON proyecto que el usuario actual NO puede
        validar/des-validar. Los partes sin proyecto quedan fuera (los gestiona el
        flujo nativo con sus reglas de siempre)."""
        return self.filtered(
            lambda line: line.project_id
            and not line._zambudio_user_can_validate_timesheet()
        )

    def action_validate_timesheet(self, *args, **kwargs):
        """Restringe el boton "Validar" nativo: un usuario (incluido un Administrador
        de partes de horas) solo puede validar partes de proyectos de los que es
        responsable, o de empleados de los que es aprobador. Los partes que no le
        corresponden se omiten; si no queda ninguno validable, se avisa.

        No cambia el campo ``validated`` ni el resto del flujo: solo filtra el conjunto
        antes de delegar en el metodo nativo (que corre despues, ya con el subconjunto
        permitido)."""
        forbidden = self._zambudio_forbidden_to_toggle_validation()
        if not forbidden:
            return super().action_validate_timesheet(*args, **kwargs)
        allowed = self - forbidden
        if not allowed:
            raise UserError(
                _(
                    "Solo puedes validar partes de horas de proyectos de los que eres "
                    "responsable (o de empleados de los que eres aprobador)."
                )
            )
        return super(AccountAnalyticLine, allowed).action_validate_timesheet(
            *args, **kwargs
        )

    def action_invalidate_timesheet(self, *args, **kwargs):
        """Misma restriccion al DES-validar: solo el responsable del proyecto (o el
        aprobador del empleado) puede quitar la validacion de un parte."""
        forbidden = self._zambudio_forbidden_to_toggle_validation()
        if not forbidden:
            return super().action_invalidate_timesheet(*args, **kwargs)
        allowed = self - forbidden
        if not allowed:
            raise UserError(
                _(
                    "Solo puedes des-validar partes de horas de proyectos de los que "
                    "eres responsable (o de empleados de los que eres aprobador)."
                )
            )
        return super(AccountAnalyticLine, allowed).action_invalidate_timesheet(
            *args, **kwargs
        )

    # ------------------------------------------------------------------
    # 2) Barrera de datos (refuerzo, independiente de la accion)
    # ------------------------------------------------------------------
    @api.constrains("validated")
    def _zambudio_check_project_manager_validation(self):
        """Refuerzo: impide marcar como validado un parte de un proyecto que el usuario
        no gestiona en escrituras NO-sudo (import, XML-RPC, acciones de servidor de
        usuarios sin privilegio). El boton "Validar" nativo lo cubre el override de
        action_validate_timesheet (filtra antes del sudo del nucleo). Se salta en
        escrituras de sistema (sudo/migraciones) y para partes sin proyecto."""
        if self.env.su:
            return
        for line in self:
            if not line.validated or not line.project_id:
                continue
            if not line._zambudio_user_can_validate_timesheet():
                raise ValidationError(
                    _(
                        "Solo el responsable del proyecto (o el aprobador del empleado) "
                        "puede validar los partes de horas de '%s'."
                    )
                    % (line.project_id.display_name or "")
                )
