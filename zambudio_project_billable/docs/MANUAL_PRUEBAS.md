# Mini manual de pruebas — Zambudio Proyecto Facturable

> La sincronizacion es **reactiva** (`@api.onchange`): ocurre **en el momento** de
> cambiar el campo en el formulario, **sin necesidad de guardar**.

## 0. Instalar / actualizar

1. Copiar el modulo `zambudio_project_billable` en el directorio de addons.
2. Activar **Modo desarrollador**.
3. **Aplicaciones** -> *Actualizar lista de aplicaciones* -> buscar
   "Zambudio - Proyecto Facturable por defecto" -> **Instalar / Actualizar**.
   - Por linea de comandos: `odoo -u zambudio_project_billable --stop-after-init`.

> Requiere `sale_project` (aporta el check Facturable) y el campo Productividad de
> Studio en Proyecto.

---

## 1. Valores por defecto (proyecto nuevo)

1. **Proyecto** -> **Nuevo**.
2. **Resultado esperado:** en *Ajustes*, **Facturable** aparece **marcado** y
   **Productividad** = **"Actividad facturable"** (sin el cuadro "Informacion
   guardada").

## 2. Cambiar Productividad a NO facturable

1. En un proyecto con Facturable marcado y un Cliente informado.
2. Cambiar **Productividad** a *Actividad No facturable* (o *Inactividad* o
   *Ausencias*).
3. **Resultado esperado (al instante, sin guardar):** **Facturable** se **desmarca**
   y el **Cliente** se **limpia**.

## 3. Cambiar Productividad a "Actividad facturable"

1. En un proyecto con Productividad no facturable y Facturable desmarcado.
2. Cambiar **Productividad** a *Actividad facturable*.
3. **Resultado esperado (al instante):** **Facturable** se **marca** y el **Cliente**
   pasa a ser **obligatorio** (marcado en rojo si esta vacio; no deja guardar sin el).

## 4. Desmarcar Facturable manualmente

1. En un proyecto Facturable con Cliente informado.
2. **Desmarcar** el check **Facturable**.
3. **Resultado esperado (al instante):** el **Cliente** se **limpia**.

## 5. Marcar Facturable manualmente

1. En un proyecto no Facturable y sin Cliente.
2. **Marcar** el check **Facturable**.
3. **Resultado esperado:** el **Cliente** pasa a ser **obligatorio** (no deja guardar
   hasta rellenarlo).

---

## Nota

La sincronizacion se aplica en el **formulario** al cambiar Productividad o Facturable.
Creaciones/actualizaciones masivas por importacion o API no pasan por `onchange`
(comportamiento pedido: sincronizar al cambiar el campo, no al guardar).
