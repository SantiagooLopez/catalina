# Catalina Web — primera entrega de Fase 10

Base revisada: feature/professional-api, commit e40b73b.
Frontend React + TypeScript + Vite. No requiere cambios al backend para las funciones incluidas.

## Windows / PowerShell

Copia la carpeta `frontend` de este paquete dentro de la raíz de tu repositorio `catalina`.
Debe quedar `catalina/frontend/web/package.json`.

Desde esa raíz:

```powershell
Set-Location frontend\web
Copy-Item .env.example .env
npm.cmd ci
npm.cmd run dev
```

Abre http://localhost:5173 . Mantén la terminal abierta. Ctrl+C detiene Vite.
Si no tienes una copia local del repositorio, también puedes extraer este paquete y ejecutar
los mismos comandos desde la carpeta que contiene `frontend`.

La dirección de Debian se configura en `.env`:

```dotenv
CATALINA_API_TARGET=https://192.168.20.140
CATALINA_ALLOW_SELF_SIGNED=true
```

Reinicia Vite después de cambiar `.env`. `CATALINA_ALLOW_SELF_SIGNED=true` es solo para el
certificado autofirmado del servidor de desarrollo; con un certificado confiable usa `false`.
No pongas contraseñas ni tokens en el archivo. Vite escucha solo en la interfaz local.
El navegador llama `/api/v1`; el proxy de Vite reenvía al Debian, evitando cambios de CORS.

## Qué incluye

- Portal propio inspirado en la referencia institucional, con azul y dorado.
- Avatar provisional vectorial; no incluye aún el escudo ni el logo definitivo de Catalina.
- Widget flotante y vista ampliada en `#/chat`, conservando la conversación al alternar.
- Login real contra `/api/v1/auth/login`, con una cuenta ya existente en Catalina.
- Tokens solamente en memoria; se vuelve a iniciar sesión al recargar la página.
- Renovación automática de tokens y cierre de sesión remoto.
- Crear, listar, buscar por título, abrir, renombrar y eliminar conversaciones.
- Paginación completa al leer conversaciones y mensajes.
- Conversación general y preguntas institucionales contra `/api/v1/answers`, con estado
  de espera y errores explícitos. El backend decide cuándo consultar documentos.
- Fuentes devueltas por la API: documento, versión, página y sección.
- Modo claro/oscuro, diseño adaptable, etiquetas accesibles y foco de teclado visible.
- Indicador de conectividad de la API en la barra lateral de la vista ampliada.

## Limitaciones explícitas

- La API actual exige sesión para preguntar: el widget puede abrirse sin sesión, pero
  la consulta necesita login. No hay autorregistro en el contrato actual.
- `/conversations/{id}/messages` no devuelve citas. Las citas de respuestas nuevas se
  conservan en memoria durante la sesión; al recargar no es posible reconstruirlas.
- No hay endpoint de descarga pública de documentos en el contrato recibido. Por eso
  las fuentes no ofrecen descargas ficticias.
- Los mensajes se muestran como texto, sin interpretar HTML recibido del modelo.
- La sesión no se comparte entre pestañas; la preferencia visual sí se guarda localmente.
- Mapa interactivo, adjuntos/OCR, panel administrativo, Microsoft y logo final son etapas
  siguientes. Los accesos de sedes y reglamentos preparan preguntas para el chat.
- El backend recupera contexto reciente de la conversación: por defecto hasta ocho
  intercambios y 8000 caracteres. Esto permite continuar un tema sin entrenar el modelo;
  no es memoria permanente ni se comparte entre conversaciones.
- Las fuentes tipográficas usan Google Fonts; si no hay Internet se usa sans-serif local.

## Comprobación en tu computador

1. Abre el portal y el widget; amplíalo con el botón de la cabecera.
2. En la barra lateral confirma que aparece “API conectada”.
3. Ingresa con la cuenta que ya utilizas para probar el login en Swagger.
4. Pregunta algo presente en tus documentos, por ejemplo sobre registro académico.
5. Comprueba la respuesta y abre “Consultar fuentes”.
6. Crea otro chat; vuelve al anterior desde el historial.
7. Prueba renombrar y eliminar una conversación de prueba.
8. Cambia el tema y revisa la vista con una ventana angosta.
9. Cierra sesión. No compartas credenciales ni tokens al reportar errores.

Si falla la conexión, confirma que Swagger abre desde ese mismo PC y que `.env` tiene
la dirección correcta. Revisa la terminal de Vite. Un error 401 indica autenticación;
403 indica permisos; 429 indica límite de solicitudes. Después de un timeout de una
pregunta, abre nuevamente la conversación antes de reenviar para evitar duplicados.

## Validación realizada

`npm run build`: TypeScript y compilación de producción correctos.
`npm test`: tres pruebas con API simulada que cubren contrato de login/preguntas/logout,
paginación, renovación concurrente de tokens, sesión vencida y propagación de errores.
No se probó contra el Debian privado ni se realizó QA visual en navegador en el entorno
de creación. La prueba de integración real debe realizarse desde tu red.

```powershell
npm.cmd test
npm.cmd run build
```

`dist` es la salida para Nginx en una fase posterior. El proxy Vite es solo de desarrollo:
antes de desplegar hay que configurar Nginx para servir `dist` y conservar `/api/v1` hacia
FastAPI. No sobrescribas la configuración actual de Nginx sin revisarla.
