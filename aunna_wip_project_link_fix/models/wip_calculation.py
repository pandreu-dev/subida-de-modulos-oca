from odoo import models


class AunnaWipCalculation(models.Model):
    _inherit = "aunna.wip.calculation"

    # ------------------------------------------------------------------
    # 1) Etiquetado de las lineas de ingreso WIP con su calculo y proyecto
    # ------------------------------------------------------------------
    def _aunna_wip_prepare_move_vals(self, settings):
        """Solo etiqueta las lineas de ingreso con su linea de calculo y proyecto.

        NO toca ``analytic_distribution``: el modulo base ya la deja con la cuenta
        analitica del proyecto al 100%. El etiquetado permite, tras contabilizar,
        rellenar el proyecto en los apuntes analiticos generados de forma nativa.
        """
        move_vals = super()._aunna_wip_prepare_move_vals(settings)
        if move_vals:
            self._aunna_wip_tag_income_commands(move_vals, settings)
        return move_vals

    def _aunna_wip_tag_income_commands(self, move_vals, settings):
        income_account = settings.get("income_account")
        if not income_account:
            return move_vals
        # El modulo base emite exactamente una linea de ingreso por cada linea de
        # calculo con WIP, en el mismo orden, de modo que se emparejan 1 a 1.
        income_vals = [
            command[2]
            for command in move_vals.get("line_ids") or []
            if len(command) >= 3
            and isinstance(command[2], dict)
            and command[2].get("account_id") == income_account.id
        ]
        calc_lines = self.line_ids.filtered(lambda line: line.wip_amount)
        for vals, calc_line in zip(income_vals, calc_lines):
            project = self._aunna_wip_calc_line_project(calc_line)
            vals["aunna_wip_calculation_line_id"] = calc_line.id
            vals["aunna_wip_project_id"] = project.id or False
        return move_vals

    def _aunna_wip_calc_line_project(self, calc_line):
        """Proyecto de una linea de calculo WIP. Se usa el proyecto informado; si
        no lo hubiera, se busca el proyecto cuya cuenta analitica coincide (en
        Odoo 19 el campo analitico de ``project.project`` se llama ``account_id``)."""
        if calc_line.project_id:
            return calc_line.project_id
        account = calc_line.analytic_account_id or self._aunna_wip_line_analytic_account(
            calc_line
        )
        if not account:
            return self.env["project.project"]
        Project = self.env["project.project"].sudo()
        for field_name in ("account_id", "analytic_account_id"):
            field = Project._fields.get(field_name)
            if (
                field
                and field.type == "many2one"
                and getattr(field, "comodel_name", False) == "account.analytic.account"
            ):
                project = Project.search([(field_name, "=", account.id)], limit=1)
                if project:
                    return project
        return self.env["project.project"]

    # ------------------------------------------------------------------
    # 2) Reversion: replicar el etiquetado y enriquecer sus apuntes analiticos
    # ------------------------------------------------------------------
    def _aunna_wip_create_native_reversal(self, move, reversal_date, settings):
        reversal_move = super()._aunna_wip_create_native_reversal(
            move, reversal_date, settings
        )
        self._aunna_wip_copy_tags_to_reversal(move, reversal_move)
        reversal_move._aunna_wip_link_analytic_lines_to_projects()
        return reversal_move

    def _aunna_wip_copy_tags_to_reversal(self, move, reversal_move):
        """Los campos tecnicos son ``copy=False``, asi que se replican en la
        reversion emparejando por cuenta contable e importe. NO se toca
        ``analytic_distribution`` (ya se copia sola con ``copy=True``)."""
        currency = move.company_id.currency_id
        used_ids = set()
        for source in move.line_ids.filtered("aunna_wip_calculation_line_id"):
            candidates = reversal_move.line_ids.filtered(
                lambda line: line.id not in used_ids
                and line.account_id == source.account_id
                and not line.aunna_wip_calculation_line_id
            )
            target = candidates.filtered(
                lambda line: currency.compare_amounts(
                    abs(line.balance), abs(source.balance)
                )
                == 0
            )[:1] or candidates[:1]
            if not target:
                continue
            used_ids.add(target.id)
            target.sudo().with_context(
                skip_analytic_sync=True,
                check_move_validity=False,
            ).write(
                {
                    "aunna_wip_calculation_line_id": source.aunna_wip_calculation_line_id.id,
                    "aunna_wip_project_id": source.aunna_wip_project_id.id or False,
                }
            )
        return True

    # ------------------------------------------------------------------
    # 3) Reparacion idempotente de asientos ya existentes
    # ------------------------------------------------------------------
    def action_open_wip_move(self):
        self._aunna_wip_repair_existing(self.move_id)
        return super().action_open_wip_move()

    def action_open_reversal_move(self):
        self._aunna_wip_repair_existing(self.reversal_move_id)
        return super().action_open_reversal_move()

    def _aunna_wip_repair_existing(self, moves):
        for calc in self:
            for move in moves & (calc.move_id | calc.reversal_move_id):
                calc._aunna_wip_tag_posted_move_lines(move)
                move._aunna_wip_link_analytic_lines_to_projects()
        return True

    def _aunna_wip_tag_posted_move_lines(self, move):
        """Etiqueta las lineas de ingreso WIP de un asiento ya creado, emparejando
        con las lineas de calculo por cuenta analitica de la distribucion o por
        importe. NO toca ``analytic_distribution`` (eso lo hace, de forma
        idempotente, ``_aunna_wip_link_analytic_lines_to_projects``)."""
        self.ensure_one()
        settings = self._aunna_wip_accounting_settings(self.company_id)
        income_account = settings.get("income_account")
        if not income_account:
            return True
        currency = self.company_id.currency_id
        calc_lines = self.line_ids.filtered(lambda line: line.wip_amount)
        used_ids = set()
        income_lines = move.line_ids.filtered(
            lambda line: line.account_id == income_account
        )
        for move_line in income_lines:
            calc_line = self._aunna_wip_match_calc_line(
                move_line, calc_lines, used_ids, currency
            )
            if not calc_line:
                continue
            used_ids.add(calc_line.id)
            project = self._aunna_wip_calc_line_project(calc_line)
            vals = {}
            if move_line.aunna_wip_calculation_line_id != calc_line:
                vals["aunna_wip_calculation_line_id"] = calc_line.id
            if move_line.aunna_wip_project_id != project:
                vals["aunna_wip_project_id"] = project.id or False
            if vals:
                move_line.sudo().with_context(
                    skip_analytic_sync=True,
                    check_move_validity=False,
                ).write(vals)
        return True

    def _aunna_wip_match_calc_line(self, move_line, calc_lines, used_ids, currency):
        distribution = move_line.analytic_distribution or {}
        account_ids = set()
        for key in distribution:
            account_ids.update(
                int(part) for part in str(key).split(",") if part.isdigit()
            )
        # a) por cuenta analitica presente en la distribucion
        for calc_line in calc_lines:
            if calc_line.id in used_ids:
                continue
            account = calc_line.analytic_account_id or self._aunna_wip_line_analytic_account(
                calc_line
            )
            if account and account.id in account_ids:
                return calc_line
        # b) por importe (primera linea de calculo libre con el mismo importe)
        amount = self._aunna_wip_move_line_abs_amount(move_line)
        for calc_line in calc_lines:
            if calc_line.id in used_ids:
                continue
            if not currency.compare_amounts(abs(calc_line.wip_amount), amount):
                return calc_line
        # Sin coincidencia fiable: no se fuerza ningun emparejamiento.
        return self.env["aunna.wip.calculation.line"]
