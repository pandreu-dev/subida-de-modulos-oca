# Manual de usuario — Informe operativo financiero (WIP)

Módulo: `aunna_wip_annual_report`

Este manual explica, de forma práctica: **qué es cada fila**, **cómo se usa el
informe**, **cómo conseguir que aparezcan los datos reales** y **por qué a veces sale
todo a 0** (y cómo arreglarlo). Para el detalle técnico de fórmulas, ver
[GUIA_CALCULOS.md](GUIA_CALCULOS.md).

---

## 1. Qué es este informe

Es un informe **mensual, por proyecto / cuenta analítica**, que compara lo **Previsto**
(lo que pones tú a mano) con lo **Real** (lo que sale de la contabilidad y del
proyecto), agrupado como un P&L de obra:

- **Ingresos** (Venta de servicios, Venta de productos)
- **Costes** (Horas internas, Horas externas, Pedidos, Materiales, Gastos)
- **PM** (rentabilidad y % de margen)
- **WIP** (facturación y obra en curso)

Está en el app **Proyectos → Informe operativo financiero** y en **Proyectos →
Configuración informe operativo financiero** (visible para usuarios de Contabilidad).

---

## 2. Cómo se usa (paso a paso)

1. **Proyectos → Configuración informe operativo financiero → Nuevo.**
2. Rellena: **Ejercicio**, rango **Desde / Hasta**, **Compañía** y **Proyecto** (o
   directamente **Cuenta analítica**). Si eliges proyecto, la cuenta analítica se pone
   sola.
3. Pulsa **Recalcular reales** (⚠️ importante: la columna **Real** solo se actualiza
   aquí; mira que **"Último recalculo"** no esté vacío).
4. Revisa el resultado en las pestañas:
   - **Vista horizontal**: la tabla agrupada y con colores (solo lectura).
   - **Detalle mensual**: aquí escribes la columna **Prev.** (Previsto).
   - **Notas de cálculo**: recordatorio de de dónde sale cada dato.
5. (Opcional) **Exportar Excel**.

### Botones

| Botón | Qué hace |
|---|---|
| **Recalcular reales** | Actualiza la columna **Real** desde la contabilidad y el proyecto. |
| **Ver detalle mensual** | Abre la lista de líneas mensuales (para editar Previsto). |
| **Actualizar vista horizontal** | Regenera la matriz de la vista horizontal. |
| **Exportar Excel** | Descarga la matriz en `.xlsx`. |

### Columnas Prev. / Real / Dif.

- **Prev.** = lo previsto (lo escribe el usuario en *Detalle mensual*).
- **Real** = lo que sale de la contabilidad/proyecto (se calcula al *Recalcular*).
- **Dif.** = Real − Prev.

---

## 3. Qué mide cada fila y de dónde sale

### Ingresos

| Fila | Qué es | De dónde sale |
|---|---|---|
| **Venta de servicios** | Ingreso reconocido de servicios | **Asientos WIP** (ingreso reconocido) en cuentas **705**, imputados a la analítica. **NO** incluye facturas. |
| **Venta de productos** | Ingreso reconocido de productos | Igual, resto del grupo **70** (700…). **NO** incluye facturas. |
| **Total ingresos** | Ingreso reconocido total | Suma de servicios + productos = ingreso reconocido vía **asientos WIP**. |

> El apartado azul (Ingresos) se alimenta de los **asientos WIP**, **no de las
> facturas**. Lo facturado se ve aparte, en la fila **Facturación**.

### Costes

| Fila | Qué es | De dónde sale |
|---|---|---|
| **Horas internas** | Coste de horas de personal propio | Partes de horas (apuntes analíticos) del proyecto de empleados con **Tipo empleado = Interno**. |
| **Horas externas** | Coste de horas de personal externo | Igual, con **Tipo empleado = Externo**. |
| **Pedidos** | Compras a proveedor | **Pedidos de compra confirmados** (aceptados, aunque **no** estén facturados), por su **fecha de confirmación**. En la vista horizontal se despliega en **una sub-fila por Tipo de pedido** (color más claro, plegable). |
| **Materiales** | Material consumido | Apuntes analíticos de material (movimientos de stock valorados) imputados a la analítica. |
| **Gastos** | Gastos de empleado | **Gastos** (`hr.expense`) imputados a la analítica. |
| **Total costes** | Suma de costes | Suma de las filas anteriores (en negativo). |

> Los costes salen de las **mismas fuentes que el panel de "Rentabilidad" del
> proyecto**, así que deben cuadrar con él.

### PM (rentabilidad) — se calcula solo

| Fila | Fórmula |
|---|---|
| **PM (Rentabilidad)** | Total ingresos − Total costes. |
| **%PM** | PM ÷ Total ingresos. |
| **%PM (Acumulado)** | PM acumulado ÷ Ingresos acumulados. |

### WIP

| Fila | Qué es | De dónde sale |
|---|---|---|
| **Facturación** | Lo facturado al cliente | Facturas/abonos de cliente en cuentas del grupo **70**. |
| **WIP** | Obra en curso (reconocido no facturado) | **Ingreso reconocido acumulado − Facturación acumulada.** |

**Idea clave del WIP:** los **Ingresos** (apartado azul) son el **ingreso reconocido**
(asientos WIP) y **no** incluyen las facturas. El **WIP = ingreso reconocido acumulado −
facturación acumulada**: **sube** con los asientos WIP y **baja** al facturar. Queda a
**0** cuando lo facturado alcanza lo reconocido, y **negativo** si se factura de más
(cobras por adelantado obra aún no reconocida).

