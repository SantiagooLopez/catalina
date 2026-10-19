# Mapa de referencia del campus

La vista ampliada incluye las pestañas Conversación y Mapa del campus. Requiere iniciar
sesión en la interfaz, igual que el chat ampliado; el directorio de ubicaciones es público.
Una respuesta de ubicación incluye identificadores y abre el mapa en la vista ampliada.
En el widget pequeño ofrece tarjetas para abrirlo y solicita sesión al ampliar.

## Datos y precisión

La fuente única está en
`services/ingestion/src/catalina_ingestion/data/campus_locations.json`.
Las direcciones proceden de las páginas institucionales enlazadas en cada ficha. El plano
vectorial propio está en `public/maps/campus-plan.svg`: representa las calles y edificios
como un esquema sin escala. Las posiciones se expresan como fracciones de ese plano;
**no son coordenadas GPS ni puertas de acceso verificadas**. Leaflet permite desplazarlo,
acercarlo y seleccionar marcadores. No se descargan mosaicos ni se usa una API de pago.
La captura original se utilizó como referencia de distribución, no como fondo del mapa.

El plano sigue los bloques trazados por el usuario: 1 Sede 4 (1.1 Biblioteca, 1.2 Auditorio),
2 Carrera 13 (2.1 Lenguas), 3 Las Torres (3.1 Psicología, 3.2 Derecho, 3.3 Polideportivo),
4 Liceo (dos bloques) y 5 El Claustro (5.1 Servicios Psicológicos, 5.2 Capilla).
Las áreas completas son polígonos seleccionables. El Polideportivo incluye una cancha
dibujada. Todas las sedes usan una paleta neutra con límites discretos; árboles, patios y
volúmenes ilustrativos aportan contexto sin representar accesos u oficinas reales.
Caracas y Carrera Séptima se identifican por sus nombres y sus ejes dobles.
Los nombres solo aparecen al pasar el mouse o seleccionar una ubicación. En la vista
general pequeña se muestran los números de sede; acercar el zoom revela las dependencias.
El mapa permite zoom centrado, pero no arrastre, desplazamiento por teclado ni box-zoom.
Las consultas resaltan el punto y su sede sin desplazar el plano automáticamente.

Google Maps se abre mediante enlaces externos de búsqueda o indicaciones basados en las
direcciones publicadas. El sistema no calcula rutas peatonales, distancias o accesos internos.
No hay solicitud de geolocalización del usuario.

Las dependencias pueden heredar la dirección y el marcador de su sede. La ficha lo indica;
no se asignan pisos, oficinas o posiciones nuevas cuando estos datos no están confirmados.
Biblioteca tiene dos resultados y exige elegir sede. Primaria y Bachillerato comparten el
área del Liceo. Registro y Control, Admisiones y Tesorería están en Las Torres. El Consultorio
Jurídico comparte espacio con Derecho, dentro de Las Torres. La herencia de dirección y
marcador recorre toda esa jerarquía. Casa Extensión se retiró del directorio a petición del
usuario. Pisos y oficinas específicos siguen pendientes. También se señalan variantes publicadas
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
