# 08 · Incidencias conocidas y soluciones

## 1) ReportLab / stock_barcode — `No module named 'rlPyCairo'`
Síntoma: `ModuleNotFoundError: rlPyCairo`, `RenderPMError`, `_rl_renderPM`. `stock_barcode`
genera PNG y ReportLab necesita backend de render.
```bash
cd /tmp
sudo apt-get update
sudo apt-get install -y build-essential pkg-config libcairo2-dev python3.12-dev
sudo -u odoo19 /opt/odoo19/venv/bin/pip install pycairo rlPyCairo
sudo -u odoo19 /opt/odoo19/venv/bin/python3 - <<'PY'
import cairo, rlPyCairo
from reportlab.graphics import renderPM
print("OK")
PY
sudo systemctl restart odoo19    # ⚠️ reinicia PRO
```

## 2) `aunna_public_holiday_timesheet_bridge` — lentitud con empleados
Síntoma: lentitud al abrir/crear empleados; logs repetitivos `skip_no_hours`,
`skip_no_user`, `skip_manual`. Probable procesamiento masivo al interactuar con
`hr.employee`.
**A revisar:** `create` / `write` / `onchange` / campos computados / server actions /
crons / vistas de `hr.employee`.
**Recomendado:** limitar al empleado/rango afectado, evitar lógica masiva en create/write,
mover a cron/wizard/botón, reducir logs INFO.
> Módulos de contexto: `hr_employee_calendar_planning`, `hr_holidays_public`,
> `calendar_public_holiday`, `project_timesheet_holidays`, `hr_timesheet`.
> Dependencias: `openupgradelib` (calendar_public_holiday), `schwifty==2024.4.0`
> (base_bank_from_iban).

## 3) SMTP — fallos de envío (Outlook / SendAsDenied)
Síntoma: fallos de envío por Microsoft Outlook / `SendAsDenied`.
**Solución aplicada:** configurar Odoo para salir desde `soporte@aunnait.es` en
*Alias Desde / Filtro DESDE*. Resultado OK (Laura recibió el correo de restablecimiento).
Diagnóstico de la cola de correo: consulta SQL en
[02-operativa-comandos.md](02-operativa-comandos.md).

## 4) Websocket / presencia
PRO debería tener `proxy_mode=True`, `workers=4`, `gevent_port=8072` y Nginx enrutando
`/websocket` → `127.0.0.1:8072`. Comandos de diagnóstico en
[02-operativa-comandos.md](02-operativa-comandos.md).

## 5) Odoo 18 Community — assets / partner_autocomplete
Causa: módulos de Odoo 19 dentro del `addons_path` de Odoo 18.
Solución: **mover los módulos v19 fuera** del addons path de Odoo 18.
