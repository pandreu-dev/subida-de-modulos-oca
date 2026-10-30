# -*- coding: utf-8 -*-
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.addons.aunna_produccion.models.produccion import PERMISO_MESES_CERRADOS


@tagged("post_install", "-at_install")
class TestMotorProduccionReal(TransactionCase):
    """Coherencia interna del motor y del endpoint BR con datos sintéticos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create(
            {
                "name": "TEST BR",
                "tcv": 12000.0,
                # el tipo y el periodo se informan en la ficha del proyecto
                "zambudio_project_type": "closed",
                "date_start": date(2026, 1, 1),
                "date": date(2026, 6, 30),
            }
        )
        cls.project.action_generar_planificacion()

    def test_avance_sincroniza_y_curva_lineal(self):
        Avance = self.env["produccion.avance.mes"]
        Avance.sincronizar_proyecto(self.project)
        avances = self.project.produccion_avance_ids.sorted("fecha_mes")
        self.assertEqual(len(avances), 6)
        # la curva lineal reparte el TCV completo entre los meses
        total_lineal = sum(a.importe_sugerido_lineal for a in avances)
        self.assertAlmostEqual(total_lineal, 12000.0, places=2)
        # y es creciente en importe acumulado (todos los tramos positivos)
        self.assertTrue(all(a.importe_sugerido_lineal > 0 for a in avances))

    def test_confirmar_no_se_pisa(self):
        Avance = self.env["produccion.avance.mes"]
        Avance.sincronizar_proyecto(self.project)
        primero = self.project.produccion_avance_ids.sorted("fecha_mes")[0]
        primero.write({"importe_confirmado": 999.99})
        primero.action_confirmar()
        Avance.sincronizar_proyecto(self.project)  # una resincronización
        self.assertEqual(primero.importe_confirmado, 999.99)
        self.assertEqual(primero.estado, "confirmado")

    def test_endpoint_br_coherente(self):
        self.env["produccion.avance.mes"].sincronizar_proyecto(self.project)
        datos = self.project.get_produccion_br_data()
        self.assertEqual(len(datos["meses"]), 6)
        # PM = avance + costes (costes en negativo) en cada mes
        for mes in datos["meses"]:
            avance = datos["avance"][mes]["valor"]
            costes = sum(f["celdas"][mes]["valor"] for f in datos["costes"])
            self.assertAlmostEqual(datos["pm"][mes], avance + costes, places=2)
        # WIP = avance acumulado - facturacion acumulada
        acum_av = acum_f = 0.0
        for mes in datos["meses"]:
            acum_av += datos["avance"][mes]["valor"]
            acum_f += datos["facturacion"][mes]
            self.assertAlmostEqual(datos["wip"][mes], acum_av - acum_f, places=2)

    def test_recalculo_marca_frescura(self):
        self.env["produccion.real.motor"].recalcular_proyectos(self.project)
        self.assertTrue(self.project.produccion_real_last_update)

    def test_selection_licencias(self):
        conceptos = dict(
            self.env["produccion.plan.linea"]._fields["concepto"].selection
        )
        self.assertIn("licencias_software", conceptos)

    def test_pm_suma_costes_negativos(self):
        """PM = Ingresos + Costes (los costes van en negativo)."""
        lineas = {l.concepto: l for l in self.project.produccion_linea_ids
                  if l.fecha_mes.month == 1}
        lineas["ingreso"].with_context(
            sin_recalculo=True, permitir_meses_pasados=PERMISO_MESES_CERRADOS).importe_previsto = 1000.0
        lineas["horas_internas"].with_context(
            sin_recalculo=True, permitir_meses_pasados=PERMISO_MESES_CERRADOS).importe_previsto = -300.0
        self.project.invalidate_recordset()
        self.assertAlmostEqual(self.project.produccion_margen, 700.0, places=2)

    def test_mes_en_curso_muestra_prevision(self):
        """El mes en curso NO está cerrado: su ingreso es la previsión vigente."""
        from odoo import fields as odoo_fields
        hoy = odoo_fields.Date.context_today(self.project)
        proj = self.env["project.project"].create({
            "name": "TEST MES EN CURSO",
            "tcv": 1200.0,
            "zambudio_project_type": "recurring",
            "date_start": hoy.replace(day=1),
            "date": hoy.replace(day=1),
        })
        proj.action_generar_planificacion()
        self.env["produccion.avance.mes"].sincronizar_proyecto(proj)
        datos = proj.get_produccion_br_data()
        clave = hoy.strftime("%Y-%m")
        self.assertEqual(datos["estado_mes"][clave], "actual")
        previsto = datos["avance"][clave]["previsto"]
        self.assertAlmostEqual(datos["avance"][clave]["valor"], previsto, places=2)

    def test_estados_de_gasto_incluyen_contabilizado(self):
        estados = self.env["produccion.real.motor"].ESTADOS_GASTO
        for e in ("approved", "posted", "in_payment", "paid"):
            self.assertIn(e, estados)

    def test_signo_movimiento_devoluciones(self):
        """Lo que entra suma coste; lo que sale (devolución) lo resta."""
        Motor = self.env["produccion.real.motor"]
        interna = self.env.ref("stock.stock_location_stock")
        proveedor = self.env.ref("stock.stock_location_suppliers")
        Move = self.env["stock.move"]
        producto = self.env["product.product"].create(
            {"name": "TEST COMPRA", "is_storable": True})
        recepcion = Move.new({
            "product_id": producto.id, "location_id": proveedor.id,
            "location_dest_id": interna.id})
        devolucion = Move.new({
            "product_id": producto.id, "location_id": interna.id,
            "location_dest_id": proveedor.id})
        self.assertEqual(Motor._signo_movimiento(recepcion), 1)
        self.assertEqual(Motor._signo_movimiento(devolucion), -1)

    def test_tipo_y_fechas_se_leen_de_la_ficha(self):
        """El tipo y el periodo son informativos: mandan los campos del proyecto."""
        proj = self.env["project.project"].create({
            "name": "TEST CABECERA",
            "zambudio_project_type": "recurring",
            "date_start": date(2026, 3, 1),
            "date": date(2026, 5, 31),
        })
        self.assertEqual(proj.tipo_produccion, "recurrente")
        self.assertEqual(proj.produccion_fecha_inicio, date(2026, 3, 1))
        self.assertEqual(proj.produccion_fecha_fin, date(2026, 5, 31))
        # y al cambiar la ficha, la pestaña sigue el cambio
        proj.zambudio_project_type = "closed"
        self.assertEqual(proj.tipo_produccion, "cerrado")


@tagged("post_install", "-at_install")
class TestMotorCompras(TransactionCase):
    """Compras: bienes por recepción/devolución, servicios por factura, sin
    duplicar la factura de un bien ya recibido."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from collections import defaultdict
        cls.defaultdict = defaultdict
        cls.company = cls.env.company
        cls.hoy = fields.Date.context_today(cls.env.user)
        m0 = cls.hoy.replace(day=1)
        cls.project = cls.env["project.project"].create({
            "name": "TEST COMPRAS",
            "tcv": 10000.0,
            "zambudio_project_type": "time_materials",
            "date_start": m0,
            "date": m0 + relativedelta(months=2),
            "company_id": cls.company.id,
        })
        plan = cls.env["account.analytic.plan"].search([], limit=1)
        cls.aa = cls.env["account.analytic.account"].create({
            "name": "TEST COMPRAS AA", "plan_id": plan.id, "company_id": cls.company.id})
        cls.project.account_id = cls.aa
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor TEST"})
        cls.bien = cls.env["product.product"].create({
            "name": "TEST BIEN", "type": "consu", "is_storable": True,
            "standard_price": 100.0, "purchase_method": "receive"})
        cls.servicio = cls.env["product.product"].create({
            "name": "TEST SERVICIO", "type": "service", "purchase_method": "purchase"})
        cls.motor = cls.env["produccion.real.motor"]
        cls.d_ini = m0
        cls.d_fin = m0 + relativedelta(months=3)

    def _po(self, producto, qty, precio, tipo):
        po = self.env["purchase.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "tipo_coste_produccion": tipo,
            "order_line": [(0, 0, {
                "product_id": producto.id, "product_qty": qty, "price_unit": precio,
                "analytic_distribution": {str(self.aa.id): 100.0},
            })],
        })
        po.button_confirm()
        return po

    def _reales(self):
        reales = self.defaultdict(float)
        self.motor._acumular_compras(self.project, self.d_ini, self.d_fin, reales)
        return {k[1]: round(v, 2) for k, v in reales.items() if v}

    def _validar(self, picking, cantidades=None):
        for mv in picking.move_ids:
            mv.quantity = cantidades.get(mv.product_id.id, mv.product_uom_qty) if cantidades else mv.product_uom_qty
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_bien_recepcion_devolucion_y_factura_no_duplica(self):
        po = self._po(self.bien, 2, 150.0, "materiales")
        self.assertEqual(self._reales(), {}, "sin recepción no hay coste")
        # recepción de 2 × 150 → −300
        pick = po.picking_ids
        self._validar(pick)
        self.assertEqual(self._reales(), {"materiales": -300.0})
        # devolución de 1 → −150
        Ret = self.env["stock.return.picking"].with_context(
            active_id=pick.id, active_ids=pick.ids, active_model="stock.picking")
        ret = Ret.create({})
        for l in ret.product_return_moves:
            l.quantity = 1
        res = ret.action_create_returns()
        dev = self.env["stock.picking"].browse(res["res_id"])
        self._validar(dev, {self.bien.id: 1})
        self.assertEqual(self._reales(), {"materiales": -150.0})
        # la factura del bien NO vuelve a contar (ya lo contó la recepción)
        po.action_create_invoice()
        bill = po.invoice_ids
        bill.invoice_date = self.hoy
        bill.action_post()
        self.assertEqual(self._reales(), {"materiales": -150.0})
        # y en el detalle aparece marcada como «no computa»
        det = self.motor.detalle_compras(self.project, self.d_ini, self.d_fin)
        fact = [x for x in det if x["origen"].startswith("Factura")]
        self.assertTrue(fact and not fact[0]["computa"])
        rec = [x for x in det if x["origen"] == "Recepción de compra"]
        self.assertTrue(rec and rec[0]["computa"] and rec[0]["importe"] == -300.0)

    def test_servicio_cuenta_por_factura(self):
        po = self._po(self.servicio, 1, 2000.0, "contratas_adm")
        self.assertEqual(self._reales(), {}, "un servicio sin facturar no es coste")
        po.action_create_invoice()
        bill = po.invoice_ids
        bill.invoice_date = self.hoy
        bill.action_post()
        self.assertEqual(self._reales(), {"contratas_adm": -2000.0})
        # el abono resta
        rev = bill._reverse_moves([{"invoice_date": self.hoy}])
        rev.action_post()
        self.assertEqual(self._reales(), {})

    def test_factura_sin_pedido_con_tipo_propio(self):
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.partner.id,
            "invoice_date": self.hoy, "company_id": self.company.id,
            "tipo_coste_produccion": "licencias_software",
            "invoice_line_ids": [(0, 0, {
                "name": "Licencia anual", "quantity": 1, "price_unit": 480.0,
                "analytic_distribution": {str(self.aa.id): 100.0},
            })],
        })
        bill.action_post()
        self.assertEqual(self._reales(), {"licencias_software": -480.0})

    def test_entrega_de_almacen_y_retorno(self):
        Picking = self.env["stock.picking"]
        if "project_id" not in Picking._fields:
            self.skipTest("esta base no tiene proyecto en los albaranes")
        wh = self.env["stock.warehouse"].search([("company_id", "=", self.company.id)], limit=1)
        self.assertTrue(wh, "hace falta un almacén de la compañía")
        clientes = self.env.ref("stock.stock_location_customers")
        # stock previo para poder servir
        self.env["stock.quant"]._update_available_quantity(self.bien, wh.lot_stock_id, 10)
        pick = Picking.create({
            "picking_type_id": wh.out_type_id.id,
            "location_id": wh.lot_stock_id.id,
            "location_dest_id": clientes.id,
            "project_id": self.project.id,
            "move_ids": [(0, 0, {
                "product_id": self.bien.id,
                "product_uom_qty": 3, "product_uom": self.bien.uom_id.id,
                "location_id": wh.lot_stock_id.id, "location_dest_id": clientes.id,
            })],
        })
        pick.action_confirm()
        pick.action_assign()
        self._validar(pick, {self.bien.id: 3})
        reales = self.defaultdict(float)
        self.motor._acumular_almacen(self.project, self.d_ini, self.d_fin, reales)
        self.assertEqual({k[1]: round(v, 2) for k, v in reales.items()}, {"materiales": -300.0})
        # retorno de 1 unidad al almacén → −200
        Ret = self.env["stock.return.picking"].with_context(
            active_id=pick.id, active_ids=pick.ids, active_model="stock.picking")
        ret = Ret.create({})
        for l in ret.product_return_moves:
            l.quantity = 1
        res = ret.action_create_returns()
        dev = self.env["stock.picking"].browse(res["res_id"])
        if "project_id" in dev._fields and not dev.project_id:
            dev.project_id = self.project
        self._validar(dev, {self.bien.id: 1})
        reales = self.defaultdict(float)
        self.motor._acumular_almacen(self.project, self.d_ini, self.d_fin, reales)
        self.assertEqual({k[1]: round(v, 2) for k, v in reales.items()}, {"materiales": -200.0})
        det = self.motor.detalle_compras(self.project, self.d_ini, self.d_fin)
        origenes = sorted(x["origen"] for x in det)
        self.assertIn("Entrega de almacén", origenes)
        self.assertIn("Retorno de material al almacén", origenes)

    def test_gasto_de_viaje_por_referencia(self):
        Motor = self.motor
        if "hr.expense" not in self.env:
            self.skipTest("sin hr_expense")
        Exp = self.env["hr.expense"]
        def gasto(codigo, nombre):
            prod = self.env["product.product"].create({
                "name": nombre, "default_code": codigo, "type": "service",
                "can_be_expensed": True})
            return Exp.new({"product_id": prod.id})
        # Laura (18/08/2026): ALLO, MIL, TRANS & ACC son viaje; el resto no
        self.assertTrue(Motor._es_gasto_de_viaje(gasto("ALLO", "Dietas")))
        self.assertTrue(Motor._es_gasto_de_viaje(gasto("MIL", "Mileage")))
        self.assertTrue(Motor._es_gasto_de_viaje(gasto("TRANS & ACC", "Travel & Accommodation")))
        self.assertFalse(Motor._es_gasto_de_viaje(gasto("FOOD", "Meals")))
        self.assertFalse(Motor._es_gasto_de_viaje(gasto("EXP_GEN", "Expenses")))
        self.assertFalse(Motor._es_gasto_de_viaje(gasto("GIFT", "Regalos")))
        # sin referencia, por nombre EXACTO
        self.assertTrue(Motor._es_gasto_de_viaje(gasto(False, "Viaje y alojamiento")))
        self.assertFalse(Motor._es_gasto_de_viaje(gasto(False, "Phone allowance")))

    def test_aviso_posible_duplicado_almacen(self):
        """Opción A: compra contra el proyecto + entrega desde almacén CON
        proyecto del mismo producto → aviso (las cifras no cambian)."""
        Picking = self.env["stock.picking"]
        if "project_id" not in Picking._fields:
            self.skipTest("esta base no tiene proyecto en los albaranes")
        po = self._po(self.bien, 5, 20.0, "materiales")
        self._validar(po.picking_ids)
        wh = self.env["stock.warehouse"].search([("company_id", "=", self.company.id)], limit=1)
        clientes = self.env.ref("stock.stock_location_customers")
        pick = Picking.create({
            "picking_type_id": wh.out_type_id.id,
            "location_id": wh.lot_stock_id.id, "location_dest_id": clientes.id,
            "project_id": self.project.id,
            "move_ids": [(0, 0, {
                "product_id": self.bien.id, "product_uom_qty": 2,
                "product_uom": self.bien.uom_id.id,
                "location_id": wh.lot_stock_id.id, "location_dest_id": clientes.id,
            })],
        })
        pick.action_confirm(); pick.action_assign()
        self._validar(pick, {self.bien.id: 2})
        avisos = self.motor.posibles_duplicados_almacen(self.project, self.d_ini, self.d_fin)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]["albaran"], pick.name)
        self.assertIn(po.name, avisos[0]["pedidos"])
        self.assertEqual(avisos[0]["comprado"], 5.0)
        # y sigue contando las dos cosas (no decide por nadie)
        reales = self.defaultdict(float)
        self.motor._acumular_compras(self.project, self.d_ini, self.d_fin, reales)
        self.motor._acumular_almacen(self.project, self.d_ini, self.d_fin, reales)
        self.assertAlmostEqual(sum(reales.values()), -100.0 - 200.0, 2)
        # el endpoint lo expone
        self.project.action_generar_planificacion()
        datos = self.project.get_produccion_br_data()
        self.assertEqual(len(datos["posibles_duplicados"]), 1)


    # ------------------------------------------------------------ hallazgos de la revisión 18/08
    def _proyecto_b(self):
        """Segundo proyecto con su propia cuenta analítica (para pedidos multiproyecto)."""
        plan = self.aa.plan_id
        aa_b = self.env["account.analytic.account"].create({
            "name": "TEST COMPRAS AA B", "plan_id": plan.id, "company_id": self.company.id})
        pb = self.env["project.project"].create({
            "name": "TEST COMPRAS B", "tcv": 5000.0, "zambudio_project_type": "time_materials",
            "date_start": self.d_ini, "date": self.d_ini + relativedelta(months=2),
            "company_id": self.company.id})
        pb.account_id = aa_b
        return pb, aa_b

    def _reales_de(self, project):
        reales = self.defaultdict(float)
        self.motor._acumular_compras(project, self.d_ini, self.d_fin, reales)
        return {k[1]: round(v, 2) for k, v in reales.items() if v}

    def test_pedido_con_lineas_de_dos_proyectos_no_duplica(self):
        """C1: cada proyecto solo se lleva SU línea del pedido."""
        pb, aa_b = self._proyecto_b()
        po = self.env["purchase.order"].create({
            "partner_id": self.partner.id, "company_id": self.company.id,
            "tipo_coste_produccion": "materiales",
            "order_line": [
                (0, 0, {"product_id": self.bien.id, "product_qty": 1, "price_unit": 100.0,
                        "analytic_distribution": {str(self.aa.id): 100.0}}),
                (0, 0, {"product_id": self.bien.id, "product_qty": 1, "price_unit": 300.0,
                        "analytic_distribution": {str(aa_b.id): 100.0}}),
            ]})
        po.button_confirm()
        self._validar(po.picking_ids)
        self.assertEqual(self._reales_de(self.project), {"materiales": -100.0})
        self.assertEqual(self._reales_de(pb), {"materiales": -300.0})

    def test_analitica_solo_en_la_factura_cuenta(self):
        """C2: pedido de bien SIN analítica y albarán sin proyecto → la recepción no
        es de nadie; el contable pone la analítica en la factura → cuenta por
        factura (y una sola vez)."""
        po = self.env["purchase.order"].create({
            "partner_id": self.partner.id, "company_id": self.company.id,
            "tipo_coste_produccion": "materiales",
            "order_line": [(0, 0, {"product_id": self.bien.id, "product_qty": 2,
                                   "price_unit": 50.0})]})
        po.button_confirm()
        self._validar(po.picking_ids)
        self.assertEqual(self._reales_de(self.project), {}, "recepción sin analítica: nada")
        po.action_create_invoice()
        bill = po.invoice_ids
        bill.invoice_date = self.hoy
        bill.invoice_line_ids.filtered("product_id").write(
            {"analytic_distribution": {str(self.aa.id): 100.0}})
        bill.action_post()
        self.assertEqual(self._reales_de(self.project), {"materiales": -100.0})
        det = [x for x in self.motor.detalle_compras(self.project, self.d_ini, self.d_fin)
               if x["origen"].startswith("Factura")]
        self.assertTrue(det and det[0]["computa"])

    def test_precio_con_descuento_y_abono_conserva_tipo(self):
        """I1: recepción valorada con el descuento del pedido. I2: el abono de una
        factura sin pedido conserva la tipología."""
        po = self._po(self.bien, 2, 100.0, "materiales")
        po.order_line.discount = 10.0
        self._validar(po.picking_ids)
        self.assertEqual(self._reales_de(self.project), {"materiales": -180.0})
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.partner.id,
            "invoice_date": self.hoy, "company_id": self.company.id,
            "tipo_coste_produccion": "licencias_software",
            "invoice_line_ids": [(0, 0, {"name": "Licencia", "quantity": 1, "price_unit": 300.0,
                                         "analytic_distribution": {str(self.aa.id): 100.0}})]})
        bill.action_post()
        self.assertEqual(self._reales_de(self.project), {"materiales": -180.0,
                                                          "licencias_software": -300.0})
        rev = bill._reverse_moves([{"invoice_date": self.hoy}])
        rev.action_post()
        self.assertEqual(self._reales_de(self.project), {"materiales": -180.0})

    def test_endpoint_sin_fechas_no_revienta(self):
        """I7: proyecto sin Fecha planificada → la pestaña recibe meses=[] (aviso), no error."""
        p = self.env["project.project"].create({"name": "SIN FECHAS", "tcv": 100.0,
                                                "zambudio_project_type": "time_materials"})
        datos = p.get_produccion_br_data()
        self.assertEqual(datos["meses"], [])
