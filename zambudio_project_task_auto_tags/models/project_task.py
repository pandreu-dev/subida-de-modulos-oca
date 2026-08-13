# -*- coding: utf-8 -*-
"""Override de project.task para propagar etiquetas del proyecto a la tarea.

Sustituye dos automatizaciones de Studio (on_create_or_write):
  - Etiqueta "Interno":   si el proyecto la tiene, se anade a la tarea.
  - Etiqueta "Formacion": si el proyecto la tiene, se anade a la tarea.

A diferencia de Studio (que usaba "set" y podia borrar otras etiquetas de la
tarea), aqui se ANADE la etiqueta con Command.link sin tocar el resto.
"""

from odoo import api, models
from odoo.fields import Command

# Referencias por NOMBRE (nunca por id de BD). El humano debe confirmar estos
# nombres frente a los reales de project.tags (Studio usaba los ids 35 y 60).
TAG_INTERNAL_NAME = "Interno"
TAG_TRAINING_NAME = "Formación"

# Lista de nombres de etiqueta a propagar del proyecto a la tarea.
TARGET_TAG_NAMES = (TAG_INTERNAL_NAME, TAG_TRAINING_NAME)

# Bandera de contexto propia para evitar recursion en el write interno.
_SKIP_CTX = "skip_zambudio_tags"


class ProjectTask(models.Model):
    _inherit = "project.task"

    @api.model_create_multi
    def create(self, vals_list):
        """Crea las tareas y propaga las etiquetas del proyecto."""
        records = super().create(vals_list)
        # Si venimos de nuestro propio reproceso, no volver a aplicar.
        if not self.env.context.get(_SKIP_CTX):
            records._zambudio_apply_project_tags()
        return records

    def write(self, vals):
        """Escribe y, si no venimos del reproceso, propaga las etiquetas."""
        res = super().write(vals)
        if not self.env.context.get(_SKIP_CTX):
            self._zambudio_apply_project_tags()
        return res

    def _zambudio_apply_project_tags(self):
        """Anade a cada tarea las etiquetas objetivo que tenga su proyecto.

        - Solo actua sobre el campo tag_ids (many2many a project.tags), que debe
          existir tanto en project.task como en project.project.
        - Compara por NOMBRE de etiqueta (no por id) y anade con Command.link.
        - Escribe unicamente si falta alguna etiqueta (eficiencia).
        - Reescribe con la bandera de contexto para no recursar.
        """
        # Robustez: si el campo tag_ids no existe en la tarea, salir sin error.
        if "tag_ids" not in self._fields:
            return

        for task in self:
            project = task.project_id
            # Sin proyecto o sin campo tag_ids en el proyecto: nada que propagar.
            if not project or "tag_ids" not in project._fields:
                continue

            project_tags = project.tag_ids
            if not project_tags:
                continue

            task_tag_ids = set(task.tag_ids.ids)
            commands = []

            for tag_name in TARGET_TAG_NAMES:
                # Buscar en el proyecto la etiqueta por nombre (insensible a
                # mayusculas y espacios extremos, como el 'ilike' de Studio).
                matching = project_tags.filtered(
                    lambda t: (t.name or "").strip().lower() == tag_name.strip().lower()
                )
                for tag in matching:
                    # Anadir solo si la tarea aun no la tiene.
                    if tag.id not in task_tag_ids:
                        commands.append(Command.link(tag.id))
                        task_tag_ids.add(tag.id)

            # Escribir solo si hay algo que anadir de verdad.
            if commands:
                task.with_context(**{_SKIP_CTX: True}).write({"tag_ids": commands})
