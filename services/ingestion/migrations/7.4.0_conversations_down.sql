BEGIN;

DROP INDEX IF EXISTS
    catalina.idx_mensajes_conversacion_fecha;

ALTER TABLE catalina.mensajes
    DROP CONSTRAINT IF EXISTS
        chk_mensajes_respuesta_no_vacia;

ALTER TABLE catalina.mensajes
    DROP CONSTRAINT IF EXISTS
        chk_mensajes_pregunta_no_vacia;

ALTER TABLE catalina.mensajes
    DROP CONSTRAINT
        mensajes_conversacion_id_fkey;

ALTER TABLE catalina.mensajes
    ADD CONSTRAINT mensajes_conversacion_id_fkey
    FOREIGN KEY (conversacion_id)
    REFERENCES catalina.conversaciones(id);

ALTER TABLE catalina.mensajes
    ALTER COLUMN fecha DROP DEFAULT;

ALTER TABLE catalina.mensajes
    ALTER COLUMN fecha TYPE TIMESTAMP WITHOUT TIME ZONE
    USING fecha AT TIME ZONE 'UTC';

ALTER TABLE catalina.mensajes
    ALTER COLUMN fecha
        SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN fecha
        DROP NOT NULL,
    ALTER COLUMN conversacion_id
        DROP NOT NULL,
    ALTER COLUMN pregunta
        DROP NOT NULL,
    ALTER COLUMN respuesta
        DROP NOT NULL;

DROP INDEX IF EXISTS
    catalina.idx_conversaciones_usuario_actualizacion;

ALTER TABLE catalina.conversaciones
    DROP CONSTRAINT IF EXISTS
        chk_conversaciones_titulo_no_vacio;

ALTER TABLE catalina.conversaciones
    ALTER COLUMN fecha_inicio DROP DEFAULT;

ALTER TABLE catalina.conversaciones
    ALTER COLUMN fecha_inicio
        TYPE TIMESTAMP WITHOUT TIME ZONE
    USING fecha_inicio AT TIME ZONE 'UTC';

ALTER TABLE catalina.conversaciones
    ALTER COLUMN fecha_inicio
        SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN fecha_inicio
        DROP NOT NULL,
    ALTER COLUMN usuario_id
        DROP NOT NULL;

ALTER TABLE catalina.conversaciones
    DROP COLUMN fecha_actualizacion,
    DROP COLUMN titulo;

DELETE FROM catalina.migraciones_esquema
WHERE version = '7.4.0';

COMMIT;
