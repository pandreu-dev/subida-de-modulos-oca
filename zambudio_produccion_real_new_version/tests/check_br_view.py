"""Monta JS/XML/SCSS reales con OWL 2 y datos simulados, sin servidor Odoo.

Uso: python tests/check_br_view.py --owl /ruta/a/owl.js [--screenshot captura.png]
Requiere Playwright y Chrome instalado. La librería OWL debe ser la de Odoo 19:
https://raw.githubusercontent.com/odoo/odoo/19.0/addons/web/static/lib/owl/owl.js
"""
import argparse
from pathlib import Path
import re

from playwright.sync_api import sync_playwright

from check_mes_actual import Date, ROOT, TestMesActualLocal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owl", required=True)
    parser.add_argument("--screenshot")
    args = parser.parse_args()
    case = TestMesActualLocal()
    case.setUp()
    case.sources["horas"] = [(Date.today, "horas_internas", -125.0)]
    data = case.project.get_produccion_br_data_new_version()
    source = (ROOT / "static/src/br_view/br_view.js").read_text(encoding="utf-8")
    source = re.sub(r"^import .*?;\s*$", "", source, flags=re.MULTILINE)
    source = source.replace("export class ", "class ").replace("export const ", "const ")
    template = (ROOT / "static/src/br_view/br_view.xml").read_text(encoding="utf-8")
    css = (ROOT / "static/src/br_view/br_view.scss").read_text(encoding="utf-8")
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content("<html><body><main id='app'></main></body></html>")
        page.add_style_tag(content="""
            body { font-family: Arial, sans-serif; margin: 24px; color: #172334; }
            .d-flex { display: flex; } .flex-wrap { flex-wrap: wrap; }
            .align-items-center { align-items: center; } .gap-3 { gap: 14px; }
            .mb-2 { margin-bottom: 12px; } .ms-auto { margin-left: auto; }
            .small { font-size: 12px; } .text-muted { color: #637083; }
            .badge,button { padding: 6px 10px; border-radius: 4px; }
            .text-bg-warning { background: #fff0b3; }
            .form-select { padding: 6px; } .mt-1 { margin-top: 6px; }
        """ + css)
        page.add_script_tag(path=str(Path(args.owl).resolve()))
        page.evaluate("data => { window.fixture = data; window.rpcCalls = 0; window.actions = []; }", data)
        page.add_script_tag(content="""
            const { Component, onWillStart, onWillUpdateProps, useState } = owl;
            const standardWidgetProps = { record: Object };
            // Simula que el widget original ya está registrado en Odoo.
            const widgets = new Map([['produccion_br_view', {}]]);
            const registry = { category: () => ({ add: (key, value) => {
                if (widgets.has(key)) { throw new Error('Widget duplicado: ' + key); }
                widgets.set(key, value);
            } }) };
            const services = {
                orm: { call: async (model, method) => {
                    if (method !== 'get_produccion_br_data_new_version') {
                        throw new Error('RPC original utilizado: ' + method);
                    }
                    window.rpcCalls++;
                    return structuredClone(window.fixture);
                } },
                action: { doAction: action => window.actions.push(action) },
            };
            const useService = name => services[name];
        """ + source + "\nwindow.TestBR = ProduccionBRView;")
        page.evaluate("""async templates => {
            window.app = new owl.App(window.TestBR, {
                templates, props: { record: { resId: 1 } },
            });
            window.component = await window.app.mount(document.getElementById('app'));
        }""", template)
        page.locator("th.br-actual").wait_for()
        assert page.locator("th.br-actual").inner_text() == "Oct 26 · En curso"
        assert page.locator("th.br-actual").evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(37, 99, 235)"
        assert page.locator("th.br-actual").evaluate("el => getComputedStyle(el).color") == "rgb(255, 255, 255)"
        cost_row = page.locator("tr").filter(has=page.locator("td.br-etiqueta", has_text="Horas internas"))
        assert cost_row.locator("td.br-actual").inner_text() == "-125,00"
        assert cost_row.locator("td.br-actual").evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(219, 234, 254)"
        assert "hasta 2026-10-30" in cost_row.locator("td.br-actual").get_attribute("title")
        income = page.locator("tr").filter(has=page.locator("td.br-etiqueta", has_text=re.compile("^Avance$")))
        assert "Ingreso previsto" in income.locator("td.br-actual").get_attribute("title")
        assert income.locator("td.br-actual .br-check").count() == 0
        page.get_by_text("Ver desviaciones", exact=False).locator("input").check()
        assert cost_row.locator("td.br-actual .br-delta").inner_text() == "Δ 375,00"
        assert income.locator("td.br-actual .br-delta").count() == 0
        material = page.locator("tr").filter(has=page.locator("td.br-etiqueta", has_text=re.compile("^Materiales$")))
        material.locator("td.br-actual").click()
        domain = page.evaluate("window.actions.at(-1).domain")
        assert ["date", "<", "2026-10-30 23:00:00"] in domain
        case.sources["horas"].append((Date.today, "horas_internas", -75.0))
        page.evaluate("data => window.fixture = data", case.project.get_produccion_br_data_new_version())
        page.get_by_role("button", name="Actualizar tabla").click()
        page.wait_for_function("window.rpcCalls === 2 && !window.component.state.cargando")
        page.wait_for_function("document.querySelector('tbody tr:nth-child(4) td.br-actual').textContent.includes('-200,00')")
        assert "-200,00" in cost_row.locator("td.br-actual").inner_text()
        pm = page.locator("tr.br-fila-pm td.br-actual")
        assert pm.inner_text() == "800,00"
        if args.screenshot:
            page.screenshot(path=args.screenshot, full_page=True)
        page.evaluate("""async () => {
            window.fixture = {meses: [], aviso_planificacion: 'Faltan las fechas de planificación.'};
            await window.component.cargar();
        }""")
        page.get_by_text("Puedes consultar esta pestaña", exact=False).wait_for()
        assert page.locator("table.br-tabla").count() == 0
        assert not errors, errors
        browser.close()
    print("OK: OWL renderiza; colores, etiqueta, costes, tooltip, desviación, navegación y actualización correctos.")


if __name__ == "__main__":
    main()
