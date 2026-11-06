# Evidencias y entregables de Catalina

Este directorio conserva las capturas, diagramas, documentos de apoyo, resultados de evaluación y presentaciones desarrollados para el prototipo.

## Entregables actuales

- [Presentación organizada por objetivos](sustentacion/output/Catalina-sustentacion-reorganizada.pptx): versión más reciente, 31 diapositivas. Las demás presentaciones se conservan como versiones de trabajo anteriores y pueden contener resultados o contenidos ya reemplazados.
- [GIF del recorrido funcional](sustentacion/output/Catalina-recorrido-funcional.gif): montaje en bucle de capturas reales existentes, no una grabación nueva ni una medición de latencia.
- [Resultados agregados del piloto](sustentacion/piloto/resultados-verificados.json): 30 participantes. Las dos preguntas globales tienen 25 respuestas válidas cada una. No se incluyen las respuestas individuales del Excel original.
- [Requerimientos](requerimientos-catalina/).
- [Anexo de evaluación RAG](anexo-x-evaluacion-rag/).
- Diagramas editables: [modelo relacional](figura-6-modelo-relacional/), [PostgreSQL y Qdrant](postgresql-qdrant/), [autenticación](figura-8-autenticacion/) y [versionamiento documental](figura-9-version-documental/).

## Interpretación de las evaluaciones

Cada corrida debe interpretarse con su fecha, configuración y alcance. El challenge histórico guardado y las métricas reportadas en el documento de grado corresponden a ejecuciones diferentes. No deben combinarse. La presentación identifica las cifras tomadas del documento entregado.

Las pausas visuales del frontend se utilizan para la demostración y no representan el tiempo de inferencia de Ollama ni el tiempo medido de recuperación.

Verificación del código antes de esta publicación: 512 pruebas del backend aprobadas (2 advertencias de dependencias), 3 pruebas del frontend aprobadas y compilación TypeScript/Vite correcta.

## Alcance del respaldo

Git conserva código y entregables, pero no sustituye un respaldo operativo de PostgreSQL, Qdrant, documentos cargados o modelos de Ollama. No se publican claves SSH, variables `.env`, contraseñas, sesiones ni archivos temporales de renderizado.
