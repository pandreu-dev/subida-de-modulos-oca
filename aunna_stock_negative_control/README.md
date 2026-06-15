# Aunnna Stock Negative Control

Modulo para Odoo 19 que impide validar operaciones de stock cuando dejarian existencias negativas, con configuracion parametrizable por producto, categoria, ubicacion o almacen.

## Objetivo funcional

El objetivo es evitar que Odoo permita validar movimientos que dejen stock negativo en ubicaciones internas o de transito, salvo en casos configurados expresamente como excepcion.

El modulo esta pensado para entornos donde se quiere proteger el stock real y evitar descuadres operativos provocados por entregas, consumos, transferencias o ajustes sin existencias suficientes.

## Que problema resuelve

En algunos flujos Odoo puede permitir validar operaciones aunque no exista stock suficiente, dependiendo de configuracion, reservas, permisos o tipo de operacion.

Este modulo anade una barrera adicional antes de validar el movimiento:

- Comprueba el stock fisico real.
- Calcula lo que se va a retirar.
- Si el resultado queda negativo y la regla dice que debe bloquearse, impide la validacion.
- Muestra un mensaje claro al usuario.

## Dependencias

El modulo depende de:

- `stock`

No depende de contabilidad ni compras, porque el control se realiza directamente sobre movimientos de stock.

## Configuracion en Ajustes de Inventario

El modulo anade una seccion en ajustes:

`Ajustes > Inventario - Stock negativo`

Campos disponibles:

- `Activar control de stock negativo`

## Activar control de stock negativo

Es el unico interruptor global del modulo.

Si esta desactivado, el modulo no bloquea nada. Esto permite instalar el modulo sin afectar a la operativa hasta que se active funcionalmente.

Si esta activado, todo stock negativo queda bloqueado. Solo se permite stock negativo si existe una regla de tipo `Permitir excepcion`.

## Menu de reglas

Las reglas se gestionan desde:

`Inventario > Configuracion > Control stock negativo > Reglas de stock negativo`

Cada regla permite definir donde se bloquea o donde se permite una excepcion.

## Tipos de regla

Hay dos acciones:

- `Bloquear`
- `Permitir excepcion`

Con la configuracion simplificada, al activar el control ya se bloquea todo stock negativo. Por tanto, las reglas que se usan normalmente son las de `Permitir excepcion`.

La accion `Bloquear` se mantiene por compatibilidad con reglas existentes, pero no es necesaria para aplicar el bloqueo general.

Esto permite configurar una politica general estricta y abrir excepciones concretas.

## Ambitos de regla

Cada regla puede aplicar por:

- Producto.
- Categoria.
- Ubicacion.
- Almacen.

## Regla por producto

Permite bloquear o permitir stock negativo para un producto concreto.

Campo usado:

- `product_tmpl_id`

La regla compara contra la plantilla del producto.

## Regla por categoria

Permite bloquear o permitir stock negativo para una categoria de producto.

Campos usados:

- `categ_id`
- `include_child_categories`

Si `Incluir subcategorias` esta marcado, tambien aplica a productos de subcategorias.

## Regla por ubicacion

Permite bloquear o permitir stock negativo en una ubicacion concreta.

Campos usados:

- `location_id`
- `include_child_locations`

Si `Incluir sububicaciones` esta marcado, tambien aplica a sububicaciones.

## Regla por almacen

Permite bloquear o permitir stock negativo en todo un almacen.

Campo usado:

- `warehouse_id`

El modulo toma la ubicacion vista del almacen o su ubicacion principal de stock y comprueba si la ubicacion del movimiento pertenece a ese arbol.

## Compania

Las reglas pueden estar vinculadas a una compania.

Si una regla no tiene compania, aplica globalmente.

Si tiene compania, solo aplica a movimientos de esa compania.

## Mensaje adicional

Cada regla puede tener un texto en `Mensaje adicional`.

Ese texto se anade al error mostrado al usuario cuando la regla bloquea la operacion.

Sirve para explicar el motivo o indicar a quien contactar.

## Operaciones cubiertas

El control se ejecuta en:

`stock.move._action_done()`

Por tanto aplica a cualquier flujo que valide movimientos de stock, incluyendo:

- Entregas a cliente.
- Transferencias internas.
- Consumos de fabricacion.
- Ajustes de inventario que reducen stock.
- Movimientos manuales desde ubicaciones internas.
- Otros procesos que terminen validando movimientos de stock.

## Operaciones que no bloquea

No bloquea movimientos cuya ubicacion origen no sea interna o de transito.

Ejemplos:

- Entrada desde proveedor.
- Entrada desde inventario.
- Entrada desde produccion si no retira de una ubicacion interna.
- Movimientos desde ubicaciones externas.

La razon es que esas ubicaciones no representan stock propio que pueda quedar negativo.

## Como calcula el stock

El modulo no usa stock libre disponible.

Usa stock fisico real de `stock.quant.quantity`, porque el stock libre puede verse afectado por reservas y podria bloquear movimientos que ya estaban correctamente reservados.

El calculo se hace por:

- Producto.
- Ubicacion.
- Lote/serie.
- Paquete.
- Propietario.
- Compania.

Ademas, si una misma validacion retira varias lineas del mismo producto/ubicacion/lote, acumula todas las cantidades antes de decidir.

## Mensaje de bloqueo

Cuando se bloquea una operacion, el usuario ve un mensaje similar a:

`No se puede validar la operacion porque dejaria stock negativo.`

Y debajo se detallan:

