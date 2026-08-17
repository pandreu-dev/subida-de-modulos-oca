# Zambudio - Datos maestros (Studio a codigo)

Pasa a **código** los 5 modelos maestros que creó Odoo Studio, **sin perder datos**.

## Modelos
- `x_tipo_empleado` — Tipo empleado (Interno, Externo…)
- `x_subtipo_empleado` — Subtipo empleado (Empleado Regular, Becario, Subco GZ, Subco Externo)
- `x_tipo_de_personal` — Tipo de personal (Directo, Indirecto)
- `x_sector` — Sector (CRM)
- `x_crm_practica` — Estructura / Práctica CRM (con campo `x_studio_divisin`: NODO RENOVABLES, NODO COMUNICACIONES, SELECT ASTERISCO, BPO, DIGITAL)

## Cómo conserva los datos
Se definen **los mismos nombres de modelo y de campo** que ya usa Studio
(`x_name`, `x_active`, `x_studio_sequence`, y `x_studio_divisin` en práctica). Al
instalar, Odoo **reutiliza las tablas y los registros existentes** (mismos ids), así
que:
- No se migra ni un dato.
- Las many2one de empleados y leads que apuntan a estos maestros **siguen válidas**.
- Solo cambia la **propiedad** del modelo: de "manual (Studio)" a "de código".

`x_active` funciona como campo de archivado (Odoo lo reconoce igual que `active`).

## Qué NO hace (a propósito)
- No replica el "chatter" (actividades/mensajes) que Studio añadió: no son datos de
  negocio. Esos campos quedan como campos manuales sin uso en estas vistas.
- No toca los campos que referencian estos maestros (en `hr.employee` / `crm.lead`);
  esos van en bloques posteriores (`hr_employee_custom`, `crm_custom`).

## Verificación tras instalar (PRE)
1. Volver a lanzar el volcado de registros y comprobar que **ids y nombres son idénticos**.
2. Abrir un empleado y un lead: su tipo/subtipo/sector deben seguir mostrándose.
3. Menús en **Ajustes → Técnico → Datos maestros configurables**.

## Pendiente al validar
- Desactivar las vistas auto-generadas de Studio de estos 5 modelos (las sustituyen las de aquí).
- Permisos: por ahora replican los de Studio (usuarios internos leen; Ajustes/Admin edita).
  Si RRHH/CRM deben editar, se cambia el grupo.

## Dependencias
- `mail`
