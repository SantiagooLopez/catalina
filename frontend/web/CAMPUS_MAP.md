# Mapa de referencia del campus

La vista ampliada incluye las pestañas Conversación y Mapa del campus. Requiere iniciar
sesión en la interfaz, igual que el chat ampliado; el directorio de ubicaciones es público.
Una respuesta de ubicación incluye identificadores y abre el mapa en la vista ampliada.
En el widget pequeño ofrece tarjetas para abrirlo y solicita sesión al ampliar.

## Datos y precisión

La fuente única está en
`services/ingestion/src/catalina_ingestion/data/campus_locations.json`.
Las direcciones proceden de las páginas institucionales enlazadas en cada ficha. Las
posiciones de referencia se expresan como fracciones de la captura aportada por el usuario;
**no son coordenadas GPS ni puertas de acceso verificadas**. La imagen es una referencia
estática de Google Maps y no se actualiza en vivo. Leaflet permite desplazarla, acercarla y
seleccionar marcadores; no se descargan mosaicos de Google ni se usa su API de pago.

Google Maps se abre mediante enlaces externos de búsqueda o indicaciones basados en las
direcciones publicadas. El sistema no calcula rutas peatonales, distancias o accesos internos.
No hay solicitud de geolocalización del usuario.

Las dependencias pueden heredar la dirección y el marcador de su sede. La ficha lo indica;
no se asignan pisos, oficinas o posiciones nuevas cuando estos datos no están confirmados.
Biblioteca tiene dos resultados y exige elegir sede. El Liceo visible en la captura queda
pendiente de identificar como primaria o bachillerato. También se señalan variantes publicadas
para los accesos de El Claustro y Carrera 13.

## Completar ubicaciones

Para cada dependencia, confirmar: nombre, sede, piso/oficina si aplica, dirección/entrada,
punto sobre la referencia y fuente. `reference_point` usa x e y entre 0 y 1 desde la esquina
superior izquierda. Mantenerlo en null/ausente si el punto no está confirmado. Usar `parent_id`
para vincular una oficina con su sede y explicar en `note` cualquier incertidumbre.

Actualizar el JSON, ejecutar las pruebas y desplegar el backend; recargar la página para
actualizar el catálogo en el navegador. La carpeta de datos se incluye como package-data.
El navegador solo puede consultar el directorio: no puede modificar las ubicaciones.

## Consultas

- `GET /api/v1/campus/locations`: catálogo público y referencias resueltas.
- `POST /api/v1/campus/query`: pregunta y `selected_id` opcional para consultar la sede activa.
- `/answers` y `/guest/answers` incluyen `locations` cuando existe una coincidencia de ubicación.

Las consultas directas de ubicación se resuelven desde este catálogo y se identifican como
Directorio del campus. Las preguntas sobre servicios o reglamentos siguen el flujo documental
normal. El pequeño chat del mapa usa exclusivamente el directorio y no inventa horarios,
teléfonos, distancias ni distribuciones interiores. Las continuaciones en el chat principal
pueden reformularse con Ollama y consultar de nuevo el directorio.

Leaflet se carga al abrir la vista del mapa para mantener ligero el widget del portal.
