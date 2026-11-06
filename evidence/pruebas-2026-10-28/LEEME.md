# Resultados de ejecución de pruebas · Catalina

Ejecución del 28 de octubre de 2026:

- Backend: suite completa configurada en tests/, 502 passed, 2 warnings, sin fallos.
- Frontend: suite completa npm test (Node test runner), 3 pass, 0 fail, 0 skipped.
- Total de casos pytest + Node: 505 aprobados.
- Cuatro programas adicionales de verificación de interfaz completados correctamente.
- Compilación TypeScript y Vite completada correctamente.

Las advertencias del backend son deprecaciones de dependencias Starlette/httpx/anyio;
se conservaron en la salida, no se ocultaron para la evidencia.

## Comandos ejecutados

Backend en Debian, desde /opt/catalina/services/ingestion:

```bash
DATABASE_PASSWORD=testing-password-only .venv/bin/python -m pytest tests -q -ra
```

La variable de contraseña es ficticia y se limita a ese proceso de pruebas. No modifica
la configuración ni las credenciales de producción.

Frontend en Windows, desde catalina/frontend/web:

```powershell
npm.cmd test
npm.cmd run build
```

Verificaciones desde el directorio de trabajo:

```powershell
node verify-independent.cjs
node verify-f-portal.cjs
node verify-themes.cjs
node verify-campus-ui.cjs --live
```

Las verificaciones de navegador usan sesiones/cuentas simuladas donde lo indica cada
programa; el directorio del mapa se consultó contra el backend real en el modo live.
No se crearon cuentas ni conversaciones de prueba en producción.

## Archivos y alcance

Los archivos backend-pytest.txt, frontend-tests.txt, frontend-build.txt y ui-*.txt son
las salidas guardadas directamente durante esta ejecución. resumen-resultados.json
resume sus resultados. Las dos capturas corresponden a los archivos de texto que reúnen
esas salidas, abiertos en el navegador; no son una terminal simulada ni una captura de
una ventana de terminal. Se añadieron encabezados para identificar los programas.

No se incluyen en este total los escenarios manuales históricos de scripts/ que crean,
reindexan o eliminan documentos, ni benchmarks o evaluaciones de corpus. Tampoco se
presenta la compilación como un caso pytest adicional.

Pie sugerido:
Resultados de las suites automatizadas del prototipo Catalina: 502 pruebas del backend
y 3 del frontend aprobadas, con verificaciones complementarias de interfaz y compilación.
Fuente: elaboración propia a partir del prototipo Catalina (2026).
