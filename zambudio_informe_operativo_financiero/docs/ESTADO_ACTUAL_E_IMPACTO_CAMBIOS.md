# Informe operativo financiero — Estado actual y cómo afectan los cambios solicitados

> Responde a lo pedido: **(1) qué está hecho hoy** y cómo se calcula cada coste, y **(2) cómo afectaría cada cambio** indicado en el correo. Módulo afectado: `zambudio_informe_operativo_financiero`.

---

## 1. Lo que está hecho hoy

El informe calcula, **por proyecto y mes**, comparando **Previsión** (la escribe el usuario) con **Real** (lo calcula el sistema desde la contabilidad y los partes). Hoy las líneas de **coste real** se calculan así:

| Coste (hoy) | Cómo se calcula hoy |
|---|---|
| **Horas internas** | Coste de los **partes de horas** de empleados **internos** (horas × coste/hora). Se marca "interna" con una **automatización** según el **tipo de empleado**. |
| **Horas externas** | Igual, pero para horas de empleados de **otra compañía del grupo**. |
| **Pedidos** | Coste de los **pedidos de compra confirmados**, **desglosado por Tipo de pedido**. Para **bienes**: lo **recibido en cada albarán**, en su fecha. Para **servicios**: el **total del pedido** en la fecha de confirmación. |
| **Materiales** (Stock interno) | Coste del **material entregado por albarán** imputado al proyecto. |
| **Gastos** | **Gastos de empleado** imputados al proyecto (hoy se suman **todos**, sin separar por categoría). |

*(Además calcula ingresos reconocidos, facturación y WIP, que no cambian con esta petición.)*

**Guardado de datos:** el informe **ya guarda, mes a mes, la Previsión, el dato Real y la Diferencia**. Es decir, el informe de **"previsión vs real vs diferencia"** que pides **prácticamente ya existe**.

---

## 2. Los cambios que pediste y cómo afectan

### 2.1 · Desdoblar "Servicios" → Contratas (Fix price) / (Por administración)
- **Afecta a:** los **tipos de pedido** y al informe (que **ya desglosa por tipo de pedido**).
- **Qué hay que hacer:** crear los **2 tipos nuevos** y marcar a qué tipología pertenece cada tipo de pedido.
- **Impacto:** **bajo-medio**.

### 2.2 · Nuevas tipologías de coste

| Tipología | ¿Cambia respecto a hoy? | Impacto |
|---|---|---|
| **Horas internas** | No: se calcula igual que ahora. | Ninguno |
| **Horas externas** | Solo cambia **la automatización** para que cuenten **solo las de Subcos GZ**. | **Ya hecho** ✔ |
| **Contratas (Fix price)** | **Nueva**: sale del desglose por tipo de pedido. Falta definir qué es "parte recepcionada" en un servicio. | Medio |
| **Contratas (Por administración)** | Igual que la anterior. | Medio |
| **Materiales** | **Cambia la definición**: pasaría a ser "lo recepcionado de cualquier tipo **excepto** contratas y viajes". Hay que **reconciliarlo con el cálculo actual** (albarán) para **no contar el coste dos veces**. | Medio-alto |
| **Gastos de Viaje** | **Nueva**: junta los **pedidos de viaje** con los **gastos de Kilometraje/Dietas** del módulo Gastos. Hoy los gastos se suman **sin separar por categoría**: hay que **filtrarlos** y engancharlos al módulo Gastos. | Medio-alto |

> **Nota (corregido tras tu revisión):** los **gastos sí llevan distribución analítica** → se contarán **según su reparto** (si un gasto está al 60 % en el proyecto, cuenta el 60 %), como los pedidos. Y los **partes de horas no generan apuntes contables** (el módulo "COSTE TH" no está instalado): el coste de horas sale del **propio parte validado**, no de la contabilidad.

- **En conjunto, el 2.2 es el grueso del desarrollo.**

### 2.3 · Guardar los costes reales de cierre junto a las previsiones (2 informes)
- **Ya hecho en parte:** el informe **ya guarda Previsión / Real / Diferencia por mes**. El "informe de previsión vs real vs diferencia" ya está.
- **Qué falta:** revisar contigo/Verónica el **modelo de datos** (si vale como está, o marcar con un campo qué es dato **de cierre** y qué es **previsión**, como comentabas).
- **Impacto:** **bajo** si vale como está; **medio** si se reestructura.

---

## 3. Lo que necesito confirmar (con Verónica) para desarrollar el 2.1–2.2
1. **Cómo marcamos** a qué tipología pertenece cada tipo de pedido.
2. Qué se cuenta como **"recepcionado"** en un servicio (¿al confirmar el pedido, o lo realmente recibido?).
3. **Materiales:** ¿solo compra directa recibida, o también el material que sale de almacén? (para no duplicar).
4. **Nombres exactos** de las categorías de gasto **Kilometraje** y **Dietas**.

---

## 4. Aviso: si vamos a Odoo Community
La clasificación de **Horas internas/externas** se hace hoy con **Studio** (solo Enterprise). En **Community** habría que **rehacer esa automatización**. A tenerlo en cuenta antes de migrar.

---

*El detalle técnico (modelos y campos de Odoo, para implementar) está en el documento `ESPEC_TIPOLOGIAS_COSTES`.*
