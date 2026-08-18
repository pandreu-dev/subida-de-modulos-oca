{
    "name": "Zambudio - Campos de empleado y proyecto (Studio a codigo)",
    "summary": "Adopta como codigo los campos x_studio_ de hr.employee y la Productividad de project.project",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "project",
        "zambudio_master_data",
    ],
    # Adopcion (state=base + propiedad del modulo) ANTES de reflejar, en instalacion nueva.
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
}
