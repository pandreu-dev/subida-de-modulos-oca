from . import models

# Los 25 campos x_studio_ de crm.lead que este modulo ADOPTA como codigo.
CRM_FIELDS = (
    "x_studio_comercial",
    "x_studio_distribucin_analitica",
    "x_studio_divisin",
    "x_studio_etapa",
    "x_studio_etapa_1",
    "x_studio_fecha_fin_contrato",
    "x_studio_fecha_fin_de_contrato",
    "x_studio_fecha_inicio_contrato",
    "x_studio_fecha_prevista_de_cierre_1",
    "x_studio_ingreso_ponderado",
    "x_studio_ingresos_cogs",
    "x_studio_ingresos_sos",
    "x_studio_many2one_field_1nk_1ja0lhri5",
    "x_studio_many2one_field_6tr_1jg75tejm",
    "x_studio_meses_de_duracin",
    "x_studio_pm_cogs",
    "x_studio_pm_sos",
    "x_studio_prctica",
    "x_studio_prctica_relacionada",
    "x_studio_probabilidad_avanzada",
    "x_studio_probabilidad_inicial",
    "x_studio_probabilidad_negociacin",
    "x_studio_responsable",
    "x_studio_selection_field_83n_1jiv18ana",
    "x_studio_tamao",
)


def _adopt(cr):
    """Adopta los campos de crm.lead: state='base' + ir.model.data propio (idempotente).

    Solo METADATOS (no toca columnas). Corre ANTES de la reflexion (pre_init_hook).
    Misma tecnica validada en zambudio_master_data.
    """
    cr.execute(
        "UPDATE ir_model_fields SET state='base' WHERE model='crm.lead' AND name IN %s",
        (CRM_FIELDS,),
    )
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'zambudio_crm_fields',
               'field_crm_lead__'||f.name,
               'ir.model.fields', f.id, true
        FROM ir_model_fields f
        WHERE f.model='crm.lead' AND f.name IN %s
        ON CONFLICT (module, name) DO NOTHING
        """,
        (CRM_FIELDS,),
    )


def pre_init_hook(env):
    _adopt(env.cr)
