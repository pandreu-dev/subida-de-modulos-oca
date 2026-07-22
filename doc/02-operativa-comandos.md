# 02 · Operativa y comandos del día a día

> Empezar siempre con `cd /tmp`. En `psql`, usar `PAGER=cat`.

## Estado de servicios
```bash
sudo systemctl status odoo19 --no-pager -l          # PRO
sudo systemctl status odoo19_pruebas --no-pager -l  # PRE
```

## Logs
```bash
sudo tail -n 120 /var/log/odoo19/odoo.log           # PRO
sudo tail -n 120 /var/log/odoo19_pruebas/odoo.log   # PRE
sudo tail -f /var/log/odoo19/odoo.log               # en vivo (salir: CTRL+C)
```

## Buscar errores recientes
```bash
sudo grep -RInE "ERROR|Traceback|ValidationError|Exception" /var/log/odoo19/odoo.log | tail -n 80
```

## Reiniciar / parar / arrancar
> ⚠️ **Para/reinicia Odoo** → corta el servicio a los usuarios. Avisar.
```bash
# PRO
sudo systemctl restart odoo19
sudo systemctl stop odoo19
sudo systemctl start odoo19
# PRE
sudo systemctl restart odoo19_pruebas
```

## Comprobar web local
```bash
curl -I --max-time 20 http://127.0.0.1:8071/ || true   # PRO
curl -I --max-time 20 http://127.0.0.1:8074/ || true   # PRE
```

## PostgreSQL sin paginador
```bash
sudo -u postgres env PAGER=cat psql -d grupo_zambudio_prod
```

## Consultar módulos custom instalados (por prefijo)
```bash
sudo -u postgres env PAGER=cat psql -d grupo_zambudio_prod <<'SQL'
SELECT name, state, latest_version
FROM ir_module_module
WHERE name ILIKE 'aunna%'
   OR name ILIKE 'zambudio%'
   OR name ILIKE 'project_delivery%'
   OR name ILIKE 'instalador%'
ORDER BY name;
SQL
```
> Cambiar la BD a `grupo_zambudio_prod_pruebas` para consultar PRE.

## Diagnóstico websocket / presencia (PRO)
```bash
sudo grep -nE "^(workers|gevent_port|longpolling_port|proxy_mode|http_port|http_interface)" /etc/odoo19.conf || true
sudo ss -ltnp | grep -E ':8071|:8072' || true
sudo nginx -T 2>/dev/null | grep -nE "server_name erp\.zambudio\.es|websocket|8071|8072|Upgrade|Connection|proxy_pass" -C 5 || true
curl -I --max-time 15 http://127.0.0.1:8072/websocket?version=19.0-2 || true
curl -I --max-time 15 https://erp.zambudio.es/websocket?version=19.0-2 || true
```

## Ver cola de correos (diagnóstico SMTP)
```bash
sudo -u postgres env PAGER=cat psql -d grupo_zambudio_prod -c "
SELECT m.id, m.create_date, m.state, m.email_to, msg.email_from,
       LEFT(msg.subject,120) AS subject,
       LEFT(COALESCE(m.failure_reason,''),250) AS failure_reason
FROM mail_mail m
LEFT JOIN mail_message msg ON msg.id = m.mail_message_id
ORDER BY m.create_date DESC
LIMIT 30;"
```
