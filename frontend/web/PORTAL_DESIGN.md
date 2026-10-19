# Portal Catalina

La composición favorece un recorrido de lectura en F: identificación y navegación en la
primera franja, mensaje y acción principal alineados a la izquierda, una segunda franja de
servicios y títulos de sección en el mismo eje. No se presupone que todas las personas
lean con un patrón idéntico: los títulos, enlaces y botones también permiten navegación
directa por teclado y lectores de pantalla.

La portada utiliza azul marino y azul institucional como base, cian para énfasis y dorado
para acciones principales. Las secciones alternan superficies azules suaves; las tarjetas
mantienen una superficie clara o su equivalente oscuro. Las familias DM Sans y Manrope
conservan continuidad con el chat. El portal tiene un enlace para saltar al contenido,
un h1, secciones con títulos identificables y menú móvil con estado aria-expanded.

`public/brand/campus-editorial.png` es una ilustración conceptual generada para este portal,
no una fotografía de las instalaciones de la universidad. La portada lo identifica así.
La imagen es decorativa; títulos y acciones están en HTML. El logo institucional y las
cinco imágenes de Catalina siguen siendo los recursos aportados por el usuario.

Flujos conservados: consulta rápida sin sesión, pregunta sugerida que rellena el chat,
acceso autenticado al espacio ampliado y al mapa, historial y cambio de tema.

Verificación: compilación TypeScript/Vite y pruebas del frontend; revisión en Chrome a
390, 768 y 1440 píxeles sin desbordamiento horizontal, menú móvil, sugerencias del portal,
requisito de sesión para mapa y cambio de tema. Se revisaron también el chat y el mapa
para evitar que los estilos del portal alteren sus superficies.
