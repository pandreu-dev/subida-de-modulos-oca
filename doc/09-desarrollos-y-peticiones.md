# 09 · Desarrollos y peticiones

## Peticiones funcionales — estado

### 1) Coste de pedidos por recepción en el informe ✅ HECHO
"Que el informe económico impacte el coste según los productos **recibidos en albarán** y
en su **fecha de recepción**" (antes: total del pedido al confirmar).
→ Desarrollado en `zambudio_informe_operativo_financiero`. **Validado por Manuel.**
Bienes: cantidad recibida × precio del pedido, cada recepción en su fecha. Servicios: por
fecha de confirmación.

### 2) Nombre de proyecto y cuenta analítica desde pedido de venta ✅ HECHO
"El proyecto creado desde un pedido de venta se llama **nº pedido - descripción de la
línea**, y su **cuenta analítica** igual."
→ `zambudio_project_sale_naming` **v19.0.2.1.0** (rehecho y probado en PRE el 21/07).
⚠️ La cuenta analítica **siempre se muestra con el cliente detrás** (`... - CLIENTE`): es
estándar de Odoo, no se puede quitar; el **campo Nombre** sí queda correcto.
Módulos de contexto: `sale_project`, `sale_timesheet`, `project`, análisis analítico,
`zambudio_project_unique_name`, `zambudio_project_type`.

### 3) Revertir "facturable por defecto" ✅ HECHO
Laura pidió quitar que el proyecto sea facturable por defecto.
→ `zambudio_project_billable` **v19.0.1.4.0**: se retiró el default; conserva la
sincronización Facturable↔Productividad y el cliente obligatorio si es facturable.

## Consulta: secuencia del pedido de venta
La jefa prefería el código de pedido como `P-YYMM-nnnnn` (en PRE salía `P-YY-MM-A/nnnnn`).
Es en **pedido de venta**.
- Ruta: `Ajustes > Técnico > Secuencias e Identificadores > Secuencias` (buscar la de
  `sale.order`).
- Prefijo deseado: `P-%(range_y)s%(range_month)s-`  ·  Longitud secuencia: **5**.

## App externa / piloto de imputación de horas
Interlocutoras: **Verónica**, **Laura**. Objetivo: app externa para registrar horas contra
proyectos/tareas de Odoo, respetando **multiempresa**.

**Flujo:**
1. Usuario se registra con email → 2. Odoo busca empleado por email →
3. Se obtiene empleado, compañía y manager → 4. Filtrar proyectos por compañía →
5. Listar tareas del proyecto → 6. Imputar horas con `employee_id`.

**Filtro empleado por email:**
```json
[["work_email","=ilike","CORREO_EMPLEADO"],["active","=",true]]
```

**Conclusiones técnicas:**
- Campo obligatorio principal: **`account_id`** (cuenta analítica del proyecto).
- `company_id`: no se envía al inicio, pero **validar por multiempresa**.
- **No** enviar `amount`/coste: Odoo lo calcula con horas × coste/hora del empleado.
- Estado "Borrador": no incluir salvo campo personalizado.
- Endpoints esperados: extraer proyectos/tareas; grabar imputaciones (JSON con proyecto,
  tarea, fecha, tiempo).
- **API key PRE caduca el 2026-10-12.** (Se habló de "persisten key" para claves eternas.)

## Excel de control de desarrollos
`PLANTILLA_CONTROL_DESARROLLOS_actualizada.xlsx` (en Descargas de Pablo). Divide en:
**Subidos a PRO** / **Validados pendientes de subir a PRO** / **Solicitados pendientes de
desarrollar en PRE**. Columnas: Título · Funcionamiento · Observaciones.
> Mantener sincronizado con [05-inventario-modulos.md](05-inventario-modulos.md).
