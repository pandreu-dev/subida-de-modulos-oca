"""Ampliacion del motor original: costes actuales y limites de dias locales."""
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import fields, models

TIPOS_COMPRA = [
    ("contratas_fp", "Contratas (Fix price)"),
    ("contratas_adm", "Contratas (Por administración)"),
    ("materiales", "Materiales"),
    ("viajes", "Gastos de Viaje"),
    ("licencias_software", "Licencias software"),
    ("otros", "Otros costes"),
]


class ProduccionRealMotor(models.AbstractModel):
    _inherit = 'produccion.real.motor'

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
