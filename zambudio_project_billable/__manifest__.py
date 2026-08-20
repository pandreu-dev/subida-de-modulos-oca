{
    "name": "Zambudio - Facturable sincronizado con Productividad",
    "summary": "Sincroniza Facturable con Productividad y exige cliente si el proyecto es facturable (ya NO fuerza facturable por defecto)",
    "version": "19.0.1.5.0",
    "category": "Services/Project",
    "author": "Zambudio",
    "license": "LGPL-3",
    "depends": [
        "project",
        "sale_project",
        # Define el campo Productividad (x_studio_selection_field_3ib_1j1am422d) que
        # este modulo muestra en la vista y sincroniza con Facturable.
        "zambudio_hr_project_fields",
    ],
    "data": [
        "views/project_project_views.xml",
    ],
    "installable": True,
    "application": False,
}
