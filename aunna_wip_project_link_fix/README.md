# AUNNA WIP - Enlace de proyecto analitico

## Problema

Los asientos WIP ya llevan distribucion analitica y aparecen en PyG, pero las lineas analiticas creadas desde esos apuntes pueden quedar sin `project_id`. Al agrupar apuntes analiticos por proyecto aparecen como `Ninguno`.

## Solucion

El modulo marca las lineas contables WIP con la linea de calculo WIP y su proyecto origen. Despues de crear/publicar el asiento, localiza las lineas analiticas generadas desde esas lineas contables y rellena el proyecto cuando el campo existe.

No cambia importes, cuentas, distribucion analitica ni la logica economica del WIP.

## Prueba

1. Calcular WIP de un presupuesto con proyecto.
2. Crear asiento WIP.
3. Abrir el asiento y comprobar que la linea con analitica tiene proyecto WIP.
4. Ir a apuntes analiticos y agrupar por proyecto.
5. Confirmar que las lineas WIP aparecen bajo el proyecto correcto.

