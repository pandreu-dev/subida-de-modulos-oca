"""Regresión ORM: costes nuevos del mes abierto sin recálculo previo."""
import base64
import io
from datetime import date, datetime
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.zambudio_produccion_new_version.models.produccion import PERMISO_MESES_CERRADOS


@tagged("post_install", "-at_install")
class TestSeguimientoMesActual(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hoy = date(2026, 10, 30)
        with patch.object(fields.Date, "context_today", return_value=cls.hoy):
            cls.project = cls.env["project.project"].with_context(tz="Europe/Madrid").create({
                "name": "TEST SEGUIMIENTO MES ABIERTO",
                "company_id": cls.env.company.id,
                "tcv": 3000.0,
                "zambudio_project_type": "recurring",
                "date_start": date(2026, 9, 1),
                "date": date(2026, 11, 30),
                "allow_timesheets": True,
            })
            if not cls.project.account_id:
                cls.project._create_analytic_account()
            cls.project.action_generar_planificacion()
            cls.env["produccion.avance.mes"].sincronizar_proyecto(cls.project)
        cls.motor = cls.env["produccion.real.motor"].with_context(tz="Europe/Madrid")
        cls.employee = cls.env["hr.employee"].create({
            "name": "TEST COSTE MES ACTUAL", "company_id": cls.env.company.id,
        })

    def setUp(self):
        super().setUp()
        patcher = patch.object(fields.Date, "context_today", return_value=self.hoy)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _hora(self, importe, fecha=None):
        Line = self.env["account.analytic.line"]
        values = {
            "name": "TEST IMPUTACION", "project_id": self.project.id,
            "employee_id": self.employee.id, "company_id": self.env.company.id,
            "date": fecha or self.hoy, "unit_amount": 1,
        }
        line = Line.create(values)
        # Fijar el coste después del cálculo de coste/hora de hr_timesheet.
        values = {"amount": importe}
        if "validated" in Line._fields:
            values["validated"] = True
        line.write(values)
        return line

    @staticmethod
    def _coste(data, concepto="horas_internas", mes="2026-10"):
        return next(f["celdas"][mes] for f in data["costes"] if f["concepto"] == concepto)

    def test_imputacion_nueva_cambio_y_borrado_sin_recalcular(self):
        plan = self.project.produccion_linea_ids.filtered(
            lambda l: l.fecha_mes == date(2026, 10, 1) and l.concepto == "horas_internas")
        plan.with_context(sin_recalculo=True).write({"importe_previsto": -500, "importe_real": -20})
        antes = self.project.produccion_linea_ids.read(["importe_real", "importe_previsto"])
        marca = self.project.produccion_real_last_update
        hora = self._hora(-125)
        data = self.project.get_produccion_br_data()
        self.assertEqual(self._coste(data)["valor"], -125)
        self.assertEqual(self._coste(data)["desviacion"], 375)
        self.assertEqual(data["estado_mes"]["2026-10"], "actual")
        self.assertEqual(data["avance"]["2026-10"]["valor"], 1000)
        self.assertFalse(data["avance"]["2026-10"]["confirmado"])
        self.assertEqual(data["pm"]["2026-10"], 875)
        hora.write({"amount": -200})
        self.assertEqual(self._coste(self.project.get_produccion_br_data())["valor"], -200)
        hora.unlink()
        self.assertEqual(self._coste(self.project.get_produccion_br_data())["valor"], 0)
        self.assertEqual(self.project.produccion_linea_ids.read(["importe_real", "importe_previsto"]), antes)
        self.assertEqual(self.project.produccion_real_last_update, marca)

    def test_pasado_futuro_y_horas_no_validadas(self):
        for mes in (9, 11):
            plan = self.project.produccion_linea_ids.filtered(
                lambda l: l.fecha_mes == date(2026, mes, 1) and l.concepto == "horas_internas")
            plan.with_context(sin_recalculo=True, permitir_meses_pasados=PERMISO_MESES_CERRADOS).write(
                {"importe_previsto": -500, "importe_real": -50})
        self._hora(-999, date(2026, 10, 31))  # día futuro: todavía no debe contar
        hora = self._hora(-100)
        if "validated" in hora._fields:
            hora.validated = False
            self.assertEqual(self._coste(self.project.get_produccion_br_data())["valor"], 0)
            hora.validated = True
        data = self.project.get_produccion_br_data()
        self.assertEqual(self._coste(data)["valor"], -100)
        self.assertEqual(self._coste(data, mes="2026-09")["valor"], -50)
        self.assertEqual(self._coste(data, mes="2026-11")["valor"], -500)

    def test_cambio_de_mes_sin_octubre_fijo(self):
        with patch.object(fields.Date, "context_today", return_value=date(2026, 11, 1)):
            self._hora(-75, date(2026, 11, 1))
            data = self.project.get_produccion_br_data()
        self.assertEqual(data["estado_mes"]["2026-10"], "pasado")
        self.assertEqual(data["estado_mes"]["2026-11"], "actual")
        self.assertEqual(self._coste(data, mes="2026-11")["valor"], -75)

    def test_filtro_ano_no_consulta_fuentes_del_mes_actual(self):
        with patch.object(type(self.motor), "_costes_por_periodo", side_effect=AssertionError("Consulta innecesaria")):
            self.assertEqual(self.project.get_produccion_br_data(anio=2025)["meses"], [])

    def test_limites_datetime_incluyen_hoy_y_cambio_horario(self):
        self.assertEqual(self.motor._mes_de(datetime(2026, 9, 30, 22)), "2026-10")
        domain = self.motor._dominio_fechas_datetime("date", date(2026, 10, 1), self.hoy)
        self.assertEqual(domain, [("date", ">=", datetime(2026, 9, 30, 22)),
                                  ("date", "<", datetime(2026, 10, 30, 23))])
        for day, hours in ((date(2026, 3, 29), 23), (date(2026, 10, 25), 25)):
            bounds = self.motor._dominio_fechas_datetime("date_done", day, day)
            self.assertEqual((bounds[1][2] - bounds[0][2]).total_seconds(), hours * 3600)

    def test_proyecto_sin_fechas_muestra_aviso_sin_error_rpc(self):
        project = self.env["project.project"].create({
            "name": "TEST SIN FECHAS DE PLANIFICACION",
            "date_start": False,
            "date": False,
        })
        with self.assertRaises(UserError):
            project._meses_planificacion()
        with patch.object(type(self.motor), "_costes_por_periodo", side_effect=AssertionError("Consulta innecesaria")):
            data = project.get_produccion_br_data()
        self.assertEqual(data["meses"], [])
        self.assertTrue(data["aviso_planificacion"])
        self.assertFalse(project.produccion_linea_ids)
        self.assertFalse(project.produccion_avance_ids)

    def test_sin_fechas_con_lineas_no_intenta_repartir_tcv(self):
        self.project.write({"date_start": False, "date": False})
        with patch.object(type(self.project), "_sincronizar_tcv", side_effect=AssertionError("Sin fechas")):
            data = self.project.get_produccion_br_data()
        self.assertEqual(data["meses"], [])
        self.assertTrue(data["aviso_planificacion"])

    def test_cron_salta_proyecto_sin_fechas_y_sigue_con_los_demas(self):
        otro = self.env["project.project"].create({
            "name": "TEST CRON SIN FECHAS", "tcv": 1000.0,
            "zambudio_project_type": "recurring",
            "date_start": date(2026, 9, 1), "date": date(2026, 11, 30),
            "allow_timesheets": True,
        })
        otro.action_generar_planificacion()
        otro.write({"date_start": False, "date": False})
        self.project.produccion_real_last_update = False
        self.env["project.project"].cron_recalcular_produccion_real()
        self.assertTrue(self.project.produccion_real_last_update)

    def test_estructura_autonoma_una_pestana_de_cada(self):
        """Versión autónoma: una sola pestaña de cada, con sus nombres originales."""
        raiz = self.env.ref("zambudio_produccion_real_new_version.view_project_form_br")
        while raiz.inherit_id:
            raiz = raiz.inherit_id
        arch = raiz._get_combined_arch()
        produccion = arch.xpath("//page[@name='produccion']")
        seguimiento = arch.xpath("//page[@name='business_review']")
        self.assertEqual(len(produccion), 1)
        self.assertEqual(len(seguimiento), 1)
        self.assertEqual(produccion[0].get("string"), "Producción")
        self.assertEqual(seguimiento[0].get("string"), "Seguimiento económico")
        self.assertFalse([p for p in arch.xpath("//page") if "new_version" in (p.get("string") or "")])
        self.assertEqual(len(arch.xpath("//widget[@name='produccion_br_view']")), 1)
        self.assertEqual(len(arch.xpath("//page[@name='business_review']/widget[@name='produccion_br_view']")), 1)
        grid = self.env["ir.module.module"].search([
            ("name", "=", "zambudio_produccion_grid_new_version"), ("state", "=", "installed")])
        if grid:
            self.assertEqual(len(arch.xpath(
                "//page[@name='produccion']//button[@name='action_ver_produccion_grid']")), 1)

    def test_excel_mes_en_curso_en_azul(self):
        import openpyxl

        wizard = self.env["produccion.exportar.br"].create({"project_id": self.project.id})
        result = wizard.action_exportar()
        self.assertEqual(result["res_model"], wizard._name)
        self.assertTrue(wizard.fichero)
        libro = openpyxl.load_workbook(io.BytesIO(base64.b64decode(wizard.fichero)))
        cabecera = [c for c in libro.worksheets[0][5] if str(c.value or "").endswith("· En curso")]
        self.assertEqual(len(cabecera), 1)
        self.assertTrue(cabecera[0].fill.fgColor.rgb.endswith("2563EB"))