---

## 4. Cómo conseguir que aparezcan los datos (requisitos)

Cada fila necesita que exista el dato **imputado a la analítica del proyecto** y **en el
periodo del informe**:

- **Venta de servicios / productos**: que haya un **asiento WIP** (Presupuesto analítico
  → *Crear asiento WIP*) o una **factura de cliente** en cuentas 70, con la analítica del
  proyecto.
- **Facturación**: **facturar** al cliente (cuentas 70) con la analítica del proyecto.
- **WIP**: se rellena solo en cuanto haya Ingresos.
- **Horas internas/externas**: que haya **partes de horas** en el proyecto **y** que los
  **empleados tengan "Tipo empleado" (Interno/Externo)** (una automatización les asigna
  la cuenta analítica "Horas internas"/"Horas externas").
- **Pedidos**: **confirmar** un pedido de compra (estado *Pedido de compra*) con la
  analítica del proyecto; **no hace falta facturarlo**. Sale con la **fecha de
  confirmación** del pedido. Si el pedido tiene **Tipo pedido**, aparece su sub-fila.
- **Materiales**: movimientos de **stock valorados** imputados a la analítica.
- **Gastos**: **gastos de empleado** (`hr.expense`) imputados a la analítica.
- **PM**: se calcula solo cuando hay Ingresos y Costes.

Y siempre: **pulsar "Recalcular reales"** después de crear/cambiar datos.

---

## 5. Por qué a veces sale TODO (o casi todo) a 0

Es lo más habitual al probar. Repasa esta lista:

1. **El informe es de un año/periodo distinto al de la actividad.**
   Ejemplo: proyecto con horas de 2025 e informe de 2026 → todo a 0. **Solución:** pon
   el **Ejercicio / rango** en el periodo donde están los datos (mira las fechas de los
   partes de horas / facturas del proyecto).

2. **No has pulsado "Recalcular reales"** (el campo *Último recalculo* está vacío) → toda
   la columna **Real** sale 0. **Solución:** pulsar *Recalcular reales*.

3. **Ingresos a 0 aunque el proyecto tenga trabajo**: si el ingreso está solo **"A
   facturar"/previsto** (sin factura ni asiento WIP), **no hay nada contabilizado** en
   cuentas 70 → Ingresos 0. **Solución:** facturar o **generar el asiento WIP** desde el
   presupuesto analítico.

4. **Horas a 0 aunque el proyecto tenga partes de horas**: casi siempre es porque los
   **empleados no tienen "Tipo empleado" (Interno/Externo)**. En el panel de Rentabilidad
   se ve como "Partes de horas" **sin separar**. **Solución:** rellenar el Tipo empleado
   en esos empleados (así la automatización los clasifica).

5. **Costes a 0**: Materiales/Gastos/Pedidos solo aparecen si están **imputados a la
   cuenta analítica del proyecto** (stock con costes analíticos activados, gastos
   publicados con analítica, facturas de proveedor de pedidos con analítica).

6. **Estás mirando un mes sin actividad**: el dato puede estar en otro mes del rango
   (la tabla se desplaza en horizontal). Mira la columna **Total** para ver el acumulado.

---

## 6. Cómo comprobar que los datos son veraces

- **Ingresos**: el **Total ingresos** de cada mes debe **cuadrar con la fila "Ingreso"**
  de *Contabilidad → Informes → Pérdidas y ganancias*, filtrando por el mismo
  proyecto/cuenta analítica.
- **Costes**: la **suma anual** de cada fila de Costes debe **cuadrar con el panel de
  "Rentabilidad"** del propio proyecto (Costes: Partes de horas, Pedidos de compra,
  Materiales, Gastos). *(El informe es mensual; el panel da totales.)*

---

## 7. Filtros útiles para encontrar proyectos con datos (modelo Proyectos)

Pegar en el editor de código del **Filtro personalizado**:

- Proyectos con **partes de horas en 2026**:
  ```
  [("timesheet_ids.date", ">=", "2026-01-01"), ("timesheet_ids.date", "<=", "2026-12-31")]
  ```
- Proyectos con **partes de horas de empleados clasificados** (para ver Horas):
  ```
  [("timesheet_ids.date", ">=", "2026-01-01"), ("timesheet_ids.date", "<=", "2026-12-31"), ("timesheet_ids.employee_id.x_studio_tipo_empleado_1", "!=", False)]
  ```

Para ver **Ingresos/WIP**, usa un proyecto al que le hayas **generado el asiento WIP**
(o facturado).

---

## 8. Notas y limitaciones actuales

- **Pedidos** se desglosa en la vista horizontal en **una sub-fila por Tipo de pedido**
  (solo los tipos con datos; color más claro y plegable con el triángulo de "Pedidos").
  Los pedidos **sin** tipo se suman en el total "Pedidos" pero no crean sub-fila.
- El coste de **Pedidos** coge el **pedido de compra confirmado** (aceptado) por su fecha
  de **confirmación**, aunque aún no esté facturado. En **Detalle mensual** y en el
  **Excel** se ve el total "Pedidos" (el desglose por tipo es de la vista horizontal).
- **Gastos** cuenta los gastos en estado *publicado/en pago/pagado*. Si tu versión usa
  otros estados y Gastos sale 0 teniendo gastos, hay que ajustar una constante en el
  código.
- La **vista horizontal** es de solo lectura (seguridad). El **Previsto** se edita en
  *Detalle mensual*.
- La analítica del informe se toma del **proyecto**; si el proyecto no tiene cuenta
  analítica, el informe no deja recalcular.
