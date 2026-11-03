# Costes reales del mes en curso

Módulo: `zambudio_produccion_real_new_version`. Versión: `19.0.3.0.0` (03/11/2026).

## Petición de Laura

En **Proyecto → Seguimiento económico**, el mes abierto debe mostrar los costes
reales que se van generando y distinguirse visualmente de los meses pasados y
futuros. El código usa la fecha actual de Odoo; no fija ningún mes.

## Diagnóstico sobre el original

El original ya devolvía el estado `actual` para el mes en curso y mantenía su
ingreso como previsión, pero leía los costes de `importe_real` de las líneas del
plan, que solo se renuevan con el cron diario o el botón de recálculo. La columna
era cian, casi igual a los meses cerrados.

## Comportamiento

| Periodo | Costes mostrados | Ingreso mostrado | Color |
|---|---|---|---|
| Pasado | Real del último recálculo guardado | Avance mensual (confirmado si lo está) | Cian |
| Mes en curso | Real consultado desde el día 1 hasta hoy | Previsión vigente, sin confirmar | Azul intenso, «En curso» |
| Futuro | Previsión | Previsión | Morado |

La tabla consulta los costes al cargarse, al cambiar el filtro de año y al pulsar
**Actualizar tabla**; no es una actualización continua. El Excel usa el mismo
endpoint. PM, %PM y agregados usan estos costes; WIP mantiene su fórmula.

Se reutilizan las cuatro fuentes existentes (horas, compras, gastos de empleado y
entregas de almacén) con sus condiciones: horas validadas cuando existe ese
circuito, facturas de proveedor contabilizadas, recepciones realizadas y
devoluciones. Los apuntes fechados después de hoy no cuentan. Si un concepto con
costes reales no tiene línea de previsión, el coste se muestra igualmente; si se
anula una imputación, la consulta devuelve el importe actualizado, incluido cero.

La lectura del mes en curso no guarda el plan, no confirma avances y no cambia la
fecha del último recálculo. El aviso **Plan guardado pendiente de recálculo** se
refiere a los datos guardados y puede seguir visible.

Sin fechas, o con fechas invertidas: la pestaña Seguimiento económico muestra el
aviso de planificación incompleta, no sincroniza el TCV ni consulta costes, y en
ambas pestañas se ocultan los botones que requieren fechas. El cron diario
«Producción: recálculo de datos reales» salta ese proyecto y lo anota en el log;
en el original, un solo proyecto planificado sin fechas hacía fallar la pasada
entera (se deshacía el recálculo de todos) y Odoo acababa desactivando el cron.

## Alcance técnico

- `models/produccion_real.py`: `_costes_por_periodo` lee las cuatro fuentes y lo
  comparten el recálculo guardado y la consulta del mes en curso;
  `_dominio_fechas_datetime` convierte días locales completos a UTC con límite
  final exclusivo (respeta el cambio de horario). Se usa en recepciones, entregas
  de almacén, avisos de posible doble coste y detalle Excel.
- `models/project.py` (`get_produccion_br_data`): el mes en curso usa esa lectura
  hasta hoy; pasado y futuro conservan el criterio original. Si el año filtrado no
  contiene el mes actual, no se consulta. Devuelve `aviso_planificacion` cuando
  faltan fechas.
- Widget OWL (`produccion_br_view`), plantilla y SCSS: cabecera `#2563EB` con
  texto blanco, celdas `#DBEAFE`, etiqueta «En curso», explicación del acumulado y
  botón **Actualizar tabla**.
- `wizard/exportar_br.py`: mismos datos y colores; el ingreso del mes en curso
  figura como previsto, no como real, en la hoja «Previsto vs Real».
- Vistas: aviso y botones ocultos sin fechas válidas en las pestañas Producción y
  Seguimiento económico.
- `cron_recalcular_produccion_real`: salta los proyectos sin fechas válidas.
- Manifests: `excludes` con el módulo original equivalente. Odoo rechaza instalar
  esta versión en una base donde estén los originales (p. ej. PRE), en lugar de
  romper el registro por modelos y widget duplicados.

## Pruebas

ORM (`tests/test_mes_actual.py`, se ejecutan con `--test-enable`):
imputación nueva/modificada/borrada sin recálculo, pasado/futuro y horas sin
validar, cambio de mes, filtro de año, límites UTC y cambio horario, proyecto sin
fechas (sin error ni consulta), sin fechas con líneas (no reparte TCV), cron que
salta un proyecto sin fechas y sigue con los demás, una sola pestaña de cada con
sus nombres originales, y Excel con el mes en curso en azul.

```bash
odoo-bin ... --test-enable --test-tags '/zambudio_produccion_real_new_version:TestSeguimientoMesActual'
```

Se conservan sin cambios los tests del original (`tests/test_motor.py` y
`test_tcv_y_carga.py`), que asumen un entorno concreto: `test_motor` necesita
`stock` y `purchase_stock`, y con `zambudio_project_tcv` instalado varios casos de
`test_tcv_y_carga` fallan porque pasan `tcv_amount` (calculado) en el `create`.
No afectan a la instalación ni al funcionamiento.

Locales sin Odoo, desde la carpeta del módulo:

```powershell
py -3 -B tests/check_mes_actual.py
py -3 -B tests/check_br_view.py --owl "RUTA_LOCAL_A_owl.js"
```

El primero ejecuta los métodos reales con registros simulados (11 pruebas, incluidas
la carga de `project.py` completo para detectar imports ausentes y el cron que salta
un proyecto sin fechas). El segundo monta
el widget con OWL de Odoo 19 en Chrome (Playwright) y comprueba colores, etiqueta,
costes, tooltips, navegación, actualización y el aviso sin fechas.

## Historia

- 19.0.1.x: copia de desarrollo independiente con los cambios aplicados al código
  original (no instalable junto a los originales).
- 19.0.2.x: ampliación que dependía de los originales y añadía páginas propias
  «(new_version)» para comparar en PRE.
- 19.0.3.0.0: versión autónoma para PRO. Código original con los cambios del mes
  en curso y las correcciones de la 2.x (proyecto sin fechas). Sin páginas
  duplicadas ni etiquetas «(new_version)».
