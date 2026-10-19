# Temas y revisión visual

`src/theme.css` define los tokens compartidos y las superficies de los temas claro y
oscuro. Se importa después de los estilos iniciales para impedir que los colores fijos del
portal sobrescriban los textos, formularios o paneles oscuros. Las reglas del mapa oscuro
usan el selector del tema para mantenerse al cargar la vista de forma diferida.

El plano conserva una sola geometría: `public/maps/campus-plan.svg`. Cada compilación
genera su variante oscura con `scripts/build-map-themes.mjs`. Al cambiar de tema, el mapa
cambia la imagen sin reinicializar los marcadores ni perder la selección.

Validación realizada: compilación TypeScript/Vite, pruebas de la API del frontend y revisión
en Chrome de acceso, bienvenida, mapa y vista móvil con sesión simulada y directorio real.
Se midieron 18 textos y controles del tema oscuro: contraste mínimo observado 6,68:1.
Es una comprobación de esos elementos, no una auditoría completa de accesibilidad.
También se comprobó el cambio de plano entre temas y la ausencia de desbordamiento móvil.

Mantener los fondos blancos de las ilustraciones originales del personaje y del logo
institucional: forman parte de los recursos recibidos, no son superficies de formulario.
