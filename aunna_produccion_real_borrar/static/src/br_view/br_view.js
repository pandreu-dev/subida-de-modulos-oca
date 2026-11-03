/** @odoo-module **/
/* Tabla Business Review: real (pasado, cian) + previsión (futuro, morado),
 * con agregados Q/H/FY, PM, WIP, tooltips y drill-down. */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";

const MESES = {
    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
    "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic",
};
const TRIMESTRE = { "03": "Q1", "06": "Q2", "09": "Q3", "12": "Q4" };

export class ProduccionBRView extends Component {
    static template = "aunna_produccion_real_borrar.BRView";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            data: null,
            anio: null,
            verDesviaciones: false,
            verAgregados: true,
            cargando: true,
        });
        onWillStart(() => this.cargar());
        // recargar solo si cambia el proyecto abierto (no en cada tecleo del formulario)
        onWillUpdateProps((next) => {
            if (next.record && next.record.resId !== this.props.record.resId) {
                return this.cargar();
            }
        });
    }

    get projectId() {
        return this.props.record.resId;
    }

    async cargar() {
        if (!this.projectId) {
            this.state.cargando = false;
            return;
        }
        this.state.cargando = true;
        this.state.data = await this.orm.call(
            "project.project", "get_produccion_br_data", [[this.projectId]],
            { anio: this.state.anio }
        );
        this.state.cargando = false;
    }

    get anios() {
        const d = this.state.data;
        if (!d) {
            return [];
        }
        return [...new Set(d.meses.map((m) => m.slice(0, 4)))];
    }

    esAnioActivo(a) {
        return this.state.anio && String(this.state.anio) === String(a);
    }

    /** Columnas: meses + agregados Q/H/FY intercalados como en la plantilla BR. */
    get columnas() {
        const d = this.state.data;
        if (!d) {
            return [];
        }
        const cols = [];
        for (const clave of d.meses) {
            const mm = clave.slice(5, 7);
            cols.push({ tipo: "mes", clave, etiqueta: MESES[mm] + " " + clave.slice(2, 4) });
            if (this.state.verAgregados && TRIMESTRE[mm]) {
                cols.push({ tipo: "agregado", clave: "Q:" + clave, etiqueta: TRIMESTRE[mm] });
                if (mm === "06") {
                    cols.push({ tipo: "agregado", clave: "H1:" + clave, etiqueta: "H1" });
                }
                if (mm === "12") {
                    cols.push({ tipo: "agregado", clave: "H2:" + clave, etiqueta: "H2" });
                    cols.push({ tipo: "agregado", clave: "FY:" + clave, etiqueta: "FY" });
                }
            }
        }
        if (this.state.verAgregados && d.meses.length) {
            cols.push({ tipo: "agregado", clave: "TOT", etiqueta: "Total" });
        }
        return cols;
    }

    /** Meses que agrega una columna Q/H/FY/TOT. */
    mesesDeAgregado(clave) {
        const d = this.state.data;
        const [tipo, hasta] = clave.split(":");
        if (clave === "TOT") {
            return d.meses;
        }
        const anio = hasta.slice(0, 4);
        const delAnio = d.meses.filter((m) => m.startsWith(anio));
        const mm = parseInt(hasta.slice(5, 7));
        if (tipo === "Q") {
            return delAnio.filter((m) => {
                const x = parseInt(m.slice(5, 7));
                return x > mm - 3 && x <= mm;
            });
        }
        if (tipo === "H1") {
            return delAnio.filter((m) => parseInt(m.slice(5, 7)) <= 6);
        }
        if (tipo === "H2") {
            return delAnio.filter((m) => parseInt(m.slice(5, 7)) > 6);
        }
        return delAnio; // FY
    }

    valorCol(fila, col) {
        if (col.tipo === "mes") {
            return this.valorMes(fila, col.clave);
        }
        return this.mesesDeAgregado(col.clave).reduce(
            (acc, m) => acc + this.valorMes(fila, m), 0
        );
    }

    valorMes(fila, mes) {
        const d = this.state.data;
        switch (fila.tipo) {
            case "avance":
                return d.avance[mes] ? d.avance[mes].valor : 0;
            case "coste":
                return fila.datos.celdas[mes] ? fila.datos.celdas[mes].valor : 0;
            case "pm":
                return d.pm[mes] || 0;
            case "fact":
                return d.facturacion[mes] || 0;
            case "wip":
                // el WIP es una foto acumulada: en agregados, el del último mes
                return d.wip[mes] || 0;
        }
        return 0;
    }

    wipCol(col) {
        const d = this.state.data;
        if (col.tipo === "mes") {
            return d.wip[col.clave] || 0;
        }
        const meses = this.mesesDeAgregado(col.clave);
        return meses.length ? d.wip[meses[meses.length - 1]] || 0 : 0;
    }

    pctPmCol(col, acumulado) {
        const d = this.state.data;
        const fuente = acumulado ? d.pct_pm_acum : d.pct_pm;
        if (col.tipo === "mes") {
            return fuente[col.clave] || 0;
        }
        const meses = this.mesesDeAgregado(col.clave);
        if (acumulado) {
            return meses.length ? fuente[meses[meses.length - 1]] || 0 : 0;
        }
        const av = meses.reduce((a, m) => a + (d.avance[m] ? d.avance[m].valor : 0), 0);
        const pm = meses.reduce((a, m) => a + (d.pm[m] || 0), 0);
        return av ? (pm / av) * 100 : 0;
    }

    desviacionMes(fila, mes) {
        const d = this.state.data;
        if (fila.tipo === "avance") {
            return d.avance[mes] ? d.avance[mes].desviacion : 0;
        }
        if (fila.tipo === "coste") {
            return fila.datos.celdas[mes] ? fila.datos.celdas[mes].desviacion : 0;
        }
        return 0;
    }

    claseCol(col) {
        const d = this.state.data;
        if (col.tipo === "agregado") {
            return "br-agregado";
        }
        const estado = d.estado_mes[col.clave];
        return "br-" + estado; // br-pasado / br-actual / br-futuro
    }

    tituloCelda(fila, col) {
        if (col.tipo !== "mes" || (fila.tipo !== "coste" && fila.tipo !== "avance")) {
            return "";
        }
        const d = this.state.data;
        const info = fila.tipo === "avance"
            ? d.avance[col.clave]
            : fila.datos.celdas[col.clave];
        if (!info) {
            return "";
        }
        const f = (v) => this.formatear(v);
        let extra = "";
        if (fila.tipo === "avance" && d.estado_mes[col.clave] !== "futuro") {
            extra = `\nCurva lineal: ${f(info.sugerido_lineal)}` +
                (info.confirmado ? "\n✓ Confirmado" : "\n(borrador)");
        }
        if (fila.tipo === "coste" && fila.datos.concepto.startsWith("horas") &&
            d.solo_horas_validadas) {
            extra += "\nSolo horas validadas por el responsable";
        }
        return `Previsto: ${f(info.previsto)}\nReal: ${f(info.real !== undefined ? info.real : info.valor)}\nDesviación: ${f(info.desviacion)}${extra}`;
    }

    formatear(v) {
        return (v || 0).toLocaleString("es-ES", {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        });
    }

    formatearPct(v) {
        return (v || 0).toLocaleString("es-ES", {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        }) + "%";
    }

    async drilldown(fila, col) {
        if (col.tipo !== "mes") {
            return;
        }
        const mes = col.clave;
        const desde = mes + "-01";
        const [anio, mm] = mes.split("-");
        const finMes = new Date(anio, parseInt(mm), 0).getDate();
        const hasta = `${mes}-${String(finMes).padStart(2, "0")}`;
        if (fila.tipo === "coste" && fila.datos.concepto.startsWith("horas")) {
            const domain = [
                ["project_id", "=", this.projectId],
                ["date", ">=", desde], ["date", "<=", hasta],
            ];
            if (this.state.data.solo_horas_validadas) {
                domain.push(["validated", "=", true]);
            }
            this.action.doAction({
                type: "ir.actions.act_window",
                name: `Partes de horas validados — ${col.etiqueta}`,
                res_model: "account.analytic.line",
                view_mode: "list",
                views: [[false, "list"]],
                domain,
            });
        } else if (fila.tipo === "coste" && fila.datos.concepto === "materiales") {
            // materiales: recepciones/devoluciones de compra y entregas de almacén
            const domain = [
                ["state", "=", "done"],
                ["date", ">=", desde], ["date", "<=", hasta],
                "|", ["picking_id.project_id", "=", this.projectId],
                "&", ["purchase_line_id", "!=", false],
                ["purchase_line_id.analytic_distribution", "in", [this.state.data.analytic_id]],
            ];
            this.action.doAction({
                type: "ir.actions.act_window",
                name: `Movimientos de material — ${col.etiqueta}`,
                res_model: "stock.move",
                view_mode: "list",
                views: [[false, "list"]],
                domain,
            });
        } else if (fila.tipo === "coste" && fila.datos.concepto === "viajes") {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: `Gastos de empleado — ${col.etiqueta}`,
                res_model: "hr.expense",
                view_mode: "list",
                views: [[false, "list"]],
                domain: [
                    ["date", ">=", desde], ["date", "<=", hasta],
                    ["analytic_distribution", "in", [this.state.data.analytic_id]],
                ],
            });
        } else if (fila.tipo === "fact" || fila.tipo === "coste") {
            const tipos = fila.tipo === "fact"
                ? ["out_invoice", "out_refund"] : ["in_invoice", "in_refund"];
            this.action.doAction({
                type: "ir.actions.act_window",
                name: `Facturas — ${col.etiqueta}`,
                res_model: "account.move.line",
                view_mode: "list",
                views: [[false, "list"]],
                domain: [
                    ["move_id.move_type", "in", tipos],
                    ["move_id.state", "=", "posted"],
                    ["date", ">=", desde], ["date", "<=", hasta],
                    ["analytic_distribution", "in", [this.state.data.analytic_id]],
                ],
            });
        }
    }

    async cambiarAnio(ev) {
        this.state.anio = ev.target.value ? parseInt(ev.target.value) : null;
        await this.cargar();
    }

    async recalcular() {
        await this.orm.call(
            "project.project", "action_recalcular_produccion_real", [[this.projectId]]
        );
        await this.cargar();
    }
}

export const produccionBRView = {
    component: ProduccionBRView,
};
registry.category("view_widgets").add("produccion_br_view", produccionBRView);
