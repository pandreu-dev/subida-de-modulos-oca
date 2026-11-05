import logging
import unicodedata

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Categorías que van al 0 % por defecto (Laura, 05/11/2026): todas las
# «Herramienta» de cada área y las de EPI. Solo se usan para marcarlas una vez;
# después manda la casilla de cada categoría.
DEFAULT_EXCLUDED_CATEGORY_NAMES = {"HERRAMIENTA", "HERRAMIENTAS", "EPI", "EPIS"}


def _normalize_category_name(name):
    text = unicodedata.normalize("NFKD", name or "")
    return text.encode("ascii", "ignore").decode().strip().upper()


class ProductCategory(models.Model):
    _inherit = "product.category"

    project_delivery_analytic_exclude = fields.Boolean(
        string="Al 0 % en traslados con proyecto",
        help="En los traslados internos con proyecto, los productos de esta categoría "
        "(y de sus subcategorías) llevan la distribución analítica al 0 %: su coste no "
        "se imputa al proyecto. Pensado para herramientas y EPI.",
    )

    def _is_project_delivery_analytic_excluded(self):
        """True si la categoría o alguna de sus categorías padre está marcada."""
        self.ensure_one()
        category = self
        while category:
            if category.project_delivery_analytic_exclude:
                return True
            category = category.parent_id
        return False

    @api.model
    def _mark_default_project_delivery_excluded_categories(self):
        categories = self.search([]).filtered(
            lambda category: _normalize_category_name(category.name)
            in DEFAULT_EXCLUDED_CATEGORY_NAMES
        )
        categories.write({"project_delivery_analytic_exclude": True})
        _logger.info(
            "Categorías marcadas al 0 %% en traslados con proyecto: %s",
            ", ".join(categories.mapped("complete_name")) or "ninguna",
        )
        return categories
