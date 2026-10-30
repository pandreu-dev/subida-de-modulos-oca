# Producción — Seguimiento económico

Módulo de AUNNA IT para Odoo 19 (Enterprise/Community). Completa la pestaña
**Producción** (previsión) con los **datos reales** del proyecto y presenta ambos
en una pestaña **Seguimiento económico** con el código de colores del BR corporativo.

## Qué aporta

| Bloque | Contenido |
|---|---|
| **Avance** | Ingreso reconocido mensual, confirmable por el gestor. El sistema sugiere dos valores: la previsión propia del proyecto y la curva lineal por días (presupuesto × días transcurridos ÷ días del periodo). |
| **Costes reales** | Calculados en vivo desde las fuentes nativas: partes de horas **validados** (internas/externas según la dimensión analítica P&L); compras de **bienes** por recepción del pedido menos devoluciones al proveedor (al precio del pedido); **servicios** y facturas sin pedido por factura de proveedor contabilizada (el abono resta; la factura de un bien ya recibido no se cuenta dos veces); gastos de empleado; material servido desde almacén al proyecto (su retorno resta). Clasificación por el «Tipo de coste (producción)» del pedido de compra o de la factura. |
| **PM (Rentabilidad)** | PM = Avance − Costes · %PM · %PM acumulado. |
| **Facturación y WIP** | Facturas de cliente posteadas · WIP = avance acumulado − facturado acumulado. |

## La pestaña Seguimiento económico

- Colores idénticos al BR corporativo: **cian** = mes cerrado (dato real),
  **cian vivo** = mes de cierre en curso, **morado** = previsión futura,
  **morado oscuro** = agregados Q / H / FY.
- **Una sola cifra por celda** (real si el mes pasó, prevista si no) — el color
  indica cuál es. El detalle previsto/real/desviación aparece al pasar el ratón.
- **Clic en una celda** de coste o facturación → los apuntes de origen.
- Toggle «Ver desviaciones» y filtro por año / periodo completo.
- **Chip de frescura**: verde si está al día; ámbar si hay imputaciones
  posteriores al último recálculo (nunca un dato silenciosamente obsoleto).

## Recalculo

- Cron diario (mes en curso + 2 anteriores) y repaso completo el día 1 de cada mes.
- Botón **Recalcular datos reales** en la pestaña (grupo «Producción: confirmar
  avance y recalcular», implícito en Project/Administrator).

## Exportación

Botón **Exportar Excel (formato BR)**: genera el libro con la paleta y estructura
del BR (columnas Ene..FY coloreadas, grupos Avance/Costes/PM/WIP), todo el
periodo o el año filtrado.

## Integraciones automáticas (sin dependencia dura)

- `zambudio_project_tcv`: si está instalado, el TCV es el de la **ficha del
  proyecto** (`tcv_amount`); si no, el campo manual de la pestaña Producción. La
  fuente en uso se muestra siempre. Si el TCV de la ficha cambia, el reparto del
  ingreso se rehace solo (y si no cabe, avisa sin bloquear).
- El Tipo de proyecto (`zambudio_project_type`) y la Fecha planificada
  (`date_start`/`date`) de la ficha mandan sobre las pestañas.
- «Puerta de atrás» controlada (módulo base): asistente de carga inicial /
  corrección de meses cerrados, por grupo y con registro de auditoría.
- Dimensión P&L («Horas internas»/«Horas externas»): si una compañía no la tiene,
  las horas cuentan como internas (comportamiento documentado).

## Instalación

1. Copiar la carpeta `aunna_produccion_real_borrar` al directorio de addons.
2. Con el servicio parado: `odoo-bin -d <bd> -i aunna_produccion_real_borrar --stop-after-init`
3. Arrancar el servicio. En cada proyecto: pestaña Producción → «Generar
   planificación» (si no existía) → pestaña Seguimiento económico → «Recalcular datos
   reales».

**Desinstalación**: limpia. El módulo solo añade modelos y campos propios; no
modifica datos de otros módulos.

## Verificación

Las fórmulas y fuentes fueron validadas al céntimo contra el sistema anterior
(«Informe operativo financiero») sobre datos reales de producción el 11/08/2026:
facturación, horas internas/externas por dimensión P&L, PM y WIP exactos en
todos los puntos comprobados (2 proyectos, ~20 valores).
