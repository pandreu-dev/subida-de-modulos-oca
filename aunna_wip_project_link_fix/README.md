# AUNNA WIP - Enlace de proyecto analitico

## Problema

Los asientos WIP ya llevan distribucion analitica y aparecen en PyG, pero las lineas analiticas creadas desde esos apuntes pueden quedar sin `project_id`. Al agrupar apuntes analiticos por proyecto aparecen como `Ninguno`.

## Solucion

El modulo marca las lineas contables WIP con la linea de calculo WIP y su proyecto origen. Despues de crear/publicar el asiento, localiza las lineas analiticas generadas desde esas lineas contables y rellena el proyecto cuando el campo existe.

Tambien vuelve a revisar los asientos WIP ya existentes al abrirlos desde el calculo, para completar el enlace si el asiento se creo antes de instalar este modulo.

No cambia importes ni cuentas. Si una linea WIP tiene distribucion analitica al proyecto con porcentaje `0%`, la normaliza a `100%` para que Odoo genere el apunte analitico con importe real.
Si el asiento ya estaba publicado y el apunte analitico se habia generado a `0,00`, el modulo intenta reconstruir esos apuntes desde la linea contable WIP corregida.

## Prueba

1. Calcular WIP de un presupuesto con proyecto.
2. Crear asiento WIP.
3. Abrir el asiento y comprobar que la linea con analitica tiene proyecto WIP.
4. Comprobar que la distribucion analitica no aparece al `0%`.
5. Ir a apuntes analiticos y agrupar por proyecto.
6. Confirmar que las lineas WIP aparecen bajo el proyecto correcto y con importe.
