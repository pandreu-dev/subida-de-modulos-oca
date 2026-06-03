from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    x_is_public_holiday_timesheet = fields.Boolean(
        string="Es parte de festivo publico",
        copy=False,
        index=True,
    )
    x_generated_by_public_holiday_bridge = fields.Boolean(
        string="Generado por puente festivos",
        copy=False,
        index=True,
    )
    x_public_holiday_line_id = fields.Many2one(
        "calendar.public.holiday.line",
        string="Linea festivo publico",
        copy=False,
        index=True,
        ondelete="set null",
    )
    x_public_holiday_source = fields.Char(
        string="Origen festivo publico",
        copy=False,
    )
    x_public_holiday_hash = fields.Char(
        string="Hash festivo publico",
        copy=False,
        index=True,
    )
