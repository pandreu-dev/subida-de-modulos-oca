# Aunnna Product Labels

Modulo para Odoo 19 que anade tres formatos personalizados de etiqueta al asistente estandar de impresion de etiquetas de producto.

## Objetivo funcional

El objetivo es que el usuario pueda imprimir etiquetas de producto usando el flujo nativo de Odoo:

`Inventario > Productos > Productos > Imprimir > Etiquetas`

El modulo no crea un menu paralelo ni obliga a usar informes sueltos desde `Ajustes > Tecnico > Informes`. La mejora se integra dentro del popup estandar `Elegir diseno de etiquetas`, que es el asistente `product.label.layout`.

## Necesidad cubierta

En almacen se trabaja con impresoras Brother QL-700 y con formatos de etiqueta propios. Los formatos estandar de Odoo no encajan con los tamanos usados, por lo que se anaden tres opciones nuevas:

- Etiqueta 17 x 54 mm.
- Etiqueta 29 x 90 mm.
- Etiqueta 30 x 30 mm.

Cada etiqueta debe imprimir la informacion minima necesaria para identificar y escanear el producto:

- Nombre del producto.
- Referencia interna.
- Codigo de barras lineal Code128 en vertical, situado a la izquierda.
- Codigo de barras en texto.
- Bloque de informacion centrado en el espacio libre de la etiqueta.

No se imprime precio.

## Dependencias

El modulo depende de:

- `product`
- `web`

No depende de `stock` porque la impresion se integra en el asistente estandar de producto. Si el usuario llega a los productos desde Inventario, el flujo sigue funcionando porque el origen real es producto/variante.

## Como se usa

1. Instalar el modulo `Aunnna Product Labels`.
2. Abrir un producto o variante.
3. Pulsar `Imprimir > Etiquetas`.
4. En el popup estandar de Odoo, seleccionar uno de los nuevos formatos:
   - `Etiqueta 17 x 54 mm`
   - `Etiqueta 29 x 90 mm`
   - `Etiqueta 30 x 30 mm`
5. Indicar la cantidad de etiquetas.
6. Pulsar `Imprimir`.
7. Odoo genera un PDF con el tamano real de etiqueta seleccionado.

## Modelos soportados

El modulo soporta los dos origenes estandar:

- `product.template`
- `product.product`

Esto significa que funciona tanto desde productos como desde variantes.

## Campos usados para imprimir

El contenido de la etiqueta se prepara en `report/product_label_report.py`.

Campos usados:

- Nombre: `display_name`, ocultando el codigo interno en el contexto y convirtiendo a mayusculas.
- Referencia interna: `default_code`.
- Codigo de barras: `barcode`.
- Diseno: codigo de barras en columna izquierda, ampliado para facilitar el escaneo, y datos de producto centrados a la derecha.

El codigo de barras se genera siempre desde `barcode`, no desde `default_code`.

Esto es importante porque Odoo detecta productos al escanear usando el campo `barcode`. Aunque actualmente referencia interna y codigo de barras puedan coincidir, el dato correcto para imprimir y escanear es `barcode`.

## Tipo de codigo de barras

El modulo usa Code128 mediante la API nativa de informes de Odoo.

El PNG del codigo de barras se genera en Python y se incrusta en el PDF como imagen base64. Esto evita que el PDF tenga que cargar una URL externa y reduce el riesgo de que aparezca un icono roto en lugar del codigo de barras.

Se usa Code128 porque las referencias internas pueden no tener 13 digitos. No se usa EAN13 y no se usa QR.

## Comportamiento si no hay codigo de barras

Si el producto no tiene informado el campo `barcode`, la etiqueta no rompe el informe.

En su lugar muestra:

`SIN CODIGO DE BARRAS`

Esto permite detectar el problema en la etiqueta y corregir la ficha del producto.

## Formatos de papel

El modulo define tres `report.paperformat`, uno por tamano.

### Etiqueta 17 x 54 mm

- Ancho: 54 mm.
- Alto: 17 mm.
- Margenes: 0.
- Header line: desactivado.
- Header spacing: 0.
- DPI: 300.

### Etiqueta 29 x 90 mm

- Ancho: 90 mm.
- Alto: 29 mm.
- Margenes: 0.
- Header line: desactivado.
- Header spacing: 0.
- DPI: 300.

