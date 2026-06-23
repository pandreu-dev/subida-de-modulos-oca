# AUNNA Portal Iframe Example

Modulo de prueba que anade una entrada en la pagina principal del portal de usuario (`/my`) y abre una pagina propia con un iframe.

## Funcionamiento

- Hereda la plantilla `portal.portal_my_home`.
- Inserta una entrada clicable en el portal del usuario.
- Crea la ruta `/my/iframe-example`.
- El iframe usa Google Maps como ejemplo, sin clave API.

## Prueba

1. Actualizar la lista de aplicaciones.
2. Instalar `AUNNA Portal Iframe Example`.
3. Entrar con un usuario de portal.
4. Abrir `/my`.
5. Comprobar que aparece la entrada `Ejemplo iframe`.
6. Hacer clic en la entrada y comprobar que se abre la pagina con el iframe cargado.
