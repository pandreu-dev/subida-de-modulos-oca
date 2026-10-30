# Costes reales del mes en curso

Fecha: 30/10/2026. Módulo: `zambudio_produccion_real_new_version`. Versión: `19.0.2.0.1`.

## Corrección 19.0.2.0.1: proyecto sin fechas

Al extraer la ampliación se omitió el import de `UserError` en `models/project.py`.
Un proyecto sin fechas disparaba esa excepción en el módulo original y el
`except UserError` de la ampliación fallaba con `NameError`, provocando RPC_ERROR.
Se recupera el import para mostrar el aviso de falta de planificación sin
generar líneas ni exigir fechas solo para abrir la pestaña. No se modifica
ningún módulo original ni las otras dos ampliaciones.

Se añade una regresión local que ejecuta el archivo completo, incluidos sus
imports: reproduce el `NameError` antes de corregirlo. El cargador simplificado
de las pruebas anteriores aportaba `UserError` y ocultaba este import ausente.
La suite local tiene ahora diez pruebas. Se añade también el caso ORM de un
proyecto nuevo sin fechas en `test_mes_actual.py`.

Validación de la corrección: **10/10 pruebas locales correctas** y **1/1 caso
ORM sin fechas correcto** en la copia neutralizada de PRE, que conserva el
nombre técnico anterior de la ampliación. Se verificaron sin cambios sus
planes, ajustes, avances, proyectos, XML IDs originales y número de crons.

## Petición de Laura y ubicación

En **Proyecto → Seguimiento económico**, el mes abierto debe mostrar los costes
reales que se van generando y distinguirse visualmente de los meses pasados y
futuros. En el ejemplo de Laura es octubre de 2026; el código utiliza la fecha
actual de Odoo y no fija octubre ni 2026.

## Diagnóstico

El código de origen ya devolvía el estado `actual` para el mes en curso y mantenía
su ingreso como previsión. Sin embargo, leía los costes de `importe_real` en las
líneas del plan: esos importes solo se renovaban mediante el botón de recálculo
o el cron. La columna actual era cian, muy parecida a los meses cerrados, y el
texto explicativo de la pestaña solo distinguía pasado y futuro.

Se reprodujo esta diferencia con datos simulados: ante un coste guardado de
−20 € y nuevas horas computables de −125 €, el endpoint original devolvía −20 €;
el modificado devuelve −125 €. Esto demuestra el comportamiento del código,
sin afirmar que se hayan auditado las imputaciones concretas de Laura en PRE.

## Comportamiento

| Periodo | Costes mostrados | Ingreso mostrado | Color |
|---|---|---|---|
| Pasado | Real del último recálculo guardado | Avance mensual según la lógica existente | Cian |
| Mes en curso | Real consultado desde el día 1 hasta hoy | Previsión vigente, sin marcar confirmado | Azul intenso, «En curso» |
| Futuro | Previsión | Previsión | Morado |

La tabla consulta los costes al cargarse, al cambiar el filtro de año y al pulsar
**Actualizar tabla**. No es una actualización continua en segundo plano. La
exportación Excel utiliza el mismo endpoint y obtiene los costes actuales al
exportar. PM, %PM y agregados utilizan estos costes; WIP mantiene su fórmula.

Se reutilizan las cuatro fuentes existentes: horas, compras, gastos de empleado
y entregas de almacén. Conservan sus condiciones de cómputo: por ejemplo, horas
validadas cuando existe ese circuito, facturas de proveedor contabilizadas,
recepciones realizadas y devoluciones. Un borrador o una hora sin validar no
empiezan a contar por este cambio. Los apuntes fechados después de hoy se excluyen
del acumulado actual, incluso dentro del mismo mes.

Si no existe línea de previsión para un concepto con costes reales, el coste se
muestra igualmente. Si desaparece o se anula una imputación computable, la nueva
consulta devuelve el importe actualizado, incluido cero; no conserva el dato
anterior como sustituto.

La desviación actual es **real acumulado − previsión del mes completo**. Es una
comparación parcial, no el resultado de un cierre. El ingreso actual aparece
como previsto en los tooltips; no se presenta como ingreso real en la hoja
«Previsto vs Real» del Excel.

## Alcance técnico

- `models/produccion_real.py`: `_costes_por_periodo` comparte la lectura de las
  cuatro fuentes entre consulta y recálculo. La consulta no escribe importes.
- `models/project.py`: el mes actual usa esa lectura hasta hoy; pasado y futuro
  conservan el criterio anterior. Si el año seleccionado no contiene el mes
  actual, no se ejecuta esa consulta adicional.
- Los filtros de fechas de recepciones/entregas convierten días locales completos
  a UTC y usan un límite final exclusivo. Así no se pierden los movimientos de
  la tarde del último día; se respeta también el cambio de horario. Este helper
  se utiliza además en el recálculo, avisos y detalle Excel de almacén para
  mantener el mismo criterio temporal. Un recálculo posterior puede incorporar
  movimientos del último día que antes quedaban excluidos.
- Vista, plantilla, JavaScript y SCSS: cabecera `#2563EB`, letras blancas y celdas
  `#DBEAFE`, etiqueta «En curso», explicación del acumulado y botón de actualización.
- `wizard/exportar_br.py`: mismos datos, colores y distinción entre ingreso
  previsto y real; se conserva el resto de hojas del libro.
