# -*- coding: utf-8 -*-
"""Motor de actuals: calcula los importes REALES por proyecto/mes/concepto desde
las fuentes nativas de Odoo y los persiste en produccion.plan.linea.importe_real.

Fuentes (validadas al céntimo contra el sistema anterior el 11/08/2026):
  * Horas: account.analytic.line del proyecto (dimensión P&L interna/externa).
  * Compras de BIENES (material, hardware…): albaranes de RECEPCIÓN del pedido
    de compra menos las DEVOLUCIONES al proveedor, al precio del pedido. El
    coste nace al recibir, no al facturar (criterio de Laura, 14/08/2026).
  * Compras de SERVICIOS (contratas, licencias…) y facturas de proveedor sin
    pedido: no tienen albarán, así que cuentan al contabilizar la factura de
    proveedor con analítica del proyecto (abono resta). Una factura de bienes
    ya contados por su recepción NO se vuelve a contar.
  * Gastos de empleado aprobados/contabilizados/pagados.
  * Material servido desde almacén al proyecto (albarán con proyecto, sin
    pedido de compra) a coste estándar; su retorno lo resta.
  * Facturación: facturas de cliente posteadas con analítica del proyecto.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.aunna_produccion.models.produccion import PERMISO_MESES_CERRADOS

# Conceptos de compra: subconjunto de CLAVES_COSTE clasificable en el pedido
TIPOS_COMPRA = [
    ("contratas_fp", "Contratas (Fix price)"),
    ("contratas_adm", "Contratas (Por administración)"),
    ("materiales", "Materiales"),
    ("viajes", "Gastos de Viaje"),
    ("licencias_software", "Licencias software"),
    ("otros", "Otros costes"),
]


class ProduccionPlanLinea(models.Model):
    _inherit = "produccion.plan.linea"

    # Categoría nueva acordada con Laura (el hueco frente al sistema anterior)
    concepto = fields.Selection(
        selection_add=[("licencias_software", "Licencias software")],
        ondelete={"licencias_software": "cascade"},
    )


class ProduccionPlanAjuste(models.Model):
    _inherit = "produccion.plan.ajuste"

    concepto = fields.Selection(
        selection_add=[("licencias_software", "Licencias software")],
        ondelete={"licencias_software": "cascade"},
    )


class ProduccionCargaInicialLinea(models.TransientModel):
    _inherit = "produccion.carga.inicial.linea"

    concepto = fields.Selection(
        selection_add=[("licencias_software", "Licencias software")],
        ondelete={"licencias_software": "cascade"},
    )


class ProduccionRealMotor(models.AbstractModel):
    """Motor de cálculo de actuals. Sin estado propio: lee fuentes nativas,
    agrega por mes y concepto, y escribe importe_real en las líneas del plan."""

    _name = "produccion.real.motor"
    _description = "Motor de datos reales de producción"

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------
    def recalcular_proyectos(self, projects, fecha_desde=None, fecha_hasta=None):
        """Recalcula actuals de los proyectos dados. Si no se acota el rango,
        usa el periodo de planificación de cada proyecto."""
        for project in projects:
            self._recalcular_proyecto(
                project.with_company(project.company_id), fecha_desde, fecha_hasta
            )

    def _recalcular_proyecto(self, project, fecha_desde, fecha_hasta):
        d_ini = fecha_desde or project.produccion_fecha_inicio or project.date_start
        d_fin = fecha_hasta or project.produccion_fecha_fin or project.date
        if not d_ini or not d_fin:
            return
        # El plan trabaja por MESES completos: los reales también (si el
        # proyecto acaba el 15, lo imputado del 16 al 30 es de ese mes).
        d_ini = d_ini.replace(day=1)
        d_fin = d_fin + relativedelta(day=31)

        reales = self._costes_por_periodo(project, d_ini, d_fin)
        self._escribir_en_plan(project, d_ini, d_fin, reales)
        project.sudo().write({"produccion_real_last_update": fields.Datetime.now()})

    def _costes_por_periodo(self, project, d_ini, d_fin):
        """Lee las cuatro fuentes sin guardar líneas ni marcar el plan al día.

        Compartido por el recálculo persistente y la consulta del mes abierto.
        Las fechas son inclusivas; no se amplían a meses completos aquí.
        """
        reales = defaultdict(float)  # (mes 'YYYY-MM', concepto) -> importe
        self._acumular_horas(project, d_ini, d_fin, reales)
        self._acumular_compras(project, d_ini, d_fin, reales)
        self._acumular_gastos(project, d_ini, d_fin, reales)
        self._acumular_almacen(project, d_ini, d_fin, reales)
        return reales

    def _dominio_fechas_datetime(self, campo, d_ini=None, d_fin=None):
        """Días locales completos convertidos a UTC para campos Datetime.

        Comparar un Datetime con una Date excluía los movimientos de hoy
        posteriores a medianoche. El límite superior es exclusivo (día siguiente)
        y cada extremo se convierte por separado para respetar el cambio horario.
        """
        tz = pytz.timezone(self.env.context.get("tz") or self.env.user.tz or "Europe/Madrid")

        def utc(fecha):
            return tz.localize(datetime.combine(fecha, time.min)).astimezone(
                pytz.utc).replace(tzinfo=None)

        dominio = []
        if d_ini:
            dominio.append((campo, ">=", utc(d_ini)))
        if d_fin:
            dominio.append((campo, "<", utc(d_fin + timedelta(days=1))))
        return dominio

    def _mes_de(self, dt):
        """'YYYY-MM' de un datetime de Odoo (UTC) en la zona horaria del usuario
        (la misma con la que el ORM acota los dominios de fecha)."""
        if not dt:
            return ""
        tz = pytz.timezone(self.env.context.get("tz") or self.env.user.tz or "Europe/Madrid")
        return pytz.utc.localize(dt).astimezone(tz).strftime("%Y-%m")

    # ------------------------------------------------------------------
    # Fuente 1: horas (partes de horas)
    # ------------------------------------------------------------------
    def _cuentas_pl_horas(self, company):
        """Cuentas analíticas 'Horas internas'/'Horas externas' del plan P&L
        de la compañía. Devuelve {analytic_account_id: 'horas_internas'|'horas_externas'}."""
        cuentas = self.env["account.analytic.account"].sudo().search(
            [
                ("name", "in", ["Horas internas", "Horas externas"]),
                "|",
                ("company_id", "=", company.id),
                ("company_id", "=", False),
            ]
        )
        mapa = {}
        for c in cuentas:
            clave = "horas_externas" if "extern" in c.name.lower() else "horas_internas"
            mapa[c.id] = clave
        return mapa

    def _dominio_horas(self, project, d_ini, d_fin, solo_validadas=True):
        """Dominio de partes de horas computables. POLÍTICA DE EMPRESA (11/08/2026):
        solo cuentan como coste las horas VALIDADAS por el responsable."""
        dominio = [
            ("project_id", "=", project.id),
            ("date", ">=", d_ini),
            ("date", "<=", d_fin),
        ]
        # ausencias (solo existe con project_timesheet_holidays)
        if "holiday_id" in self.env["account.analytic.line"]._fields:
            dominio.append(("holiday_id", "=", False))
        if solo_validadas and self.horas_requieren_validacion():
            dominio.append(("validated", "=", True))
        return dominio

    def horas_requieren_validacion(self):
        """True si esta base tiene el circuito de validación de partes."""
        return "validated" in self.env["account.analytic.line"]._fields

    def _acumular_horas(self, project, d_ini, d_fin, reales):
        mapa_pl = self._cuentas_pl_horas(project.company_id)
        lineas = self.env["account.analytic.line"].sudo().search(
            self._dominio_horas(project, d_ini, d_fin)
        )
        campos_plan = [
            f for f in lineas._fields
            if f.startswith("x_plan") and f.endswith("_id")
        ]
        for lin in lineas:
            concepto = "horas_internas"  # fallback documentado: sin dimensión → interna
            for campo in campos_plan:
                cuenta = lin[campo]
                if cuenta and cuenta.id in mapa_pl:
                    concepto = mapa_pl[cuenta.id]
                    break
            # el apunte de horas ya lleva el coste en negativo (horas × coste/hora)
            reales[(lin.date.strftime("%Y-%m"), concepto)] += lin.amount

    # ------------------------------------------------------------------
    # Fuente 2: compras (facturas de proveedor con analítica del proyecto)
    # ------------------------------------------------------------------
    @staticmethod
    def _cuenta_analitica(project):
        """Cuenta analítica del proyecto (account_id en Odoo 19; fallback al
        nombre antiguo por si se instala en una base migrada)."""
        for campo in ("account_id", "analytic_account_id"):
            if campo in project._fields and project[campo]:
                return project[campo]
        return project.env["account.analytic.account"]

    # Mapeo de los tipos de pedido de compra reales de la casa a nuestras
    # tipologías de coste. Se busca por NOMBRE para que siga funcionando aunque
    # el módulo que define esos tipos se retire.
    MAPEO_TIPO_PEDIDO = {
        "subcontrata (fix price)": "contratas_fp",
        "subcontrata (t&m)": "contratas_adm",
        "servicios": "contratas_adm",
        "material": "materiales",
        "hardware": "materiales",
        "herramienta": "materiales",
        "epi": "materiales",
        "software (licencias)": "licencias_software",
        "gastos de viaje": "viajes",
        "flota vehiculos": "viajes",
        "flota vehículos": "viajes",
        "documentacion": "otros",
        "documentación": "otros",
        "otros": "otros",
    }

    def _concepto_de_pedido(self, pedido):
        """Tipología de coste de un pedido de compra: primero nuestro campo
        propio; si no, el tipo de pedido de la casa; por defecto «otros»."""
        propio = getattr(pedido, "tipo_coste_produccion", False)
        if propio:
            return propio
        tipo = getattr(pedido, "aunna_purchase_order_type_id", False)
        if tipo and tipo.name:
            return self.MAPEO_TIPO_PEDIDO.get(tipo.name.strip().lower(), "otros")
        return "otros"

    def _concepto_de_factura(self, linea):
        """Tipología de una línea de factura de proveedor: el «Tipo de coste
        (producción)» de la propia factura si se informó; si no, el del pedido
        de compra de origen; si no hay pedido, «otros»."""
        move = linea.move_id
        propio = getattr(move, "tipo_coste_produccion", False)
        # el abono de una factura sin pedido hereda la tipología de la factura
        if not propio and getattr(move, "reversed_entry_id", False):
            propio = getattr(move.reversed_entry_id, "tipo_coste_produccion", False)
        if propio:
            return propio
        if linea.purchase_line_id:
            return self._concepto_de_pedido(linea.purchase_line_id.order_id)
        return "otros"

    def _factura_ya_contada_por_recepcion(self, linea, project, cuenta, hay_stock):
        """True si la línea de factura es de un BIEN comprado por pedido CUYA
        RECEPCIÓN SE ATRIBUYE A ESTE PROYECTO: entonces el coste lo pone (o lo
        pondrá) la recepción del albarán y contarla otra vez sería duplicar.

        Si la recepción NO es atribuible al proyecto (pedido sin analítica y
        albarán sin proyecto: el contable pone la analítica en la factura, caso
        habitual), la factura ES la única fuente y cuenta. Los servicios no
        tienen albarán. Los «dropship» (proveedor→cliente sin pasar por nuestro
        almacén) y los pedidos cuyos albaranes se cancelaron cuentan por factura."""
        pl = linea.purchase_line_id
        if not (hay_stock and pl and pl.product_id and pl.product_id.type != "service"):
            return False
        movs = pl.move_ids.filtered(lambda m: m.state != "draft")
        hechos = movs.filtered(lambda m: m.state == "done")
        if movs and not hechos and all(m.state == "cancel" for m in movs):
            return False  # todo cancelado: nunca habrá recepción
        if hechos and all(self._signo_movimiento(m) == 0 for m in hechos):
            return False  # dropship: cuenta la factura
        # ¿la recepción (hecha o futura) se atribuye a este proyecto?
        if cuenta and self._pct_distribucion(pl.analytic_distribution, cuenta.id):
            return True
        for m in hechos or movs:
            if self._pct_recepcion(m, project, cuenta):
                return True
        return False

    @staticmethod
    def _signo_movimiento(mov):
        """+1 si la mercancía ENTRA en la empresa (recepción → es coste),
        −1 si SALE (devolución al proveedor → descuenta coste), 0 si es un
        traslado interno.

        Se mira el sentido real del movimiento en vez de buscar «devoluciones»:
        así vale tanto para la devolución de una compra (sale) como para la
        devolución de una entrega (entra), que con el criterio anterior se
        sumaba como coste siendo un retorno de material. Indicación de Laura
        (14/08/2026): a las recepciones hay que restarles las devoluciones.
        """
        origen_interno = mov.location_id.usage == "internal"
        destino_interno = mov.location_dest_id.usage == "internal"
        if destino_interno and not origen_interno:
            return 1
        if origen_interno and not destino_interno:
            return -1
        return 0

    def _acumular_compras(self, project, d_ini, d_fin, reales):
        """Compras = bienes por RECEPCIÓN (− devoluciones) + servicios y
        facturas sin albarán por FACTURA de proveedor contabilizada."""
        self._acumular_recepciones(project, d_ini, d_fin, reales)
        self._acumular_facturas_proveedor(project, d_ini, d_fin, reales)

    def _acumular_recepciones(self, project, d_ini, d_fin, reales):
        """Coste de compras de BIENES = lo RECEPCIONADO menos lo DEVUELTO (no
        lo facturado), valorado al precio del pedido. El coste nace en la
        recepción; la devolución lo deshace."""
        Move = self.env.get("stock.move")
        if Move is None:
            return
        cuenta = self._cuenta_analitica(project)
        for mov in self._movimientos_compra(project, cuenta, d_ini, d_fin):
            signo = self._signo_movimiento(mov)
            if not signo:
                continue
            pct = self._pct_recepcion(mov, project, cuenta)
            if not pct:
                continue
            linea_pc = mov.purchase_line_id
            concepto = self._concepto_de_pedido(linea_pc.order_id)
            reales[(self._mes_de(mov.date), concepto)] -= (
                signo * self._importe_recepcion(mov) * pct / 100.0)

    def _movimientos_compra(self, project, cuenta, d_ini=None, d_fin=None, productos=None):
        """Movimientos hechos ligados a un pedido de compra que PUEDEN ser del
        proyecto: albarán con el proyecto, o línea de pedido con su analítica.
        Acotado por compañía del proyecto (si la tiene) para no recorrer toda
        la base en cada recálculo."""
        Move = self.env["stock.move"].sudo()
        dominio = [("state", "=", "done"), ("purchase_line_id", "!=", False)]
        dominio += self._dominio_fechas_datetime("date", d_ini, d_fin)
        if productos:
            dominio.append(("product_id", "in", list(productos)))
        if project.company_id:
            dominio.append(("company_id", "=", project.company_id.id))
        alternativas = []
        if "project_id" in self.env["stock.picking"]._fields:
            alternativas.append([("picking_id.project_id", "=", project.id)])
        if cuenta:
            alternativas.append([("purchase_line_id.analytic_distribution", "in", [cuenta.id])])
        if not alternativas:
            return Move.browse()
        if len(alternativas) == 2:
            dominio = dominio + ["|"] + alternativas[0] + alternativas[1]
        else:
            dominio = dominio + alternativas[0]
        return Move.search(dominio, order="date asc")

    def _pct_recepcion(self, mov, project, cuenta):
        """% del movimiento de compra que corresponde al proyecto, decidido por
        SU PROPIA línea de pedido (no por las demás líneas del pedido):
          * la línea lleva la analítica del proyecto → ese % (puede ser parcial);
          * la línea no lleva analítica y el albarán lleva el proyecto → 100;
          * en cualquier otro caso → 0 (no es coste de este proyecto)."""
        linea_pc = mov.purchase_line_id
        if cuenta and linea_pc.analytic_distribution:
            return self._pct_distribucion(linea_pc.analytic_distribution, cuenta.id)
        pick = mov.picking_id
        if pick and "project_id" in pick._fields and pick.project_id \
                and pick.project_id.id == project.id:
            return 100.0
        return 0.0

    def _importe_recepcion(self, mov):
        """Valor del movimiento al precio del pedido: con descuento, sin
        impuestos, en la moneda de la compañía y en la UdM del producto (lo
        mismo que Odoo usa para valorar la recepción)."""
        linea_pc = mov.purchase_line_id
        cantidad = (mov.quantity if "quantity" in mov._fields else mov.product_uom_qty) or 0.0
        if mov.product_uom and mov.product_id.uom_id and mov.product_uom != mov.product_id.uom_id:
            cantidad = mov.product_uom._compute_quantity(cantidad, mov.product_id.uom_id)
        if hasattr(linea_pc, "_get_stock_move_price_unit"):
            precio = linea_pc._get_stock_move_price_unit()
        else:
            precio = getattr(linea_pc, "price_unit_discounted", None)
            if precio is None:
                precio = linea_pc.price_unit or 0.0
        return cantidad * (precio or 0.0)

    def _lineas_factura_proveedor(self, project, d_ini, d_fin):
        cuenta = self._cuenta_analitica(project)
        if not cuenta:
            return self.env["account.move.line"]
        return self.env["account.move.line"].sudo().search(
            [
                ("move_id.state", "=", "posted"),
                ("move_id.move_type", "in", ["in_invoice", "in_refund"]),
                ("display_type", "=", "product"),
                ("analytic_distribution", "in", [cuenta.id]),
                ("date", ">=", d_ini),
                ("date", "<=", d_fin),
            ],
            order="date asc",
        )

    def _acumular_facturas_proveedor(self, project, d_ini, d_fin, reales):
        """Servicios (contratas, licencias…) y facturas sin pedido: cuentan al
        contabilizar la factura de proveedor; el abono (in_refund) resta. Las
        líneas de BIENES con pedido se saltan: ya las contó la recepción."""
        cuenta = self._cuenta_analitica(project)
        if not cuenta:
            return
        hay_stock = self.env.get("stock.move") is not None
        for lin in self._lineas_factura_proveedor(project, d_ini, d_fin):
            if self._factura_ya_contada_por_recepcion(lin, project, cuenta, hay_stock):
                continue
            pct = self._pct_distribucion(lin.analytic_distribution, cuenta.id)
            if not pct:
                continue
            concepto = self._concepto_de_factura(lin)
            # balance: en moneda de la compañía y ya con signo (factura debe +,
            # abono haber −) → el coste es −balance
            reales[(lin.date.strftime("%Y-%m"), concepto)] += -lin.balance * pct / 100.0

    @staticmethod
    def _pct_distribucion(distribucion, cuenta_id):
        """Porcentaje asignado a la cuenta en una analytic_distribution
        (las claves pueden ser '276' o compuestas '276,90')."""
        for clave, pct in (distribucion or {}).items():
            if str(cuenta_id) in str(clave).split(","):
                return pct
        return 0.0

    # ------------------------------------------------------------------
    # Fuente 3: gastos de empleado (hr.expense) -> Gastos de viaje
    # ------------------------------------------------------------------
    # Desde que se aprueba, el gasto cuenta y SIGUE contando aunque después se
    # contabilice o se pague (antes 'posted'/'in_payment' se escapaban y el
    # importe desaparecía al contabilizar — detectado por Laura el 13/08/2026).
    ESTADOS_GASTO = ("approved", "posted", "in_payment", "paid", "done")

    # Categorías de gasto que son «Gastos de viaje» (Laura, 18/08/2026): las
    # referencias ALLO (Dietas), MIL (Kilometraje) y TRANS & ACC (Viaje y
    # alojamiento). El resto (comidas, regalos, comunicación, gastos generales…)
    # va a «Otros costes». Se mira primero la referencia interna del producto y,
    # por si la referencia cambiara, también el nombre en español/inglés.
    CODIGOS_VIAJE = ("ALLO", "MIL", "TRANS & ACC", "TRANS&ACC")
    NOMBRES_VIAJE = ("dietas", "dieta", "kilometraje", "mileage",
                     "viaje y alojamiento", "travel & accommodation",
                     "travel and accommodation", "per diem")

    def _es_gasto_de_viaje(self, gasto):
        producto = gasto.product_id
        if not producto:
            return False
        codigo = (producto.default_code or "").strip().upper()
        if codigo in self.CODIGOS_VIAJE:
            return True
        # por nombre solo si coincide EXACTO (evitar "Phone allowance" → viaje)
        nombre = (producto.name or "").strip().lower()
        return nombre in self.NOMBRES_VIAJE

    @staticmethod
    def _importe_gasto(gasto):
        """Importe del gasto SIN IVA en moneda de la compañía: el mismo criterio
        que el informe de Pablo (untaxed) y que el resto de costes del motor
        (facturas y pedidos van sin impuestos). Decisión de Verónica 18/08/2026:
        ceñirse al cálculo que a Laura le cuadra al céntimo."""
        for campo in ("untaxed_amount", "total_amount", "price_total"):
            if campo in gasto._fields:
                return gasto[campo] or 0.0
        return 0.0

    def _acumular_gastos(self, project, d_ini, d_fin, reales):
        Gasto = self.env.get("hr.expense")
        if Gasto is None:
            return
        cuenta = self._cuenta_analitica(project)
        if not cuenta:
            return
        dominio = [
            ("state", "in", list(self.ESTADOS_GASTO)),
            ("analytic_distribution", "in", [cuenta.id]),
            ("date", ">=", d_ini),
            ("date", "<=", d_fin),
        ]
        if project.company_id:
            dominio.append(("company_id", "=", project.company_id.id))
        gastos = Gasto.sudo().search(dominio)
        for g in gastos:
            pct = self._pct_distribucion(g.analytic_distribution, cuenta.id)
            if not pct:
                continue
            concepto = "viajes" if self._es_gasto_de_viaje(g) else "otros"
            reales[(g.date.strftime("%Y-%m"), concepto)] -= self._importe_gasto(g) * pct / 100.0

    # ------------------------------------------------------------------
    # Fuente 4: entregas de almacén (material servido al proyecto)
    # ------------------------------------------------------------------
    def _acumular_almacen(self, project, d_ini, d_fin, reales):
        Picking = self.env.get("stock.picking")
        if Picking is None or "project_id" not in Picking._fields:
            return
        pickings = Picking.sudo().search(
            [
                ("project_id", "=", project.id),
                ("state", "=", "done"),
            ] + self._dominio_fechas_datetime("date_done", d_ini, d_fin)
        )
        for pick in pickings:
            mes = self._mes_de(pick.date_done)
            for mov in pick.move_ids.filtered(lambda m: m.state == "done"):
                # Los movimientos ligados a un pedido de compra ya los valora
                # _acumular_compras al precio del pedido: contarlos aquí otra vez
                # (a coste estándar) duplicaría el coste.
                if mov.purchase_line_id:
                    continue
                sentido = self._sentido_entrega(mov)
                if not sentido:
                    continue
                # sale hacia el proyecto → coste; vuelve del proyecto → lo resta
                reales[(mes, "materiales")] -= sentido * self._valor_movimiento(mov, project)

    def posibles_duplicados_almacen(self, project, d_ini, d_fin):
        """Opción A acordada con Laura (18/08/2026): AVISAR, no decidir.

        La operativa de la casa es: si un producto se compró contra el proyecto
        (su recepción ya cargó el coste), la entrega posterior desde el almacén
        NO lleva el proyecto, para no cargarlo dos veces. Aquí se detecta el
        despiste: entregas desde almacén CON proyecto de un producto que también
        se recepcionó contra ese mismo proyecto. No toca cifras: devuelve la
        lista para que una persona decida (quitar el proyecto de la entrega, o
        dejarlo si de verdad es un consumo adicional)."""
        Picking = self.env.get("stock.picking")
        Move = self.env.get("stock.move")
        if Picking is None or Move is None or "project_id" not in Picking._fields:
            return []
        cuenta = self._cuenta_analitica(project)
        entregas = []
        for pick in Picking.sudo().search([
            ("project_id", "=", project.id), ("state", "=", "done"),
        ] + self._dominio_fechas_datetime("date_done", d_ini, d_fin)):
            for mov in pick.move_ids.filtered(lambda m: m.state == "done"):
                if mov.purchase_line_id or self._sentido_entrega(mov) <= 0:
                    continue
                entregas.append((pick, mov))
        if not entregas:
            return []
        productos = {mov.product_id.id for _p, mov in entregas}
        # recepciones contra el proyecto de esos mismos productos (sin acotar
        # fecha: la compra pudo ser meses antes)
        comprados = {}  # product_id -> [(pedido, cantidad)]
        for mov in self._movimientos_compra(project, cuenta, productos=productos):
            if self._signo_movimiento(mov) <= 0 or not self._pct_recepcion(mov, project, cuenta):
                continue
            linea_pc = mov.purchase_line_id
            cant = (mov.quantity if "quantity" in mov._fields else mov.product_uom_qty) or 0.0
            comprados.setdefault(mov.product_id.id, []).append((linea_pc.order_id.name, cant))
        avisos = []
        for pick, mov in entregas:
            if mov.product_id.id not in comprados:
                continue
            cant = (mov.quantity if "quantity" in mov._fields else mov.product_uom_qty) or 0.0
            pedidos = sorted({p for p, _c in comprados[mov.product_id.id]})
            avisos.append({
                "fecha": pick.date_done.date(),
                "albaran": pick.name or "",
                "picking_id": pick.id,
                "move_id": mov.id,
                "producto": mov.product_id.display_name or "",
                "cantidad": cant,
                "importe": -self._valor_movimiento(mov, project),
                "pedidos": ", ".join(pedidos),
                "comprado": sum(c for _p, c in comprados[mov.product_id.id]),
            })
        return avisos

    def _sentido_entrega(self, mov):
        """+1 si el material SALE del almacén hacia el proyecto (coste), −1 si
        es el RETORNO de una entrega anterior (vuelve al almacén: resta), 0 en
        cualquier otro caso (p. ej. una entrada que no es retorno de nada: no
        se puede saber si es coste de este proyecto y no se cuenta)."""
        signo = self._signo_movimiento(mov)
        if signo < 0:
            return 1
        if signo > 0 and mov.origin_returned_move_id                 and self._signo_movimiento(mov.origin_returned_move_id) < 0:
            return -1
        return 0

    @staticmethod
    def _valor_movimiento(mov, project):
        """Valor del movimiento a coste estándar de la compañía del proyecto
        (cantidad en la UdM del producto)."""
        cantidad = (mov.quantity if "quantity" in mov._fields else mov.product_uom_qty) or 0.0
        if mov.product_uom and mov.product_id.uom_id and mov.product_uom != mov.product_id.uom_id:
            cantidad = mov.product_uom._compute_quantity(cantidad, mov.product_id.uom_id)
        producto = mov.product_id.with_company(project.company_id)
        return cantidad * (producto.standard_price or 0.0)

    # ------------------------------------------------------------------
    # Fuente 5: facturación de cliente (para WIP; no es una línea del plan)
    # ------------------------------------------------------------------
    def facturacion_por_mes(self, project, d_ini=None, d_fin=None):
        """{ 'YYYY-MM': importe facturado } de facturas de cliente posteadas."""
        cuenta = self._cuenta_analitica(project)
        if not cuenta:
            return {}
        dominio = [
            ("move_id.state", "=", "posted"),
            ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
            ("display_type", "=", "product"),
            ("analytic_distribution", "in", [cuenta.id]),
        ]
        if d_ini:
            dominio.append(("date", ">=", d_ini))
        if d_fin:
            dominio.append(("date", "<=", d_fin))
        lineas = self.env["account.move.line"].sudo().search(dominio)
        por_mes = defaultdict(float)
        for lin in lineas:
            pct = self._pct_distribucion(lin.analytic_distribution, cuenta.id)
            if not pct:
                continue
            signo = 1 if lin.move_id.move_type == "out_invoice" else -1
            por_mes[lin.date.strftime("%Y-%m")] += (
                signo * lin.price_subtotal * pct / 100.0
            )
        return dict(por_mes)

    # ------------------------------------------------------------------
    # Detalle para el Excel (transparencia total de cada cifra)
    # ------------------------------------------------------------------
    def detalle_horas(self, project, d_ini, d_fin):
        """Todas las líneas de horas del periodo, marcando cuáles computan
        (validadas) y cuáles no. Para la hoja de detalle del Excel."""
        mapa_pl = self._cuentas_pl_horas(project.company_id)
        lineas = self.env["account.analytic.line"].sudo().search(
            self._dominio_horas(project, d_ini, d_fin, solo_validadas=False),
            order="date asc",
        )
        campos_plan = [
            f for f in lineas._fields if f.startswith("x_plan") and f.endswith("_id")
        ]
        con_validacion = self.horas_requieren_validacion()
        resultado = []
        for lin in lineas:
            tipo = "Internas"
            for campo in campos_plan:
                cuenta = lin[campo]
                if cuenta and cuenta.id in mapa_pl:
                    tipo = ("Externas (SCR)"
                            if mapa_pl[cuenta.id] == "horas_externas" else "Internas")
                    break
            validada = bool(lin.validated) if con_validacion else True
            resultado.append({
                "fecha": lin.date,
                "empleado": lin.employee_id.name or "",
                "descripcion": lin.name or "",
                "horas": lin.unit_amount,
                "coste": lin.amount,
                "tipo": tipo,
                "validada": validada,
                "computa": validada,
            })
        return resultado

    def detalle_compras(self, project, d_ini, d_fin):
        """Todo lo que no son horas, documento a documento, con la marca
        «computa»: recepciones/devoluciones de compra (bienes), facturas de
        proveedor (servicios y sin pedido computan; las de bienes con pedido
        se muestran en gris porque ya las contó su recepción), gastos de
        empleado y entregas de almacén."""
        cuenta = self._cuenta_analitica(project)
        if not cuenta:
            return []
        etiquetas = dict(TIPOS_COMPRA)
        resultado = []

        # recepciones y devoluciones de compra (bienes)
        Move = self.env.get("stock.move")
        hay_stock = Move is not None
        if hay_stock:
            for mov in self._movimientos_compra(project, cuenta, d_ini, d_fin):
                signo = self._signo_movimiento(mov)
                if not signo:
                    continue
                pct = self._pct_recepcion(mov, project, cuenta)
                if not pct:
                    continue
                linea_pc = mov.purchase_line_id
                importe = self._importe_recepcion(mov) * pct / 100.0
                tipo = self._concepto_de_pedido(linea_pc.order_id)
                resultado.append({
                    "fecha": mov.date.date(),
                    "origen": "Recepción de compra" if signo > 0 else "Devolución a proveedor",
                    "documento": (mov.picking_id.name if mov.picking_id else "") or "",
                    "tercero": linea_pc.order_id.partner_id.name or "",
                    "referencia": linea_pc.order_id.name or "",
                    "descripcion": mov.product_id.display_name or "",
                    "tipo": etiquetas.get(tipo, tipo),
                    "importe": -signo * importe,
                    "computa": True,
                })

        # facturas de proveedor
        for lin in self._lineas_factura_proveedor(project, d_ini, d_fin):
            pct = self._pct_distribucion(lin.analytic_distribution, cuenta.id)
            if not pct:
                continue
            tipo = self._concepto_de_factura(lin)
            ya_contada = self._factura_ya_contada_por_recepcion(lin, project, cuenta, hay_stock)
            resultado.append({
                "fecha": lin.date,
                "origen": "Factura proveedor" + (" (bien: contado en la recepción)" if ya_contada else ""),
                "documento": lin.move_id.name or "",
                "tercero": lin.move_id.partner_id.name or "",
                "referencia": lin.purchase_line_id.order_id.name
                if lin.purchase_line_id else "",
                "descripcion": lin.name or "",
                "tipo": etiquetas.get(tipo, tipo),
                "importe": -lin.balance * pct / 100.0,
                "computa": not ya_contada,
            })

        # gastos de empleado
        Gasto = self.env.get("hr.expense")
        if Gasto is not None:
            for g in Gasto.sudo().search([
                ("state", "in", list(self.ESTADOS_GASTO)),
                ("analytic_distribution", "in", [cuenta.id]),
                ("date", ">=", d_ini), ("date", "<=", d_fin),
            ], order="date asc"):
                pct = self._pct_distribucion(g.analytic_distribution, cuenta.id)
                if not pct:
                    continue
                importe = self._importe_gasto(g)
                resultado.append({
                    "fecha": g.date,
                    "origen": "Gasto de empleado",
                    "documento": g.name or "",
                    "tercero": g.employee_id.name or "",
                    "referencia": dict(g._fields["state"].selection).get(g.state, g.state),
                    "descripcion": g.name or "",
                    "tipo": "Gastos de Viaje" if self._es_gasto_de_viaje(g) else "Otros costes",
                    "importe": -importe * pct / 100.0,
                    "computa": True,
                })

        # entregas de almacén
        Picking = self.env.get("stock.picking")
        if Picking is not None and "project_id" in Picking._fields:
            sospechosos = {(d["picking_id"], d["producto"]): d["pedidos"]
                           for d in self.posibles_duplicados_almacen(project, d_ini, d_fin)}
            for pick in Picking.sudo().search([
                ("project_id", "=", project.id), ("state", "=", "done"),
            ] + self._dominio_fechas_datetime("date_done", d_ini, d_fin), order="date_done asc"):
                for mov in pick.move_ids.filtered(lambda m: m.state == "done"):
                    if mov.purchase_line_id:
                        continue  # ya listado como recepción/devolución de compra
                    sentido = self._sentido_entrega(mov)
                    if not sentido:
                        continue
                    valor = self._valor_movimiento(mov, project)
                    if not valor:
                        continue
                    cant = mov.quantity if "quantity" in mov._fields else mov.product_uom_qty
                    aviso = sospechosos.get((pick.id, mov.product_id.display_name or ""))
                    resultado.append({
                        "fecha": pick.date_done.date(),
                        "origen": ("Entrega de almacén" if sentido > 0 else "Retorno de material al almacén")
                        + (" ⚠ posible duplicado (comprado en %s)" % aviso if aviso and sentido > 0 else ""),
                        "documento": pick.name or "",
                        "tercero": pick.partner_id.name or "",
                        "referencia": "%.2f x %.2f €" % (
                            cant or 0.0,
                            mov.product_id.with_company(project.company_id).standard_price or 0.0),
                        "descripcion": mov.product_id.display_name or "",
                        "tipo": "Materiales",
                        "importe": -sentido * valor,
                        "computa": True,
                    })
        resultado.sort(key=lambda x: x["fecha"])
        return resultado

    # ------------------------------------------------------------------
    # Persistencia en el plan (rellena importe_real, reservado para esto)
    # ------------------------------------------------------------------
    def _escribir_en_plan(self, project, d_ini, d_fin, reales):
        lineas = self.env["produccion.plan.linea"].sudo().search(
            [
                ("project_id", "=", project.id),
                ("fecha_mes", ">=", d_ini),
                ("fecha_mes", "<=", d_fin),
            ]
        )
        por_clave = {
            (l.fecha_mes.strftime("%Y-%m"), l.concepto): l for l in lineas
        }
        vistos = set()
        for clave, importe in reales.items():
            linea = por_clave.get(clave)
            vistos.add(clave)
            if linea:
                if abs(linea.importe_real - importe) > 0.004:
                    linea.with_context(sin_recalculo=True).write(
                        {"importe_real": importe}
                    )
            else:
                mes, concepto = clave
                if concepto == "ingreso":
                    continue
                self.env["produccion.plan.linea"].sudo().with_context(
                    sin_recalculo=True, permitir_meses_pasados=PERMISO_MESES_CERRADOS
                ).create(
                    {
                        "project_id": project.id,
                        "fecha_mes": fields.Date.to_date(mes + "-01"),
                        "concepto": concepto,
                        "importe_previsto": 0.0,
                        "importe_real": importe,
                    }
                )
        # limpiar reales que ya no existen en las fuentes (p. ej. factura anulada)
        for clave, linea in por_clave.items():
            if clave not in vistos and linea.concepto != "ingreso" and linea.importe_real:
                linea.with_context(sin_recalculo=True).write({"importe_real": 0.0})
