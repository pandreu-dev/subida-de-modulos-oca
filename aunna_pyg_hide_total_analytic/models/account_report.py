import unicodedata
from collections.abc import Mapping

from odoo import models


class AccountReport(models.Model):
    _inherit = "account.report"

    def get_report_information(self, *args, **kwargs):
        result = super().get_report_information(*args, **kwargs)
        return self._aunna_hide_total_column_from_result(result, args, kwargs)

    def get_report_informations(self, *args, **kwargs):
        super_method = getattr(super(), "get_report_informations", False)
        if super_method:
            result = super_method(*args, **kwargs)
        else:
            result = super().get_report_information(*args, **kwargs)
        return self._aunna_hide_total_column_from_result(result, args, kwargs)

    def _get_lines(self, options, *args, **kwargs):
        lines = super()._get_lines(options, *args, **kwargs)
        if self._aunna_is_profit_and_loss_report():
            removed_indices = self._aunna_total_column_indices(options)
            lines = self._aunna_filter_lines(
                lines,
                removed_indices,
                self._aunna_column_count(options),
            )
        return lines

    def _get_columns_name(self, options, *args, **kwargs):
        columns = super()._get_columns_name(options, *args, **kwargs)
        if self._aunna_is_profit_and_loss_report():
            removed_indices = self._aunna_total_column_indices({"columns": columns})
            columns = self._aunna_remove_indices(columns, removed_indices)
        return columns

    def _aunna_hide_total_column_from_result(self, result, args=False, kwargs=False):
        if not self._aunna_is_profit_and_loss_report() or not isinstance(result, Mapping):
            return result

        options = result.get("options") or self._aunna_options_from_args(args, kwargs)
        if not isinstance(options, Mapping):
            return result

        removed_indices = self._aunna_total_column_indices(options, result)
        if not removed_indices:
            return result

        filtered_result = dict(result)
        source_column_count = self._aunna_column_count(options)

        result_options = result.get("options")
        if isinstance(result_options, Mapping):
            filtered_result["options"] = self._aunna_filter_total_from_options(
                result_options,
                removed_indices,
            )

        if isinstance(result.get("lines"), list):
            filtered_result["lines"] = self._aunna_filter_lines(
                result["lines"],
                removed_indices,
                source_column_count,
            )
        if isinstance(result.get("column_headers"), list):
            filtered_result["column_headers"] = self._aunna_filter_column_headers(
                result["column_headers"],
                removed_indices,
            )
        return filtered_result

    def _aunna_options_from_args(self, args=False, kwargs=False):
        kwargs = kwargs or {}
        if isinstance(kwargs.get("options"), Mapping):
            return kwargs["options"]
        for arg in args or []:
            if isinstance(arg, Mapping):
                return arg
        return {}

    def _aunna_filter_total_from_options(self, options, removed_indices):
        filtered_options = dict(options)
        if isinstance(options.get("columns"), list):
            filtered_options["columns"] = self._aunna_remove_indices(
                options["columns"],
                removed_indices,
            )
        if isinstance(options.get("column_headers"), list):
            filtered_options["column_headers"] = self._aunna_filter_column_headers(
                options["column_headers"],
                removed_indices,
            )
        return filtered_options

    def _aunna_is_profit_and_loss_report(self):
        self.ensure_one()
        xmlid = self.get_external_id().get(self.id, "")
        if xmlid in {
            "account_reports.profit_and_loss",
            "account_reports.account_financial_report_profitandloss0",
        }:
            return True
        normalized_name = self._aunna_normalize_text(self.name or "")
        return any(
            token in normalized_name
            for token in (
                "perdidas y ganancias",
                "perdidas ganancias",
                "profit and loss",
                "profit loss",
                "profit & loss",
                "pyg",
            )
        )

    def _aunna_normalize_text(self, value):
        value = unicodedata.normalize("NFKD", str(value or ""))
        value = "".join(char for char in value if not unicodedata.combining(char))
        return " ".join(value.lower().split())

    def _aunna_is_total_label(self, value):
        return self._aunna_normalize_text(value) == "total"

    def _aunna_total_column_indices(self, options, result=False):
        indices = set()
        columns = options.get("columns") if isinstance(options, Mapping) else []
        if isinstance(columns, list):
            for index, column in enumerate(columns):
                if isinstance(column, Mapping) and self._aunna_is_total_label(
                    column.get("name")
                ):
                    indices.add(index)

        headers = []
        if isinstance(options, Mapping) and isinstance(options.get("column_headers"), list):
            headers = options["column_headers"]
        elif isinstance(result, Mapping) and isinstance(result.get("column_headers"), list):
            headers = result["column_headers"]
        indices.update(self._aunna_total_indices_from_headers(headers))
        return indices

    def _aunna_total_indices_from_headers(self, headers):
        indices = set()
        if not headers:
            return indices
        leaf_row = headers[-1] if isinstance(headers[-1], list) else []
        position = 0
        for cell in leaf_row:
            colspan = self._aunna_cell_colspan(cell)
            if isinstance(cell, Mapping) and self._aunna_is_total_label(cell.get("name")):
                indices.update(range(position, position + colspan))
            position += colspan
        return indices

    def _aunna_cell_colspan(self, cell):
        if not isinstance(cell, Mapping):
            return 1
        try:
            return max(1, int(cell.get("colspan") or 1))
        except (TypeError, ValueError):
            return 1

    def _aunna_filter_column_headers(self, headers, removed_indices):
        if not removed_indices:
            return headers
        filtered_headers = []
        for row in headers:
            if not isinstance(row, list):
                filtered_headers.append(row)
                continue
            filtered_row = []
            position = 0
            for cell in row:
                colspan = self._aunna_cell_colspan(cell)
                covered = set(range(position, position + colspan))
                removed_count = len(covered.intersection(removed_indices))
                position += colspan
                if removed_count >= colspan:
                    continue
                if isinstance(cell, Mapping) and self._aunna_is_total_label(
                    cell.get("name")
                ):
                    continue
                new_cell = dict(cell) if isinstance(cell, Mapping) else cell
                if isinstance(new_cell, dict) and colspan != colspan - removed_count:
                    new_cell["colspan"] = colspan - removed_count
                filtered_row.append(new_cell)
            filtered_headers.append(filtered_row)
        return filtered_headers

    def _aunna_column_count(self, options):
        columns = options.get("columns") if isinstance(options, Mapping) else []
        return len(columns) if isinstance(columns, list) else 0

    def _aunna_filter_lines(self, lines, removed_indices, source_column_count=0):
        if not removed_indices:
            return lines
        filtered_lines = []
        for line in lines:
            if not isinstance(line, Mapping):
                filtered_lines.append(line)
                continue
            filtered_line = dict(line)
            if isinstance(line.get("columns"), list):
                columns = line["columns"]
                if self._aunna_should_filter_line_columns(
                    columns,
                    removed_indices,
                    source_column_count,
                ):
                    filtered_line["columns"] = self._aunna_remove_indices(
                        columns,
                        removed_indices,
                    )
                else:
                    filtered_line["columns"] = columns
            if isinstance(line.get("children"), list):
                filtered_line["children"] = self._aunna_filter_lines(
                    line["children"],
                    removed_indices,
                    source_column_count,
                )
            filtered_lines.append(filtered_line)
        return filtered_lines

    def _aunna_should_filter_line_columns(
        self,
        columns,
        removed_indices,
        source_column_count=0,
    ):
        if not removed_indices:
            return False
        if source_column_count:
            return len(columns) == source_column_count
        return len(columns) > max(removed_indices)

    def _aunna_remove_indices(self, values, removed_indices):
        if not removed_indices:
            return values
        return [
            value
            for index, value in enumerate(values)
            if index not in removed_indices
        ]