- Producto.
- Ubicacion.
- Stock actual.
- Cantidad a retirar.
- Stock resultante.
- Lote/serie, si aplica.
- Mensaje adicional de la regla, si existe.

## Ejemplos de configuracion

### Bloquear todo stock negativo

1. Ir a Ajustes.
2. Abrir la seccion `Inventario - Stock negativo`.
3. Marcar `Activar control de stock negativo`.
4. Guardar.

Resultado:

Cualquier operacion que deje stock negativo queda bloqueada salvo excepciones.

### Permitir excepcion para una ubicacion

1. Ir a `Inventario > Configuracion > Control stock negativo > Reglas de stock negativo`.
2. Crear regla.
3. Accion: `Permitir excepcion`.
4. Aplicar por: `Ubicacion`.
5. Seleccionar ubicacion.
6. Marcar `Incluir sububicaciones` si procede.

Resultado:

Aunque el bloqueo general este activo, esa ubicacion permite negativo.

### Permitir excepcion para una categoria

1. En ajustes, activar el control.
2. Crear regla.
3. Accion: `Permitir excepcion`.
4. Aplicar por: `Categoria`.
5. Seleccionar categoria.
6. Marcar `Incluir subcategorias` si procede.

Resultado:

Aunque el bloqueo general este activo, esa categoria permite negativo.

### Permitir excepcion para un almacen completo

1. Crear regla.
2. Accion: `Permitir excepcion`.
3. Aplicar por: `Almacen`.
4. Seleccionar almacen.

Resultado:

Aunque el bloqueo general este activo, las ubicaciones pertenecientes a ese almacen permiten negativo.

## Seguridad

Permisos definidos:

- Usuarios de inventario pueden leer reglas.
- Responsables de inventario pueden crear, modificar y borrar reglas.

Archivo:

`security/ir.model.access.csv`

## Archivos del modulo

- `__manifest__.py`: dependencias y datos del modulo.
- `models/res_config_settings.py`: parametros globales en ajustes.
- `models/stock_negative_rule.py`: modelo de reglas y excepciones.
- `models/stock_move.py`: validacion antes de confirmar movimientos.
- `views/res_config_settings_views.xml`: seccion en ajustes.
- `views/stock_negative_rule_views.xml`: menu, vistas y accion de reglas.
- `security/ir.model.access.csv`: permisos.
- `README.md`: documentacion funcional y tecnica.

## Pruebas recomendadas

### Prueba 1: modulo instalado pero desactivado

1. Instalar el modulo.
2. No activar el control en ajustes.
3. Validar una salida que deje negativo.
4. Confirmar que el modulo no bloquea.

### Prueba 2: bloqueo global

1. Activar el control.
2. Intentar entregar mas unidades de las disponibles.
3. Confirmar que Odoo bloquea la validacion con mensaje claro.

### Prueba 3: excepcion por producto

1. Mantener bloqueo global activo.
2. Crear regla `Permitir excepcion` por producto.
3. Intentar dejar negativo ese producto.
4. Confirmar que permite la operacion.
5. Probar otro producto sin excepcion y confirmar que bloquea.

### Prueba 4: excepcion por categoria

1. Mantener el control activo.
2. Crear regla `Permitir excepcion` por categoria.
3. Intentar dejar negativo un producto de esa categoria.
4. Confirmar que permite la operacion.
5. Probar un producto de otra categoria y confirmar que bloquea.

### Prueba 5: ubicaciones hijas

1. Crear regla por ubicacion con `Incluir sububicaciones`.
2. Hacer una salida desde una sububicacion.
3. Confirmar que la regla aplica.

### Prueba 6: almacen

1. Crear regla por almacen.
2. Hacer salida desde una ubicacion interna del almacen.
3. Confirmar que bloquea si deja stock negativo.

### Prueba 7: lotes o numeros de serie

1. Usar producto con lote/serie.
2. Tener stock solo en un lote.
3. Intentar sacar mas cantidad de ese lote.
4. Confirmar que el mensaje indica el lote/serie.

### Prueba 8: transferencia interna

1. Tener stock insuficiente en ubicacion origen.
2. Validar transferencia interna.
3. Confirmar que bloquea la salida de la ubicacion origen.

### Prueba 9: ajuste de inventario

1. Hacer un ajuste que reduzca stock por debajo de cero.
2. Validarlo.
3. Confirmar que el modulo bloquea si aplica la regla.

## Consideraciones tecnicas

El modulo revisa antes de ejecutar el `super()` de `_action_done()`. Por eso bloquea antes de que el movimiento cree o modifique quants.

La comprobacion usa `stock.quant._gather()` si existe en la version instalada. Si no, usa `read_group()` sobre `stock.quant`.

La comprobacion es estricta por ubicacion, lote, paquete y propietario. Esto evita permitir negativo en un lote concreto solo porque exista stock de otro lote.

## Limitaciones conocidas

- No corrige negativos ya existentes.
- No crea inventarios de ajuste.
- No reserva stock automaticamente.
- No decide sustituciones de lote o ubicacion.
- Si ya existe stock negativo antes de instalar el modulo, seguira existiendo hasta que se corrija manualmente.

## Criterio de aceptacion

El modulo se considera correcto si:

- Se puede activar desde ajustes de inventario.
- Se puede configurar por producto, categoria, ubicacion y almacen.
- Las excepciones permiten negativos solo donde corresponde.
- Las operaciones que dejan negativo se bloquean con mensaje claro.
- Las operaciones con stock suficiente se validan normalmente.
- No afecta a entradas de proveedor ni movimientos desde ubicaciones externas.
