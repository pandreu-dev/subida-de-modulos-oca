# Producción — Seguimiento económico (versión para producción)

**Módulo `zambudio_produccion_real_new_version`, versión 19.0.3.0.0.**

Versión **autónoma** del seguimiento económico de Verónica para instalar en PRO.
Son tres módulos que van juntos y sustituyen a los originales:

| Módulo de esta versión | Original equivalente |
|---|---|
| `zambudio_produccion_new_version` | `zambudio_produccion` (pestaña Producción, planificación) |
| `zambudio_produccion_real_new_version` | `zambudio_produccion_real` (pestaña Seguimiento económico) |
| `zambudio_produccion_grid_new_version` | `zambudio_produccion_grid` (cuadrícula Enterprise) |

El contenido es el código original (mismos modelos, campos, pestañas, textos y
permisos) más los cambios del mes en curso pedidos por Laura. Solo cambian el
nombre de la carpeta y el manifest. **No dependen de los originales y no deben
instalarse en la misma base que ellos**: definen los mismos modelos. En PRE se
conservan los originales de Verónica; en PRO se instala esta versión.

## Qué cambia respecto al original

- **Mes en curso abierto.** Sus costes reales se consultan desde el día 1 hasta
  hoy al abrir la pestaña o pulsar **Actualizar tabla**, sin esperar al cron
  diario ni pulsar **Recalcular datos reales**. El ingreso del mes sigue siendo
  previsión y no se confirma.
- **Color propio:** cabecera azul intenso (`#2563EB`, texto blanco), celdas azul
  claro (`#DBEAFE`) y etiqueta «En curso», en pantalla y en el Excel.
- **Límites de fecha:** recepciones y entregas de almacén se filtran por días
  locales completos convertidos a UTC; ya no se pierden los movimientos de la
  tarde del último día. Afecta también al recálculo guardado y al detalle Excel.
- **Proyecto sin fechas:** la pestaña muestra un aviso en lugar de un error y se
  ocultan los botones que necesitan fechas (generar, recalcular, importar,
  confirmar avance, exportar). Era el origen del aviso «Internal» de PRE (30/10).
  El cron diario de recálculo salta ese proyecto en vez de fallar para todos.
- **Protección:** los manifests declaran `excludes` con los originales; Odoo no
  deja instalar esta versión donde estén los de Verónica.

Detalle técnico y pruebas: [docs/mes_en_curso.md](docs/mes_en_curso.md).

## Qué aporta (igual que el original)

| Bloque | Contenido |
|---|---|
| **Avance** | Ingreso reconocido mensual, confirmable por el gestor. Sugiere la previsión propia del proyecto y la curva lineal por días. |
| **Costes reales** | Partes de horas **validados** (internas/externas según la dimensión analítica P&L); compras de **bienes** por recepción menos devoluciones (al precio del pedido); **servicios** y facturas sin pedido por factura de proveedor contabilizada; gastos de empleado; material servido desde almacén al proyecto. Clasificación por el «Tipo de coste (producción)» del pedido o la factura. |
| **PM (Rentabilidad)** | PM = Avance − Costes · %PM · %PM acumulado. |
| **Facturación y WIP** | Facturas de cliente contabilizadas · WIP = avance acumulado − facturado acumulado. |

## La pestaña Seguimiento económico

- Colores: **cian** = mes pasado (dato real guardado), **azul intenso** = mes en
  curso abierto, **morado** = previsión futura, **morado oscuro** = agregados Q/H/FY.
- Meses pasados: real del último recálculo guardado (cron diario «Producción:
  recálculo de datos reales» o botón **Recalcular datos reales**).
- Mes en curso: costes reales hasta hoy e ingreso previsto. La desviación compara
  un acumulado parcial con la previsión del mes completo.
- Meses futuros: previsión. Detalle previsto/real/desviación al pasar el ratón;
  clic en una celda de coste o facturación → apuntes de origen.
- El chip de frescura informa del último recálculo **guardado**; puede seguir
  ámbar aunque los costes del mes en curso ya estén al día en la tabla.

## Integraciones (sin dependencia dura)

- `zambudio_project_tcv`: si está instalado, el TCV es el de la ficha
  (`tcv_amount`); si no, el campo manual de la pestaña Producción.
- Tipo de proyecto (`zambudio_project_type`) y Fecha planificada
  (`date_start`/`date`) de la ficha mandan sobre las pestañas.
- Dimensión P&L («Horas internas»/«Horas externas»): si una compañía no la tiene,
  las horas cuentan como internas.

## Instalación

Instalar los tres módulos juntos (la cuadrícula se instala sola si `web_grid`
está presente). `openpyxl` es necesario para el Excel. Al instalar, el
`post_init_hook` da el grupo «Producción: carga inicial y corrección de meses
cerrados» a Laura Moreno Alonso y a Desarrollo Odoo.

`zambudio_cierre_mensual` depende del original `zambudio_produccion_real`; para
usarlo con esta versión habría que cambiar esa dependencia.
