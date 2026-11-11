import importlib.util

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_path


@tagged("post_install", "-at_install")
class TestReturns(TransactionCase):
    """Devoluciones con «Devolver» de un traslado con proyecto: restan lo que cargó su
    salida en lugar de sumar (Laura, 11/11/2026). Caso de la bobina: salen 100 m,
    vuelven 30 m, el proyecto solo carga 70 m."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.stock = cls.wh.lot_stock_id
        cls.van = cls.env["stock.location"].create({
            "name": "FURGONETA DEVOLUCIONES", "usage": "transit", "company_id": cls.company.id})
        plan, _other_plans = cls.env["account.analytic.plan"]._get_all_plans()
        cls.account = cls.env["account.analytic.account"].create({
            "name": "TEST DEVOLUCIONES", "plan_id": plan.id, "company_id": cls.company.id})
        cls.project = cls.env["project.project"].create({
            "name": "TEST DEVOLUCIONES", "company_id": cls.company.id, "account_id": cls.account.id})
        Category = cls.env["product.category"]
        cls.material = cls.env["product.product"].create({
            "name": "TEST BOBINA", "type": "consu", "is_storable": True,
            "categ_id": Category.create({"name": "TEST CABLE"}).id, "standard_price": 1.0})
        cls.tool = cls.env["product.product"].create({
            "name": "TEST LLAVE", "type": "consu", "is_storable": True,
            "categ_id": Category.create({
                "name": "TEST HERRAMIENTAS", "project_delivery_analytic_exclude": True}).id,
            "standard_price": 20.0})
        for product in (cls.material, cls.tool):
            cls.env["stock.quant"]._update_available_quantity(product, cls.stock, 1000)

    def _deliver(self, product, qty):
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.wh.int_type_id.id,
            "location_id": self.stock.id,
            "location_dest_id": self.van.id,
            "project_id": self.project.id,
            "move_ids": [(0, 0, {
                "product_id": product.id, "product_uom_qty": qty, "product_uom": product.uom_id.id,
                "location_id": self.stock.id, "location_dest_id": self.van.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        self._validate(picking, qty)
        return picking

    def _return(self, picking, qty):
        wizard = self.env["stock.return.picking"].with_context(
            active_id=picking.id, active_ids=picking.ids, active_model="stock.picking").create({})
        for line in wizard.product_return_moves:
            line.quantity = qty
        returned = self.env["stock.picking"].browse(wizard.action_create_returns()["res_id"])
        self._validate(returned, qty)
        return returned

    def _validate(self, picking, qty):
        for move in picking.move_ids:
            move.quantity = qty
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def _lines(self, *pickings):
        return self.env["account.analytic.line"].search([
            ("category", "=", "picking_entry"),
            ("ref", "in", [picking.name for picking in pickings]),
        ])

    def _materials(self):
        items = self.project._get_items_from_aal_picking(with_action=False) or [{"billed": 0.0}]
        return items[0]["billed"]

    def test_bobina_100_vuelven_30_carga_70(self):
        delivery = self._deliver(self.material, 100)
        returned = self._return(delivery, 30)
        self.assertEqual(returned.project_id, self.project)
        return_line = self._lines(returned)
        self.assertAlmostEqual(return_line.amount, 30.0, msg="la devolución resta")
        self.assertAlmostEqual(return_line.unit_amount, -30.0)
        if "timesheet_invoice_type" in return_line._fields:  # con sale_timesheet (PRO)
            self.assertEqual(return_line.timesheet_invoice_type, "other_costs",
                             "sigue siendo coste, no ingreso")
        self.assertAlmostEqual(sum(self._lines(delivery, returned).mapped("amount")), -70.0)
        self.assertAlmostEqual(self._materials(), -70.0, msg="fila «Materiales» de la rentabilidad")
        moves, total = self.project._get_project_delivery_stock_move_totals()
        self.assertEqual(len(moves), 2)
        self.assertAlmostEqual(total, -70.0, msg="botón del camión")

    def test_devolucion_total_deja_cero_aunque_cambie_el_coste(self):
        delivery = self._deliver(self.material, 4)
        self.material.standard_price = 1.5
        returned = self._return(delivery, 4)
        self.assertAlmostEqual(self._lines(returned).amount, 4.0,
                               msg="descuenta al coste con que se cargó, no al de hoy")
        self.assertAlmostEqual(self._materials(), 0.0)

    def test_devolucion_de_una_devolucion_vuelve_a_cargar(self):
        delivery = self._deliver(self.material, 5)
        returned = self._return(delivery, 5)
        resent = self._return(returned, 2)
        self.assertAlmostEqual(self._lines(resent).amount, -2.0)
        self.assertAlmostEqual(self._materials(), -2.0)

    def test_herramienta_al_0_no_resta_nada(self):
        delivery = self._deliver(self.tool, 1)
        returned = self._return(delivery, 1)
        self.assertFalse(self._lines(delivery, returned))
        self.assertAlmostEqual(self._materials(), 0.0)

    def test_devolucion_resta_el_porcentaje_que_cargo_la_salida(self):
        # Herramienta entregada al 100 % (antes de la regla o cambiada a mano): su
        # devolución la descuenta entera, aunque la regla de hoy la pondría al 0 %.
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.wh.int_type_id.id,
            "location_id": self.stock.id,
            "location_dest_id": self.van.id,
            "project_id": self.project.id,
            "move_ids": [(0, 0, {
                "product_id": self.tool.id, "product_uom_qty": 1, "product_uom": self.tool.uom_id.id,
                "location_id": self.stock.id, "location_dest_id": self.van.id,
            })],
        })
        picking.move_ids.analytic_distribution = {str(self.account.id): 100.0}
        picking.action_confirm()
        picking.action_assign()
        self._validate(picking, 1)
        self.assertAlmostEqual(self._materials(), -20.0)
        returned = self._return(picking, 1)
        self.assertEqual(returned.move_ids.analytic_distribution, {str(self.account.id): 100.0})
        self.assertAlmostEqual(self._materials(), 0.0)

    def test_migracion_corrige_devoluciones_ya_hechas(self):
        delivery = self._deliver(self.material, 100)
        returned = self._return(delivery, 30)
        # Estado de antes de 19.0.1.3.0: la devolución sumaba coste
        self._lines(returned).write({"amount": -30.0, "unit_amount": 30.0})
        returned.move_ids.project_delivery_analytic_cost = -30.0
        self.assertAlmostEqual(self._materials(), -130.0)
        migration = file_path("project_delivery_analytic_valuation/migrations/19.0.1.3.0/post-migrate.py")
        spec = importlib.util.spec_from_file_location("pdav_post_migrate_19_0_1_3_0", migration)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "19.0.1.2.1")
        self.env.invalidate_all()
        self.assertAlmostEqual(self._materials(), -70.0)
        self.assertAlmostEqual(returned.move_ids.project_delivery_analytic_cost, 30.0)
        self.assertAlmostEqual(sum(self._lines(delivery).mapped("amount")), -100.0,
                               "la salida no se toca")
