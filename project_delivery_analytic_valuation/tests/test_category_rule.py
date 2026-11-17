from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCategoryRule(TransactionCase):
    """Traslados internos con proyecto: cada línea al 100 % salvo las categorías
    marcadas «al 0 %» (herramientas y EPI), que no imputan coste al proyecto."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.stock = cls.wh.lot_stock_id
        cls.int_type = cls.wh.int_type_id
        cls.van = cls.env["stock.location"].create({
            "name": "FURGONETA TEST", "usage": "transit", "company_id": cls.company.id})
        cls.project, cls.account = cls._project("TEST TRASLADOS")
        Category = cls.env["product.category"]
        area = Category.create({"name": "TEST AREA"})
        cls.categ_material = Category.create({"name": "TEST MATERIAL", "parent_id": area.id})
        cls.categ_tool = Category.create({
            "name": "TEST HERRAMIENTA", "parent_id": area.id,
            "project_delivery_analytic_exclude": True})
        categ_tool_sub = Category.create({"name": "TEST ELECTRICA", "parent_id": cls.categ_tool.id})
        cls.material = cls._product("TEST MATERIAL", cls.categ_material, 10.0)
        cls.tool = cls._product("TEST HERRAMIENTA", cls.categ_tool, 20.0)
        cls.tool_sub = cls._product("TEST TALADRO", categ_tool_sub, 5.0)
        for product in (cls.material, cls.tool, cls.tool_sub):
            cls.env["stock.quant"]._update_available_quantity(product, cls.stock, 100)

    @classmethod
    def _project(cls, name):
        plan, _other_plans = cls.env["account.analytic.plan"]._get_all_plans()
        account = cls.env["account.analytic.account"].create({
            "name": name, "plan_id": plan.id, "company_id": cls.company.id})
        project = cls.env["project.project"].create({
            "name": name, "company_id": cls.company.id, "account_id": account.id})
        return project, account

    @classmethod
    def _product(cls, name, category, cost):
        return cls.env["product.product"].create({
            "name": name, "type": "consu", "is_storable": True,
            "categ_id": category.id, "standard_price": cost})

    def _picking(self, lines, project=None, picking_type=None, location_dest=None):
        picking_type = picking_type or self.int_type
        location_dest = location_dest or self.van
        vals = {
            "picking_type_id": picking_type.id,
            "location_id": self.stock.id,
            "location_dest_id": location_dest.id,
            "move_ids": [(0, 0, {
                "product_id": product.id, "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": self.stock.id, "location_dest_id": location_dest.id,
            }) for product, qty in lines],
        }
        if project:
            vals["project_id"] = project.id
        return self.env["stock.picking"].create(vals)

    def _validate(self, picking):
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def _move(self, picking, product):
        return picking.move_ids.filtered(lambda move: move.product_id == product)

    @staticmethod
    def _distribution(move):
        return {key: float(value) for key, value in (move.analytic_distribution or {}).items()}

    def _lines(self, picking):
        return self.env["account.analytic.line"].search([
            ("category", "=", "picking_entry"), ("ref", "=", picking.name)])

    def _sin_distribucion(self, moves):
        """Líneas de antes de 19.0.1.2.0: la columna a NULL."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE stock_move SET analytic_distribution = NULL WHERE id IN %s", [tuple(moves.ids)])
        moves.invalidate_recordset(["analytic_distribution"])

    def test_lineas_al_100_y_herramientas_al_0(self):
        picking = self._picking(
            [(self.material, 2), (self.tool, 1), (self.tool_sub, 1)], project=self.project)
        key = str(self.account.id)
        self.assertEqual(self._distribution(self._move(picking, self.material)), {key: 100.0})
        self.assertEqual(self._distribution(self._move(picking, self.tool)), {key: 0.0})
        self.assertEqual(
            self._distribution(self._move(picking, self.tool_sub)), {key: 0.0},
            "la subcategoría hereda la marca de su categoría padre")

    def test_validar_solo_imputa_lo_no_excluido(self):
        picking = self._picking([(self.material, 2), (self.tool, 1)], project=self.project)
        self._validate(picking)
        lines = self._lines(picking)
        self.assertEqual(lines.product_id, self.material)
        self.assertAlmostEqual(sum(lines.mapped("amount")), -20.0)
        moves, total = self.project._get_project_delivery_stock_move_totals()
        self.assertEqual(moves.product_id, self.material, "el botón no cuenta las herramientas")
        self.assertAlmostEqual(total, -20.0)

    def test_cambiar_y_quitar_el_proyecto_recalcula(self):
        other_project, other_account = self._project("TEST TRASLADOS B")
        picking = self._picking([(self.material, 1), (self.tool, 1)], project=self.project)
        picking.project_id = other_project
        key = str(other_account.id)
        self.assertEqual(self._distribution(self._move(picking, self.material)), {key: 100.0})
        self.assertEqual(self._distribution(self._move(picking, self.tool)), {key: 0.0})
        picking.project_id = False
        self.assertFalse(any(picking.move_ids.mapped("analytic_distribution")))

    def test_proyecto_cambiado_en_traslado_hecho(self):
        other_project, other_account = self._project("TEST TRASLADOS C")
        picking = self._picking([(self.material, 3), (self.tool, 1)], project=self.project)
        self._validate(picking)
        picking.project_id = other_project
        lines = self._lines(picking)
        self.assertEqual(lines.account_id, other_account)
        self.assertAlmostEqual(sum(lines.mapped("amount")), -30.0)
        picking.project_id = False
        self.assertFalse(self._lines(picking), "sin proyecto no queda coste imputado")

    def test_cambio_a_mano_se_respeta(self):
        picking = self._picking([(self.tool, 1)], project=self.project)
        move = picking.move_ids
        key = str(self.account.id)
        move.analytic_distribution = {key: 100.0}
        self._validate(picking)
        self.assertEqual(self._distribution(move), {key: 100.0})
        self.assertAlmostEqual(sum(self._lines(picking).mapped("amount")), -20.0)

    def test_entregas_y_traslados_sin_proyecto_no_cambian(self):
        customers = self.env.ref("stock.stock_location_customers")
        delivery = self._picking(
            [(self.tool, 1)], project=self.project,
            picking_type=self.wh.out_type_id, location_dest=customers)
        self.assertFalse(delivery.move_ids.analytic_distribution)
        internal = self._picking([(self.tool, 1)])
        self.assertFalse(internal.move_ids.analytic_distribution)

    def test_distribucion_de_cabecera_mantiene_la_exclusion(self):
        picking = self._picking([(self.material, 1), (self.tool, 1)], project=self.project)
        other_account = self._project("TEST TRASLADOS D")[1]
        key = str(other_account.id)
        picking.analytic_distribution = {key: 100.0}
        self.assertEqual(self._distribution(self._move(picking, self.material)), {key: 100.0})
        self.assertEqual(self._distribution(self._move(picking, self.tool)), {key: 0.0})

    def test_apunte_con_fecha_del_movimiento(self):
        picking = self._picking([(self.material, 1)], project=self.project)
        self._validate(picking)
        move = picking.move_ids
        past = fields.Datetime.now() - relativedelta(days=40)
        move.date = past
        # al tocar la distribución se regenera el apunte: conserva la fecha del movimiento
        move.analytic_distribution = {str(self.account.id): 100.0}
        line = self._lines(picking)
        self.assertEqual(line.date, fields.Date.context_today(move, past))

    def test_hecho_antes_de_la_regla_sigue_al_100(self):
        picking = self._picking([(self.tool, 1)], project=self.project)
        self._validate(picking)
        self._sin_distribucion(picking.move_ids)
        picking._sync_project_delivery_analytic_lines()
        self.assertFalse(picking.move_ids.analytic_distribution)
        self.assertAlmostEqual(sum(self._lines(picking).mapped("amount")), -20.0)
        moves, total = self.project._get_project_delivery_stock_move_totals()
        self.assertIn(picking.move_ids, moves)
        self.assertAlmostEqual(total, -20.0)

    def test_pendiente_antes_de_la_regla_la_aplica_al_validar(self):
        picking = self._picking([(self.material, 1), (self.tool, 1)], project=self.project)
        self._sin_distribucion(picking.move_ids)
        self._validate(picking)
        self.assertEqual(self._distribution(self._move(picking, self.tool)), {str(self.account.id): 0.0})
        self.assertEqual(self._lines(picking).product_id, self.material)

    def test_actualizacion_rellena_pendientes_vacios(self):
        picking = self._picking([(self.material, 1), (self.tool, 1)], project=self.project)
        self._sin_distribucion(picking.move_ids)
        self.env["stock.move"]._apply_project_delivery_rule_to_pending_moves(only_empty=True)
        key = str(self.account.id)
        self.assertEqual(self._distribution(self._move(picking, self.material)), {key: 100.0})
        self.assertEqual(self._distribution(self._move(picking, self.tool)), {key: 0.0})

    def test_cambio_a_mano_sobrevive_al_pendiente(self):
        picking = self._picking([(self.tool, 2)], project=self.project)
        key = str(self.account.id)
        picking.move_ids.analytic_distribution = {key: 100.0}
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = 1
        picking.move_ids.picked = True
        Form.from_action(self.env, picking.button_validate()).save().process()
        self.assertTrue(picking.backorder_ids)
        self.assertEqual(self._distribution(picking.backorder_ids.move_ids), {key: 100.0})
        self.assertAlmostEqual(sum(self._lines(picking).mapped("amount")), -20.0)

    def test_proyecto_y_linea_en_el_mismo_guardado(self):
        other_project, other_account = self._project("TEST TRASLADOS F")
        picking = self._picking([(self.material, 1), (self.tool, 1)], project=self.project)
        tool_move = self._move(picking, self.tool)
        key = str(other_account.id)
        picking.write({
            "project_id": other_project.id,
            "move_ids": [Command.update(tool_move.id, {"analytic_distribution": {key: 100.0}})],
        })
        self.assertEqual(self._distribution(tool_move), {key: 100.0})
        self.assertEqual(self._distribution(self._move(picking, self.material)), {key: 100.0})

    def test_editar_linea_con_cabecera_en_traslado_hecho(self):
        picking = self._picking([(self.material, 1), (self.tool, 1)], project=self.project)
        key = str(self.account.id)
        picking.analytic_distribution = {key: 100.0}
        self._validate(picking)
        tool_move = self._move(picking, self.tool)
        picking.write({"move_ids": [Command.update(tool_move.id, {"analytic_distribution": {key: 100.0}})]})
        self.assertEqual(self._distribution(tool_move), {key: 100.0})
        self.assertAlmostEqual(sum(self._lines(picking).mapped("amount")), -30.0)

    def test_entrega_con_proyecto_imputa_la_herramienta_al_100(self):
        customers = self.env.ref("stock.stock_location_customers")
        delivery = self._picking(
            [(self.tool, 1)], project=self.project,
            picking_type=self.wh.out_type_id, location_dest=customers)
        self._validate(delivery)
        self.assertAlmostEqual(sum(self._lines(delivery).mapped("amount")), -20.0)

    def test_pasar_a_entrega_quita_el_0(self):
        customers = self.env.ref("stock.stock_location_customers")
        picking = self._picking([(self.tool, 1)], project=self.project)
        self.assertEqual(self._distribution(picking.move_ids), {str(self.account.id): 0.0})
        picking.write({"picking_type_id": self.wh.out_type_id.id, "location_dest_id": customers.id})
        self.assertFalse(picking.move_ids.analytic_distribution)

    def test_boton_pondera_el_porcentaje(self):
        other_account = self._project("TEST TRASLADOS E")[1]
        picking = self._picking([(self.material, 2)], project=self.project)
        picking.analytic_distribution = {str(self.account.id): 50.0, str(other_account.id): 50.0}
        self._validate(picking)
        _moves, total = self.project._get_project_delivery_stock_move_totals()
        self.assertAlmostEqual(total, -10.0)

    def test_marcado_inicial_de_categorias(self):
        Category = self.env["product.category"]
        herramientas = Category.create({"name": "Herramientas"})
        epi = Category.create({"name": " epi "})
        material = Category.create({"name": "Material"})
        marked = Category._mark_default_project_delivery_excluded_categories()
        self.assertIn(herramientas, marked)
        self.assertIn(epi, marked)
        self.assertNotIn(material, marked)
        self.assertTrue(herramientas.project_delivery_analytic_exclude)
        self.assertFalse(material.project_delivery_analytic_exclude)
