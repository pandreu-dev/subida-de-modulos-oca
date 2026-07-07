# Mini manual de pruebas — Zambudio Proyecto Facturable

## 0. Instalar / actualizar

1. Copiar el modulo `zambudio_project_billable` en el directorio de addons.
2. Activar **Modo desarrollador**.
3. **Aplicaciones** → *Actualizar lista de aplicaciones* → buscar
   "Zambudio - Proyecto Facturable por defecto" → **Instalar**.
   - Por linea de comandos: `odoo -i zambudio_project_billable --stop-after-init`.

> Requiere que este instalado `sale_project` (el que aporta el check Facturable) y el
> campo Productividad de Studio en Proyecto.

---

## 1. Facturable por defecto

1. Ir a **Proyecto** → **Nuevo**.
2. **Resultado esperado:** en la pestana *Ajustes*, el check **Facturable** aparece
   **marcado** por defecto.

## 2. Cliente obligatorio si es facturable

1. En un proyecto nuevo (Facturable marcado), dejar el **Cliente** vacio.
2. Intentar **guardar**.
3. **Resultado esperado:** el formulario marca **Cliente** como obligatorio y no deja
   guardar hasta rellenarlo.
4. Desmarcar **Facturable** → el **Cliente** deja de ser obligatorio y ya se puede
   guardar sin cliente.

## 3. Sincronizacion con Productividad (se desmarca)

1. En un proyecto **Facturable**, poner **Productividad** = *Actividad No facturable*
   (o *Inactividad* o *Ausencias*).
2. **Guardar**.
3. **Resultado esperado:** al guardar, el check **Facturable** se **desmarca** solo.

## 4. Productividad facturable (se conserva)

1. En un proyecto, poner **Productividad** = *Actividad facturable* y marcar
   **Facturable**.
2. **Guardar**.
3. **Resultado esperado:** el check **Facturable** se **mantiene** marcado.

## 5. No se vuelve a marcar solo (solo desmarcar)

1. Partir de un proyecto **no facturable** con Productividad = *Inactividad*.
2. Cambiar **Productividad** a *Actividad facturable* y **guardar**.
3. **Resultado esperado:** el check **Facturable** **NO** se marca automaticamente
   (hay que marcarlo a mano). Es el comportamiento pedido ("solo desmarcar").

## 6. Proyecto sin Productividad

1. Crear un proyecto y dejar **Productividad** vacia.
2. **Guardar**.
3. **Resultado esperado:** el proyecto se queda **Facturable** (el check por defecto se
   conserva; solo se quita al elegir una actividad no facturable).

---

## Nota de criterio (a confirmar)

En el paso 6 se ha interpretado que un proyecto **sin** Productividad debe **conservar**
el check Facturable por defecto (asi la regla "crear facturable por defecto" tiene
sentido). Solo se desmarca cuando se elige una actividad **no** facturable.

Si prefieres el criterio estricto —*sin Productividad tambien se desmarca*— es un cambio
de una linea en `models/project_project.py`: quitar la condicion `and productivity` del
metodo `_zambudio_sync_billable_from_productivity`. Dime y lo ajusto.
