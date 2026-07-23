from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    invoice_in_arrears_initialized = fields.Boolean(
        string="Facturacion vencida inicializada",
        copy=False,
        readonly=True,
    )
    invoice_in_arrears_last_period_start = fields.Date(
        string="Inicio del ultimo periodo vencido facturado",
        copy=False,
        readonly=True,
    )
    invoice_in_arrears_last_period_end = fields.Date(
        string="Fin del ultimo periodo vencido facturado",
        copy=False,
        readonly=True,
    )

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_invoice_in_arrears_init"):
            return result

        watched_fields = {
            "plan_id",
            "start_date",
            "subscription_start_date",
            "date_start",
            "next_invoice_date",
        }
        if watched_fields.intersection(vals):
            non_arrears = self.filtered(
                lambda order: order.invoice_in_arrears_initialized
                and not order._is_invoice_in_arrears_subscription()
            )
            if non_arrears:
                non_arrears.with_context(skip_invoice_in_arrears_init=True).write(
                    {
                        "invoice_in_arrears_initialized": False,
                        "invoice_in_arrears_last_period_start": False,
                        "invoice_in_arrears_last_period_end": False,
                    }
                )

            arrears = self.filtered(lambda order: order._is_invoice_in_arrears_subscription())
            arrears._ensure_invoice_in_arrears_initialized(force="next_invoice_date" in vals)

        return result

    def action_confirm(self):
        arrears_orders = self.filtered(lambda order: order._is_invoice_in_arrears_subscription())
        arrears_orders._ensure_invoice_in_arrears_initialized()
        result = super().action_confirm()
        arrears_orders._ensure_invoice_in_arrears_initialized(force=True)
        return result

    def _get_invoiceable_lines(self, final=False):
        lines = super()._get_invoiceable_lines(final=final)

        if self.env.context.get("subscription_invoice_in_arrears"):
            return lines

        for order in self:
            if not order._is_invoice_in_arrears_subscription():
                continue
            if self.env.context.get("subscription_invoice_in_arrears_skip_recurring"):
                lines -= lines.filtered(
                    lambda line, current_order=order: line.order_id == current_order
                    and line._is_invoice_in_arrears_recurring_line()
                )
                continue

            next_invoice_date = order._get_invoice_in_arrears_due_date()
            if next_invoice_date and order._get_invoice_in_arrears_today() < next_invoice_date:
                lines -= lines.filtered(
                    lambda line, current_order=order: line.order_id == current_order
                    and line._is_invoice_in_arrears_recurring_line()
                )

        return lines

    def _create_invoices(self, grouped=False, final=False, date=None):
        if self.env.context.get("subscription_invoice_in_arrears"):
            return super()._create_invoices(grouped=grouped, final=final, date=date)

        arrears_orders = self.filtered(lambda order: order._is_invoice_in_arrears_subscription())
        if not arrears_orders:
            return super()._create_invoices(grouped=grouped, final=final, date=date)

        moves = self.env["account.move"]
        normal_orders = self - arrears_orders
        if normal_orders:
            moves |= super(SaleOrder, normal_orders)._create_invoices(
                grouped=grouped,
                final=final,
                date=date,
            )

        for order in arrears_orders:
            order._ensure_invoice_in_arrears_initialized(force=True)
            due_date = order._get_invoice_in_arrears_due_date()
            today = order._get_invoice_in_arrears_today()

            if due_date and today < due_date:
                moves |= order._create_invoice_in_arrears_non_recurring_only(grouped, final, date)
                continue

            period_start, period_end = order._get_invoice_in_arrears_period(due_date or today)
            if order._invoice_in_arrears_period_already_processed(period_end):
                moves |= order._create_invoice_in_arrears_non_recurring_only(grouped, final, date)
                continue

            order_context = order._get_invoice_in_arrears_context(period_start, period_end)
            order_moves = super(SaleOrder, order.with_context(**order_context))._create_invoices(
                grouped=grouped,
                final=final,
                date=date,
            )
            moves |= order_moves
            if order._moves_include_invoice_in_arrears_recurring_lines(order_moves):
                order._mark_invoice_in_arrears_period(period_start, period_end, due_date or today)

        return moves

    def _create_recurring_invoice(self, *args, **kwargs):
        arrears_orders = self.filtered(lambda order: order._is_invoice_in_arrears_subscription())
        if not arrears_orders:
            return super()._create_recurring_invoice(*args, **kwargs)

        moves = self.env["account.move"]
        normal_orders = self - arrears_orders
        if normal_orders:
            moves |= super(SaleOrder, normal_orders)._create_recurring_invoice(*args, **kwargs)

        for order in arrears_orders:
            order._ensure_invoice_in_arrears_initialized(force=True)
            due_date = order._get_invoice_in_arrears_due_date()
            today = order._get_invoice_in_arrears_today()

            if due_date and today < due_date:
                continue

            period_start, period_end = order._get_invoice_in_arrears_period(due_date or today)
            if order._invoice_in_arrears_period_already_processed(period_end):
                continue

            order_context = order._get_invoice_in_arrears_context(period_start, period_end)
            order_moves = super(SaleOrder, order.with_context(**order_context))._create_recurring_invoice(
                *args,
                **kwargs,
            )
            if getattr(order_moves, "_name", None) == "account.move":
                moves |= order_moves
                if order._moves_include_invoice_in_arrears_recurring_lines(order_moves):
                    order._mark_invoice_in_arrears_period(period_start, period_end, due_date or today)

        return moves

    def _create_invoice_in_arrears_non_recurring_only(self, grouped=False, final=False, date=None):
        self.ensure_one()
        order = self.with_context(subscription_invoice_in_arrears_skip_recurring=True)
        if not order._get_invoiceable_lines(final=final):
            return self.env["account.move"]
        return super(SaleOrder, order)._create_invoices(grouped=grouped, final=final, date=date)

    def _is_invoice_in_arrears_subscription(self):
        self.ensure_one()
        if "plan_id" not in self._fields or not self.plan_id:
            return False
        if "invoice_in_arrears" not in self.plan_id._fields:
            return False
        return bool(self.plan_id.invoice_in_arrears)

    def _ensure_invoice_in_arrears_initialized(self, force=False):
        if self.env.context.get("skip_invoice_in_arrears_init"):
            return

        for order in self:
            if not order._is_invoice_in_arrears_subscription() or "next_invoice_date" not in order._fields:
                continue

            start_date = order._get_invoice_in_arrears_start_date()
            current_next_date = (
                order._get_invoice_in_arrears_due_date()
                or start_date
                or order._get_invoice_in_arrears_today()
            )
            first_due_date = order._get_invoice_in_arrears_first_due_date(
                start_date or current_next_date
            )

            if order.invoice_in_arrears_initialized:
                needs_first_due = bool(
                    force
                    and first_due_date
                    and not order.invoice_in_arrears_last_period_end
                    and not order._has_previous_invoice_in_arrears_relevant_invoice()
                    and (
                        (start_date and current_next_date <= start_date)
                        or (
                            order._is_invoice_in_arrears_aligned_to_period_start()
                            and current_next_date != first_due_date
                        )
                    )
                )
                if needs_first_due:
                    order.with_context(skip_invoice_in_arrears_init=True).write(
                        {"next_invoice_date": first_due_date}
                    )
                continue

            vals = {"invoice_in_arrears_initialized": True}
            if order._has_previous_invoice_in_arrears_relevant_invoice():
                period_start, period_end = order._get_invoice_in_arrears_period(current_next_date)
                vals.update(
                    {
                        "invoice_in_arrears_last_period_start": period_start,
                        "invoice_in_arrears_last_period_end": period_end,
                        "next_invoice_date": order._add_invoice_in_arrears_period(current_next_date),
                    }
                )
            elif (
                not order.next_invoice_date
                or (start_date and current_next_date <= start_date)
                or (
                    order._is_invoice_in_arrears_aligned_to_period_start()
                    and first_due_date
                    and current_next_date > first_due_date
                )
            ):
                vals["next_invoice_date"] = first_due_date
            else:
                vals["next_invoice_date"] = current_next_date

            order.with_context(skip_invoice_in_arrears_init=True).write(vals)

    def _get_invoice_in_arrears_start_date(self):
        self.ensure_one()
        for field_name in ("start_date", "subscription_start_date", "date_start"):
            if field_name in self._fields and self[field_name]:
                return fields.Date.to_date(self[field_name])
        if "date_order" in self._fields and self.date_order:
            return fields.Date.to_date(self.date_order)
        return False

    def _get_invoice_in_arrears_due_date(self):
        self.ensure_one()
        if "next_invoice_date" in self._fields and self.next_invoice_date:
            return fields.Date.to_date(self.next_invoice_date)
        return False

    def _get_invoice_in_arrears_today(self):
        self.ensure_one()
        forced_today = self.env.context.get("subscription_invoice_in_arrears_today")
        return fields.Date.to_date(forced_today) if forced_today else fields.Date.context_today(self)

    def _get_invoice_in_arrears_period(self, invoice_date):
        self.ensure_one()
        invoice_date = fields.Date.to_date(invoice_date)
        period_end = invoice_date - timedelta(days=1)

        if self.invoice_in_arrears_last_period_end and self.invoice_in_arrears_last_period_end < period_end:
            period_start = self.invoice_in_arrears_last_period_end + timedelta(days=1)
        else:
            period_start = invoice_date - self._get_invoice_in_arrears_period_delta()
            start_date = self._get_invoice_in_arrears_start_date()
            if start_date and period_start < start_date <= period_end:
                period_start = start_date

        if period_start > period_end:
            period_start = period_end

        return period_start, period_end

    def _get_invoice_in_arrears_period_delta(self, periods=1):
        self.ensure_one()
        value, unit = self._get_invoice_in_arrears_period_value_unit()
        value = max(value, 1) * periods

        if unit in ("week", "weekly"):
            return relativedelta(weeks=value)
        if unit in ("month", "monthly"):
            return relativedelta(months=value)
        if unit in ("quarter", "quarterly"):
            return relativedelta(months=3 * value)
        if unit in ("year", "yearly", "annual", "annually"):
            return relativedelta(years=value)
        if unit in ("day", "daily"):
            return relativedelta(days=value)

        raise self._get_invoice_in_arrears_unsupported_unit_error(unit)

    def _get_invoice_in_arrears_period_value_unit(self):
        self.ensure_one()
        plan = self.plan_id
        value = 1
        for field_name in ("billing_period_value", "recurring_interval", "interval", "duration"):
            if field_name in plan._fields and plan[field_name]:
                value = plan[field_name]
                break

        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 1
        value = max(value, 1)

        unit = False
        for field_name in ("billing_period_unit", "recurring_rule_type", "unit", "duration_unit"):
            if field_name in plan._fields and plan[field_name]:
                unit = plan[field_name]
                break

        unit = (unit or "month").lower()
        if unit.endswith("s"):
            unit = unit[:-1]

        return value, unit

    def _get_invoice_in_arrears_unsupported_unit_error(self, unit):
        self.ensure_one()
        return UserError(
            _(
                "No se puede calcular el periodo vencido para el plan %(plan)s "
                "porque la unidad de facturacion %(unit)s no esta soportada."
            )
            % {"plan": self.plan_id.display_name, "unit": unit}
        )

    def _add_invoice_in_arrears_period(self, date_value):
        self.ensure_one()
        return fields.Date.to_date(date_value) + self._get_invoice_in_arrears_period_delta()

    def _get_invoice_in_arrears_first_due_date(self, date_value):
        self.ensure_one()
        date_value = fields.Date.to_date(date_value)
        if not date_value:
            return False

        aligned_due_date = self._get_invoice_in_arrears_aligned_next_period_start(date_value)
        if aligned_due_date:
            return aligned_due_date

        return self._add_invoice_in_arrears_period(date_value)

    def _is_invoice_in_arrears_aligned_to_period_start(self):
        self.ensure_one()
        plan = self.plan_id
        return bool("billing_first_day" in plan._fields and plan.billing_first_day)

    def _get_invoice_in_arrears_aligned_next_period_start(self, date_value):
        self.ensure_one()
        if not self._is_invoice_in_arrears_aligned_to_period_start():
            return False

        value, unit = self._get_invoice_in_arrears_period_value_unit()
        if unit in ("month", "monthly"):
            return self._get_invoice_in_arrears_next_month_boundary(date_value, value)
        if unit in ("quarter", "quarterly"):
            return self._get_invoice_in_arrears_next_month_boundary(date_value, 3 * value)
        if unit in ("year", "yearly", "annual", "annually"):
            return self._get_invoice_in_arrears_next_year_boundary(date_value, value)
        if unit in ("week", "weekly", "day", "daily"):
            return False

        raise self._get_invoice_in_arrears_unsupported_unit_error(unit)

    @staticmethod
    def _get_invoice_in_arrears_next_month_boundary(date_value, month_step):
        month_step = max(int(month_step or 1), 1)
        current_month_index = date_value.year * 12 + date_value.month - 1
        next_month_index = ((current_month_index // month_step) + 1) * month_step
        return date(next_month_index // 12, (next_month_index % 12) + 1, 1)

    @staticmethod
    def _get_invoice_in_arrears_next_year_boundary(date_value, year_step):
        year_step = max(int(year_step or 1), 1)
        current_group_start = ((date_value.year - 1) // year_step) * year_step + 1
        return date(current_group_start + year_step, 1, 1)

    def _invoice_in_arrears_period_already_processed(self, period_end):
        self.ensure_one()
        return bool(
            self.invoice_in_arrears_last_period_end
            and fields.Date.to_date(self.invoice_in_arrears_last_period_end) >= fields.Date.to_date(period_end)
        )

    def _has_previous_invoice_in_arrears_relevant_invoice(self):
        self.ensure_one()
        recurring_lines = self.order_line.filtered(lambda line: line._is_invoice_in_arrears_recurring_line())
        invoice_lines = recurring_lines.invoice_lines.filtered(
            lambda line: line.move_id.state != "cancel"
            and line.move_id.move_type in ("out_invoice", "out_refund")
        )
        return bool(invoice_lines)

    def _get_invoice_in_arrears_context(self, period_start, period_end):
        self.ensure_one()
        return {
            "subscription_invoice_in_arrears": True,
            "subscription_invoice_in_arrears_period_start": fields.Date.to_string(period_start),
            "subscription_invoice_in_arrears_period_end": fields.Date.to_string(period_end),
        }

    def _moves_include_invoice_in_arrears_recurring_lines(self, moves):
        self.ensure_one()
        if not moves or getattr(moves, "_name", None) != "account.move":
            return False
        return any(
            sale_line.order_id == self and sale_line._is_invoice_in_arrears_recurring_line()
            for sale_line in moves.invoice_line_ids.sale_line_ids
        )

    def _mark_invoice_in_arrears_period(self, period_start, period_end, invoice_date):
        self.ensure_one()
        vals = {
            "invoice_in_arrears_initialized": True,
            "invoice_in_arrears_last_period_start": period_start,
            "invoice_in_arrears_last_period_end": period_end,
        }
        next_invoice_date = self._get_invoice_in_arrears_due_date()
        if not next_invoice_date or next_invoice_date <= fields.Date.to_date(invoice_date):
            vals["next_invoice_date"] = self._add_invoice_in_arrears_period(invoice_date)

        self.with_context(skip_invoice_in_arrears_init=True).write(vals)
