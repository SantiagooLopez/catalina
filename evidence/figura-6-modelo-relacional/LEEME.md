# Figura 6 · modelo relacional desde PostgreSQL

Se consultaron pg_class, pg_namespace, pg_attribute, pg_attrdef y pg_constraint del
servidor catalina-server en una transacción de solo lectura. No se consultaron registros
de usuarios ni se modificaron datos, tablas o restricciones.

`esquema-postgresql-original.json` contiene las columnas y restricciones del esquema
catalina obtenidas en esa consulta. El diagrama representa siete tablas principales y
un subconjunto de sus atributos para mantenerlo legible. Se preservan los tipos reales,
claves primarias, claves foráneas y nulabilidad.

IMPORTANTE: PostgreSQL no tiene una tabla roles. El rol se almacena en usuarios.rol,
varchar(50), NOT NULL. El recuadro punteado del diagrama es una anotación del atributo,
no una entidad física ni una relación FK roles -> usuarios. Si el texto del informe
describe esa tabla como implementada, debe corregirse para coincidir con la base real.

Relaciones verificadas:
- conversaciones.usuario_id -> usuarios.id (obligatoria).
- mensajes.conversacion_id -> conversaciones.id (obligatoria).
- versiones_documentos.documento_id -> documentos.id (admite NULL).
- trabajos_ingesta.version_documento_id -> versiones_documentos.id (obligatoria).
- ejecuciones_indexacion.version_documento_id -> versiones_documentos.id (obligatoria).
- ejecuciones_indexacion.trabajo_ingesta_id -> trabajos_ingesta.id (admite NULL).
- versiones_documentos.ejecucion_indexacion_activa_id -> ejecuciones_indexacion.id
  (admite NULL; no tiene restricción UNIQUE en las restricciones extraídas).

Cada relación principal se representa con la cardinalidad permitida por la FK y su
nulabilidad. No se presupone que todo padre tenga registros hijos. Las tablas auxiliares
omitidas se enumeran al pie del diagrama. No se afirma que sea el esquema completo.

Archivos:
- figura-6-modelo-relacional.png: imagen para insertar en el informe.
- modelo-relacional.svg: versión vectorial para conservar nitidez al ampliar/imprimir.
- modelo-relacional.mmd: relaciones físicas en Mermaid; la nota de roles está en el SVG.
- esquema-postgresql-original.json: catálogo original de respaldo.

El diagrama fue dibujado a partir de los metadatos reales. No es una captura de pgAdmin
ni una exportación de una herramienta ER de PostgreSQL.

Pie sugerido:
Figura 6. Modelo relacional implementado del núcleo de Catalina, obtenido del catálogo
de PostgreSQL. Los roles se almacenan en el atributo usuarios.rol.
Fuente: elaboración propia a partir de la base PostgreSQL del prototipo Catalina (2026).
