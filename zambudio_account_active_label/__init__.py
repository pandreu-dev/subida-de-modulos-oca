from . import models


def _fix_active_label(env):
    """Fuerza la etiqueta del campo `active` de account.account a 'Activo' en TODOS
    los idiomas. El override del `string` (codigo) solo corrige el ingles; en la BD
    quedaba una traduccion es_ES pegada como 'Obsoleto' que sobrevivia. Aqui se
    reescribe por idioma."""
    field = env["ir.model.fields"].search(
        [("model", "=", "account.account"), ("name", "=", "active")], limit=1
    )
    if not field:
        return
    langs = env["res.lang"].search([]).mapped("code") or ["en_US", "es_ES"]
    for lang in langs:
        field.with_context(lang=lang).write({"field_description": "Activo"})


def post_init_hook(env):
    _fix_active_label(env)
