BEGIN;

-- ============================================================
-- Catalina
-- Migración: 7.4.0
-- Descripción: modelo profesional de conversaciones y mensajes
-- ============================================================

-- ------------------------------------------------------------
-- CONVERSACIONES
-- ------------------------------------------------------------

ALTER TABLE catalina.conversaciones
    ADD COLUMN titulo VARCHAR(160)
        NOT NULL
        DEFAULT 'Nueva conversación',
    ADD COLUMN fecha_actualizacion TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE catalina.conversaciones
    ALTER COLUMN usuario_id SET NOT NULL;

ALTER TABLE catalina.conversaciones
    ALTER COLUMN fecha_inicio DROP DEFAULT;

ALTER TABLE catalina.conversaciones
    ALTER COLUMN fecha_inicio TYPE TIMESTAMPTZ
    USING fecha_inicio AT TIME ZONE 'UTC';

ALTER TABLE catalina.conversaciones
    ALTER COLUMN fecha_inicio
        SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN fecha_inicio
        SET NOT NULL;

ALTER TABLE catalina.conversaciones
    ADD CONSTRAINT chk_conversaciones_titulo_no_vacio
    CHECK (BTRIM(titulo) <> '');

CREATE INDEX idx_conversaciones_usuario_actualizacion
    ON catalina.conversaciones (
        usuario_id,
        fecha_actualizacion DESC,
        id DESC
    );

-- ------------------------------------------------------------
-- MENSAJES
-- ------------------------------------------------------------

ALTER TABLE catalina.mensajes
    ALTER COLUMN conversacion_id SET NOT NULL,
    ALTER COLUMN pregunta SET NOT NULL,
    ALTER COLUMN respuesta SET NOT NULL;

ALTER TABLE catalina.mensajes
    ALTER COLUMN fecha DROP DEFAULT;

ALTER TABLE catalina.mensajes
    ALTER COLUMN fecha TYPE TIMESTAMPTZ
    USING fecha AT TIME ZONE 'UTC';

ALTER TABLE catalina.mensajes
    ALTER COLUMN fecha
        SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN fecha
        SET NOT NULL;

ALTER TABLE catalina.mensajes
    ADD CONSTRAINT chk_mensajes_pregunta_no_vacia
    CHECK (BTRIM(pregunta) <> '');

ALTER TABLE catalina.mensajes
    ADD CONSTRAINT chk_mensajes_respuesta_no_vacia
    CHECK (BTRIM(respuesta) <> '');

ALTER TABLE catalina.mensajes
    DROP CONSTRAINT mensajes_conversacion_id_fkey;

ALTER TABLE catalina.mensajes
    ADD CONSTRAINT mensajes_conversacion_id_fkey
    FOREIGN KEY (conversacion_id)
    REFERENCES catalina.conversaciones(id)
    ON DELETE CASCADE;

CREATE INDEX idx_mensajes_conversacion_fecha
    ON catalina.mensajes (
        conversacion_id,
        fecha ASC,
        id ASC
    );

-- ------------------------------------------------------------
-- REGISTRO DE MIGRACIÓN
-- ------------------------------------------------------------

INSERT INTO catalina.migraciones_esquema (
    version,
    descripcion
)
VALUES (
    '7.4.0',
    'Modelo profesional de conversaciones y mensajes'
);

COMMIT;
