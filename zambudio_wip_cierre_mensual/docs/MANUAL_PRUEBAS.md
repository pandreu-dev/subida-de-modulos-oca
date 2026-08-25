# Cerrar mes (WIP) — Manual de pruebas

> Módulo: **`zambudio_wip_cierre_mensual`** · Entorno: **PRE (pruebas)**
> Para: responsable de contabilidad (Manuel)

## 1. Qué hace
Genera, **de una vez para todos los proyectos**, el asiento de **ingreso reconocido (WIP)** de un mes:
- **Un asiento por proyecto**, con el importe del **avance confirmado** de ese mes (el mismo que se ve en la pestaña *Seguimiento económico*).
- Fecha del asiento: **último día del mes**.
- **Reversión automática** el **día 1** del mes siguiente.
- Ya **no** se hace desde el presupuesto analítico ni entrando proyecto a proyecto.

## 2. Dónde está
**Contabilidad → Cerrar mes (WIP)** (dentro del desplegable *Contabilidad*).

## 3. Cómo usarlo (paso a paso)
1. Abre **Contabilidad → Cerrar mes (WIP)**.
2. En la ventana rellena:
   - **Compañía**: la que quieras cerrar (p. ej. AUNNA IT).
   - **Mes** y **Año**: un mes **ya cerrado / confirmado** (no el mes en curso).
3. Pulsa **"Cerrar mes y generar asientos"**.
4. Se abre la **lista de los asientos creados** (uno por proyecto), cada uno con su reversión.

## 4. Qué comprobar (que está correcto)
- Sale **un asiento por cada proyecto** con avance confirmado ese mes.
- Abre un asiento y mira la línea de **ingreso (cuenta 705)** → debe llevar la **distribución analítica del proyecto**.
- El **importe** del asiento = el **avance confirmado** de ese proyecto ese mes (cuadra con *Seguimiento económico*).
- La **fecha** del asiento es el **último día del mes**; y su **reversión** (referencia *"Reversión de: …"*) tiene fecha el **día 1** del mes siguiente.
- **No duplica:** vuelve a lanzar el **mismo mes** → esos proyectos deben **omitirse** (no se crean otra vez).

## 5. Cosas a tener en cuenta
- Si eliges un mes **sin avances confirmados**, saldrá *"no se ha generado ningún asiento"*. Es normal: elige un mes ya cerrado.
- Si **falta un proyecto** que esperabas → ese proyecto **no tiene el avance confirmado** ese mes. Ve a su ficha, ejecuta **"Recalcular datos reales"** / confírmalo, y vuelve a lanzar el cierre.
- El importe sale del **confirmado**, **no** de la previsión (por si difieren; el confirmado es lo que valida el equipo).
- El cierre es **por compañía**: lánzalo una vez por cada compañía que quieras cerrar.

## 6. Cómo probarlo YA (sin esperar a fin de mes)
El cierre solo genera desde avances **CONFIRMADOS**. Para probarlo ahora con un mes pasado (p. ej. **julio**):

1. **Mira qué meses tienen ya avances confirmados** (a lo mejor no hay que preparar nada). Con acceso al servidor, en solo lectura:
   ```sql
   SELECT fecha_mes, estado, COUNT(*) AS proyectos, SUM(importe_confirmado) AS total
   FROM produccion_avance_mes GROUP BY fecha_mes, estado ORDER BY fecha_mes, estado;
   ```
   Si aparece algún mes en estado **`confirmado`**, ve directo al paso 4 con ese mes.
2. En un **proyecto de prueba** → pestaña **Seguimiento económico**: asegúrate de que el mes de prueba (p. ej. julio) tiene un **ingreso reconocido / avance** (si no, añádelo).
3. Pulsa **"Recalcular datos reales"** y luego **"Confirmar avance mensual"** → el avance de ese mes queda en estado **confirmado**.
4. Abre **Contabilidad → Cerrar mes (WIP)**, elige ese **mes/año** y pulsa **"Cerrar mes y generar asientos"** → genera el asiento del proyecto (+ su reversión el día 1 del mes siguiente).

> ⚠️ **Clave:** añadir solo el "ingreso esperado" (previsión) **no basta** — el cierre usa el **confirmado**. Hay que darle a **"Confirmar avance mensual"** para ese mes. Si "Confirmar avance mensual" no deja con el **mes en curso** (agosto), hazlo con un **mes cerrado** (julio). Si aun así no es cómodo, se puede añadir un **"modo prueba"** al asistente que genere desde la previsión (pídeselo a Pablo).

## 7. Si algo no cuadra
Anota **proyecto + mes + qué esperabas vs qué salió** y pásaselo a Pablo. Estamos en **PRE (pruebas)**, así que cualquier asiento se puede **borrar o cancelar** sin ningún problema.
