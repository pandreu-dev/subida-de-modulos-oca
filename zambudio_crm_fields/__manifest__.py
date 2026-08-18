{
    "name": "Zambudio - Campos de CRM (Studio a codigo)",
    "summary": "Adopta como codigo los 25 campos x_studio_ de crm.lead",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        "crm",
        "analytic",
        "zambudio_master_data",
    ],
    # Adopcion (state=base + propiedad del modulo) ANTES de reflejar, en instalacion nueva.
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
}
