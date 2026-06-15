from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AunnaStockNegativeRule(models.Model):
    _name = "aunna.stock.negative.rule"
    _description = "Regla de control de stock negativo"
    _order = "sequence, id"

    name = fields.Char(string="Nombre", required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    action = fields.Selection(
        [
            ("block", "Bloquear"),
            ("allow", "Permitir excepcion"),
        ],
        string="Accion",
        required=True,
        default="block",
    )
    scope = fields.Selection(
        [
            ("product", "Producto"),
            ("category", "Categoria"),
            ("location", "Ubicacion"),
            ("warehouse", "Almacen"),
        ],
        string="Aplicar por",
        required=True,
        default="product",
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto",
        ondelete="cascade",
    )
    categ_id = fields.Many2one(
        "product.category",
        string="Categoria",
        ondelete="cascade",
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Ubicacion",
        domain="[('usage', 'in', ('internal', 'transit'))]",
        ondelete="cascade",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacen",
        ondelete="cascade",
    )
    include_child_categories = fields.Boolean(
        string="Incluir subcategorias",
        default=True,
    )
    include_child_locations = fields.Boolean(
        string="Incluir sububicaciones",
        default=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compania",
        default=lambda self: self.env.company,
    )
    message = fields.Char(
        string="Mensaje adicional",
        help="Texto opcional que se anade al aviso de bloqueo.",
    )

    @api.constrains("scope", "product_tmpl_id", "categ_id", "location_id", "warehouse_id")
    def _check_scope_value(self):
        for rule in self:
            if rule.scope == "product" and not rule.product_tmpl_id:
                raise ValidationError("Debe seleccionar un producto para la regla por producto.")
            if rule.scope == "category" and not rule.categ_id:
                raise ValidationError("Debe seleccionar una categoria para la regla por categoria.")
            if rule.scope == "location" and not rule.location_id:
                raise ValidationError("Debe seleccionar una ubicacion para la regla por ubicacion.")
            if rule.scope == "warehouse" and not rule.warehouse_id:
                raise ValidationError("Debe seleccionar un almacen para la regla por almacen.")

    def _aunna_is_child_of(self, record, parent):
        if not record or not parent:
            return False
        if record == parent:
            return True
        if "parent_path" in record._fields and record.parent_path and parent.parent_path:
            return record.parent_path.startswith(parent.parent_path)
        return bool(record.search_count([("id", "=", record.id), ("id", "child_of", parent.id)]))

    def _aunna_matches(self, product, location, company):
        self.ensure_one()
        if self.company_id and self.company_id != company:
            return False
        if self.scope == "product":
            return product.product_tmpl_id == self.product_tmpl_id
        if self.scope == "category":
            if self.include_child_categories:
                return self._aunna_is_child_of(product.categ_id, self.categ_id)
            return product.categ_id == self.categ_id
        if self.scope == "location":
            if self.include_child_locations:
                return self._aunna_is_child_of(location, self.location_id)
            return location == self.location_id
        if self.scope == "warehouse":
            warehouse_location = self.warehouse_id.view_location_id or self.warehouse_id.lot_stock_id
            return self._aunna_is_child_of(location, warehouse_location)
        return False

    @api.model
    def _aunna_get_matching_rules(self, product, location, company):
        rules = self.sudo().search(
            [
                ("active", "=", True),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ]
        )
        return rules.filtered(lambda rule: rule._aunna_matches(product, location, company))

    @api.model
    def _aunna_should_block(self, product, location, company):
        params = self.env["ir.config_parameter"].sudo()
        enabled = params.get_param("aunna_stock_negative_control.enabled", "False") in (
            "True",
            "1",
            True,
        )
        if not enabled:
            return False, self.browse()

        matching_rules = self._aunna_get_matching_rules(product, location, company)
        allow_rules = matching_rules.filtered(lambda rule: rule.action == "allow")
        if allow_rules:
            return False, allow_rules[:1]

        block_rules = matching_rules.filtered(lambda rule: rule.action == "block")
        return True, block_rules[:1]
