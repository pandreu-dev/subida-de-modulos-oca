# Analisis estandar

No se ha identificado una opcion funcional visible que oculte automaticamente la columna `Total` del PyG solo cuando hay filtro analitico.

No se deja override activo porque sin revisar el codigo exacto de `account_reports` Enterprise instalado puede ser arriesgado:

- Puede descuadrar cabeceras y lineas.
- Puede afectar PDF/XLSX.
- Puede afectar otros informes si Odoo cambia las opciones internas.

Recomendacion: resolverlo con una revision especifica del motor de informes en la BD objetivo o con configuracion estandar si existe.
