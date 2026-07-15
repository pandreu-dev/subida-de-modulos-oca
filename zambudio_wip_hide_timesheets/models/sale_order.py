from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_view_timesheet(self):
        """El boton "Partes de horas" de la CABECERA del pedido de venta reconstruye su
        dominio en Python (ignora el dominio almacenado de la accion, que ya parchea el
        heuristico generico de este modulo). Por eso aqui, sobre la accion ya montada,
        se reinyecta el mismo marcador: ocultar los apuntes generados desde asientos
        (ingreso reconocido WIP), que NO son partes de horas reales -> nunca tienen
        `move_line_id`. No oculta ningun parte real."""
        action = super().action_view_timesheet()
        if isinstance(action, dict) and action.get("res_model") == "account.analytic.line":
            domain = list(action.get("domain") or [])
            already = any(
                isinstance(leaf, (list, tuple)) and leaf and leaf[0] == "move_line_id"
                for leaf in domain
            )
            if not already:
                domain.append(("move_line_id", "=", False))
                action["domain"] = domain
        return action
