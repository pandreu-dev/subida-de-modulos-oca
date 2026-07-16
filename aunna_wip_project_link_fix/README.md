# AUNNA WIP - Enlace de proyecto analitico

## Problema

Los asientos WIP ya llevan distribucion analitica y aparecen en PyG, pero las lineas analiticas creadas desde esos apuntes pueden quedar sin `project_id`. Al agrupar apuntes analiticos por proyecto aparecen como `Ninguno`.

> **Cambio jul-2026 (Opcion B):** rellenar el `project_id` estandar hacia que Odoo
> tratara estos apuntes de ingreso reconocido como **partes de horas** (aparecian en el
> tablero del proyecto, en Rentabilidad y en las listas de partes, contando incluso como
> horas). Por eso, **desde `19.0.3.0.0` el modulo ya NO pone el `project_id` estandar en
> esas lineas (y lo retira de las existentes via migracion)**. El vinculo con el proyecto
> se conserva por la **cuenta analitica** (1:1 con el proyecto) y por el campo propio
> `aunna_wip_project_id`; en *Apuntes analiticos* se agrupan por **cuenta analitica** en
> vez de por proyecto. El informe operativo financiero y los asientos de coste no se ven
> afectados.

## Solucion

El modulo marca las lineas contables WIP con la linea de calculo WIP y su proyecto origen. Despues de crear/publicar el asiento, localiza las lineas analiticas generadas desde esas lineas contables y (desde `19.0.3.0.0`) se asegura de que NO lleven el `project_id` estandar, ademas de normalizar su distribucion analitica.

Tambien vuelve a revisar los asientos WIP ya existentes al abrirlos desde el calculo, para completar el enlace si el asiento se creo antes de instalar este modulo.

No cambia importes ni cuentas. Si una linea WIP tiene distribucion analitica al proyecto con porcentaje `0%`, la normaliza a la cuenta analitica del calculo con `100%`.
Si el asiento ya estaba publicado y el apunte analitico se habia generado a `0,00`, el modulo reconstruye el apunte desde la linea contable WIP corregida, usando el importe real del debe/haber.
La reconstruccion no informa cantidad/horas a cero en el apunte analitico WIP, para evitar que el importe contable quede anulado.

## Prueba

1. Calcular WIP de un presupuesto con proyecto.
2. Crear asiento WIP.
3. Abrir el asiento y comprobar que la linea con analitica tiene proyecto WIP.
4. Comprobar que la distribucion analitica no aparece al `0%`.
5. Ir a apuntes analiticos y agrupar por proyecto.
6. Confirmar que las lineas WIP aparecen bajo el proyecto correcto y con importe.

Para reparar un asiento antiguo, abrir el calculo WIP desde `Calculos WIP` y entrar en el asiento con `Abrir asiento WIP`. Esa accion vuelve a normalizar la distribucion y reconstruye el apunte analitico si estaba a cero.

## Estado de la incidencia

La incidencia de distribucion analitica WIP sigue pendiente de validacion funcional en Odoo. El historial completo de pruebas, sintomas y comprobaciones recomendadas esta documentado en:

`docs/INCIDENCIA_DISTRIBUCION_ANALITICA_WIP.md`