- La versión 19.0.2.0.0 convierte las tres copias en ampliaciones compatibles:
  base y grid dependen de sus originales sin repetir modelos ni datos XML;
  real hereda el motor, proyecto y asistente Excel originales y añade una vista
  heredada y un widget con nombre propio. No se modifican los originales,
  otros módulos, las referencias `_borrar` ni `new/doc`.

La lectura nueva no guarda el plan, no confirma avances y no cambia la fecha del
último recálculo. El aviso **Plan guardado pendiente de recálculo** sigue referido
a los datos persistidos; puede seguir visible con el mes actual ya actualizado.
El endpoint conserva la sincronización previa del TCV que ya existía, la cual
sí puede reajustar previsiones si cambia el TCV. No se convierte todo el endpoint
en una operación de solo lectura.

## Pruebas ejecutadas

**Nueve pruebas locales de Python**, ejecutando métodos del módulo con registros
simulados; las fuentes de datos y el ORM se sustituyen por dobles de prueba:

1. Nuevas imputaciones, modificación y desaparición sin recálculo previo.
2. Las cuatro fuentes, devoluciones, conceptos sin línea y exclusión de fechas futuras.
3. Conservación del criterio de meses pasados/futuros e ingreso actual previsto.
4. Filtro de otro año y proyecto sin fechas.
5. Paso octubre → noviembre y diciembre → enero.
6. Límites UTC y días de 23/25 horas en Madrid.
7. Inclusión de movimientos de hoy por la tarde.
8. Uso de esos límites en las consultas de recepciones y almacén.
9. Generación y lectura de un XLSX real: importes, totales, colores, etiquetas e
   ingreso abierto sin dato real ficticio.

Desde la carpeta del módulo:

```powershell
py -3 -B tests/check_mes_actual.py
```

Requiere `python-dateutil`, `pytz` y `openpyxl`. Resultado: **9/9 correctas**.
Se comprobó además la diferencia −20/−125 contra el código original archivado.

**Prueba de navegador:** Chrome sin ventana, librería OWL distribuida con Odoo 19,
JS/XML/SCSS del módulo y datos/servicios simulados. Comprobados renderizado,
colores calculados, etiqueta, tooltips, ausencia de confirmación del mes abierto,
desviaciones, dominio de navegación de material y actualización de costes/PM.
Resultado: correcto, sin errores JavaScript. No equivale a una sesión completa
del cliente Odoo ni a compilar los assets con su servidor.

```powershell
py -3 -B tests/check_br_view.py --owl "RUTA_LOCAL_A_owl.js"
```

Requiere Playwright y Chrome. La ruta apunta a la librería de
[Odoo 19](https://raw.githubusercontent.com/odoo/odoo/19.0/addons/web/static/lib/owl/owl.js).
El script no descarga dependencias ni accede a PRE.

También se comprobaron sintaxis Python, XML, manifest y rutas de sus recursos.

## Instalación y validación en Odoo

**Los módulos originales deben permanecer instalados.** Esta versión amplía
sus modelos mediante `_inherit`, sin volver a definirlos con `_name`, y conserva
sus identificadores, permisos, tareas y pestañas. La cuadrícula original y
`zambudio_cierre_mensual` mantienen sus dependencias y funcionamiento.

Esto sustituye el diseño inicial de copias independientes, que no permitía
instalarlas junto a los originales. Las tres carpetas se llaman ahora
`zambudio_produccion_new_version`, `zambudio_produccion_real_new_version` y
`zambudio_produccion_grid_new_version`. Sus nombres visibles terminan también
en `_new_version`. La versión técnica del manifest es `19.0.2.0.0`.

Se ejecutaron seis pruebas ORM en una copia temporal y neutralizada de PRE:
las cinco de cálculo y fechas más una comprobación de herencia de vista,
pestañas únicas y widget propio. Resultado: **0 fallos y 0 errores**.
La instalación conservó exactamente los registros de 1.342 líneas de plan,
134 avances, 259 proyectos y sus ajustes, los XML IDs originales y el número
de tareas programadas. No se instaló la ampliación en el PRE activo.

Esa instalación se probó con los nombres anteriores a `_new_version`.
El cambio posterior de nombres conserva el comportamiento y actualiza las
dependencias, XML IDs propios, assets, widget y referencias de las pruebas.
El log de la copia mostró una incidencia preexistente de
`aunna_portal_iframe_example` no instalable; no se modificó ese módulo.

Ejemplo para repetir las pruebas en una copia neutralizada con los originales
instalados y con un proceso/configuración propios:

```bash
/ruta/venv/bin/python /ruta/odoo/odoo-bin \
  -c /ruta/configuracion_aislada.conf -d zambudio_br_sandbox \
  -i zambudio_produccion_real_new_version --test-enable \
  --test-tags '/zambudio_produccion_real_new_version:TestSeguimientoMesActual' \
  --stop-after-init --http-interface=127.0.0.1 --http-port=8099 \
  --workers=0 --max-cron-threads=0
```

Si la ampliación ya estaba instalada **en esa base aislada**, usar `-u` en lugar
de `-i`. El comando de ejemplo utiliza rutas orientativas. Referencia:
[pruebas de Odoo 19](https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html).

Después de desplegar en el entorno de destino: abrir un proyecto
con planificación, añadir una imputación válida del mes y pulsar «Actualizar
tabla»; comprobar coste, PM, columna azul y Excel, y repetir con devolución o
anulación. Comprobar también los permisos de los usuarios que usarán la pestaña.
Las pruebas locales no garantizan por sí solas la integración con todos los
módulos y datos de la instalación destino.
