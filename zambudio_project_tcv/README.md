# Project TCV — Odoo 19

Añade un campo **TCV (Total Contract Value)** a los pedidos de venta y a los proyectos.

## Regla aplicada

- Pedido no recurrente: `amount_untaxed`.
- Suscripción:
  - meses = `(fecha final - fecha de confirmación).days / 30`
  - recurrente = `recurring_monthly * meses`
  - se añaden una sola vez las líneas no recurrentes.
- Proyecto: suma del TCV de todos los pedidos confirmados (`sale`) cuyo `project_id` sea el proyecto.
- Los pedidos en otra moneda se convierten a la moneda de la compañía del proyecto usando la fecha del pedido.
- Si una suscripción no tiene fecha final, solo se incluyen sus líneas no recurrentes y se muestra un aviso.

## Por qué es calculado y no acumulativo

No se escribe `TCV anterior + nuevo pedido`. El valor se recalcula desde los pedidos vinculados para evitar duplicados y para mantenerse correcto al modificar, cancelar, borrar o mover un pedido de proyecto.

## Instalación

1. Copiar `project_tcv` en una ruta de addons.
2. Reiniciar Odoo.
3. Actualizar la lista de aplicaciones.
4. Instalar **Project TCV**.

Actualización por terminal:

```bash
./odoo-bin -d NOMBRE_BD -u project_tcv --stop-after-init
```

## Pruebas mínimas

1. Pedido normal de 1.000 € sin impuestos enlazado al proyecto → TCV proyecto 1.000 €.
2. Suscripción con MRR 100 €, confirmada el 01/01/2026 y final 01/07/2026 → `181 / 30 × 100 = 603,33 €`.
3. Cancelar el pedido → deja de sumar al proyecto.
4. Cambiar el pedido de proyecto → ambos proyectos se recalculan.
5. Suscripción sin fecha final → aviso y recurrente no incluido.

## Nota funcional

La fórmula solicitada divide los días entre 30. Por ello, un año natural puede dar más de 12 meses. Si el negocio quiere meses contractuales exactos, hay que cambiar la fórmula por meses de calendario o por la duración del plan recurrente.