### Etiqueta 30 x 30 mm

- Ancho: 30 mm.
- Alto: 30 mm.
- Margenes: 0.
- Header line: desactivado.
- Header spacing: 0.
- DPI: 300.

## Informes creados

El modulo crea tres acciones de informe que llama el wizard:

- `aunna_product_labels.action_report_product_label_17x54`
- `aunna_product_labels.action_report_product_label_29x90`
- `aunna_product_labels.action_report_product_label_30x30`

Y tres plantillas QWeb:

- `aunna_product_labels.report_product_label_17x54`
- `aunna_product_labels.report_product_label_29x90`
- `aunna_product_labels.report_product_label_30x30`

Estos informes existen para ser llamados desde el wizard estandar. No son el flujo principal de uso.

## Funcionamiento tecnico

Archivo principal:

`models/product_label_layout.py`

Este archivo hereda:

`product.label.layout`

Y anade tres valores al selection `print_format`:

- `label_17_54_custom`
- `label_29_90_custom`
- `label_30_30_custom`

Cuando el usuario selecciona uno de esos formatos, el metodo `_prepare_report_data()` devuelve el XML ID del informe correspondiente y prepara los datos que necesita QWeb.

Si el usuario selecciona cualquier formato estandar de Odoo, el modulo llama al comportamiento original con `super()`.

## Cantidades

El modulo respeta la cantidad indicada en el asistente estandar.

La cantidad se guarda en `quantity_by_product`, y el informe genera tantas etiquetas como indique el wizard para cada producto.

## Archivos del modulo

- `__manifest__.py`: dependencias y carga de datos.
- `models/product_label_layout.py`: extension del asistente estandar.
- `report/product_label_report.py`: preparacion de productos y cantidades.
- `report/product_label_reports.xml`: paperformats, acciones de informe y plantillas QWeb.
- `README.md`: documentacion funcional y tecnica.

## Pruebas recomendadas

### Prueba 1: opciones visibles

1. Abrir un producto.
2. Ir a `Imprimir > Etiquetas`.
3. Confirmar que aparecen:
   - `Etiqueta 17 x 54 mm`
   - `Etiqueta 29 x 90 mm`
   - `Etiqueta 30 x 30 mm`

### Prueba 2: impresion desde producto

1. Abrir un producto con referencia interna y codigo de barras.
2. Imprimir una etiqueta 29 x 90 mm.
3. Comprobar que el PDF no sale en A4.
4. Comprobar que aparecen nombre, referencia y codigo de barras.

### Prueba 3: impresion desde variante

1. Abrir una variante de producto.
2. Imprimir una etiqueta 17 x 54 mm.
3. Confirmar que imprime los datos de la variante correcta.

### Prueba 4: cantidad

1. Indicar cantidad 3 en el asistente.
2. Imprimir.
3. Confirmar que se generan 3 etiquetas.

### Prueba 5: escaneo

1. Imprimir etiqueta.
2. Escanear el codigo de barras con lector.
3. Confirmar que Odoo detecta el producto correcto.

### Prueba 6: producto sin barcode

1. Abrir un producto sin codigo de barras.
2. Imprimir etiqueta.
3. Confirmar que aparece `SIN CODIGO DE BARRAS`.

## Consideraciones para impresora Brother QL-700

Los tamanos definidos en Odoo son exactos, pero la impresion fisica puede depender de:

- Driver de Brother.
- Rollo instalado.
- Orientacion.
- Escala de impresion.
- Margenes que aplique el driver.
- Corte automatico.

Por eso, despues de instalar el modulo, hay que validar con impresion real y ajustar CSS si el resultado queda desplazado.

## Limitaciones conocidas

- No imprime directamente a impresora sin capa adicional de impresion.
- No crea etiquetas de albaran ni de lote/serie desde stock; este modulo solo extiende etiquetas de producto.
- No modifica formatos estandar de Odoo.
- No usa QR.

## Criterio de aceptacion

El modulo se considera correcto si:

- Las tres opciones aparecen dentro del wizard estandar.
- El PDF sale con tamano real de etiqueta.
- Respeta la cantidad indicada.
- Imprime nombre, referencia interna, barcode grafico y barcode en texto.
- El barcode escaneado identifica el producto en Odoo.
- No imprime precio.
