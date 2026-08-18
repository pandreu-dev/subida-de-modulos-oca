# Zambudio - Campos de CRM (Studio a código)

Adopta como **código** (sin mover datos) los **25 campos** que Studio añadió a
`crm.lead`. Misma técnica validada en `zambudio_master_data` (state=base + propiedad
del módulo vía `pre_init_hook`).

## Qué hace
- Define en código los 25 `x_studio_*` de `crm.lead` con su tipo, relación y valores de
  selection EXACTOS (según la foto de PRE) y los adopta (dejan de ser de Studio).
- Las **automatizaciones de CRM** (`zambudio_crm_automations`) siguen funcionando: usan
  los MISMOS nombres de campo.

## Detalles
- Los 2 campos que en Studio eran **calculados** (`x_studio_fecha_fin_contrato`,
  `x_studio_ingreso_ponderado`) se adoptan como campos **normales**: conservan su valor
  actual; la lógica real la llevan las automatizaciones. (Decisión de negocio: replicar;
  los datos podían perderse — aquí se conservan.)
- Campos monetarios (`ingresos_sos`, `ingresos_cogs`) usan `company_currency` de crm.lead.
- Hay **duplicados/heredados** de Studio (p. ej. `x_studio_prctica` selection viejo vs
  `x_studio_prctica_relacionada` m2o; dos "fecha fin de contrato"). Se adoptan todos para
  no romper nada; la limpieza de duplicados se puede hacer aparte más adelante.

## Sin vistas propias
Las vistas de Studio siguen mostrando estos campos hasta que se migren/limpien. Este
módulo solo pasa la **propiedad** de los campos a código.

## Dependencias
- `crm`, `analytic`, `zambudio_master_data`
