BEGIN;

-- ============================================================
-- Catalina
-- Migración: 7.3.0
-- Descripción: modelo de autenticación y sesiones
-- ============================================================

-- ------------------------------------------------------------
-- 1. Evolución de usuarios
-- ------------------------------------------------------------

ALTER TABLE catalina.usuarios
    ADD COLUMN email VARCHAR(320);

ALTER TABLE catalina.usuarios
    ADD COLUMN nombre VARCHAR(160);

ALTER TABLE catalina.usuarios
    ADD COLUMN password_hash TEXT;

ALTER TABLE catalina.usuarios
    ADD COLUMN fecha_actualizacion TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE catalina.usuarios
    ADD COLUMN ultimo_acceso TIMESTAMPTZ;

-- La tabla está vacía al momento de esta migración,
-- por lo que podemos convertir estos campos en obligatorios.

ALTER TABLE catalina.usuarios
    ALTER COLUMN email SET NOT NULL;

ALTER TABLE catalina.usuarios
    ALTER COLUMN nombre SET NOT NULL;

ALTER TABLE catalina.usuarios
    ALTER COLUMN password_hash SET NOT NULL;

-- Email único sin distinguir mayúsculas/minúsculas.
CREATE UNIQUE INDEX uq_usuarios_email_normalizado
    ON catalina.usuarios (LOWER(email));

CREATE INDEX idx_usuarios_activo
    ON catalina.usuarios (activo);

CREATE INDEX idx_usuarios_rol
    ON catalina.usuarios (rol);


-- ------------------------------------------------------------
-- 2. Sesiones de autenticación
-- ------------------------------------------------------------

CREATE TABLE catalina.sesiones_auth (
    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    usuario_id INTEGER NOT NULL,

    refresh_token_hash TEXT NOT NULL,

    fecha_creacion TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    fecha_expiracion TIMESTAMPTZ
        NOT NULL,

    fecha_revocacion TIMESTAMPTZ,

    ultima_rotacion TIMESTAMPTZ,

    ip INET,

    user_agent TEXT,

    CONSTRAINT sesiones_auth_usuario_id_fkey
        FOREIGN KEY (usuario_id)
        REFERENCES catalina.usuarios(id)
        ON DELETE CASCADE,

    CONSTRAINT ck_sesiones_auth_expiracion
        CHECK (
            fecha_expiracion > fecha_creacion
        )
);

CREATE INDEX idx_sesiones_auth_usuario
    ON catalina.sesiones_auth (usuario_id);

CREATE INDEX idx_sesiones_auth_expiracion
    ON catalina.sesiones_auth (fecha_expiracion);

CREATE INDEX idx_sesiones_auth_activas
    ON catalina.sesiones_auth (
        usuario_id,
        fecha_expiracion
    )
    WHERE fecha_revocacion IS NULL;


-- ------------------------------------------------------------
-- 3. Registrar la migración
-- ------------------------------------------------------------

INSERT INTO catalina.migraciones_esquema (
    version,
    descripcion
)
VALUES (
    '7.3.0',
    'Modelo de autenticación, credenciales y sesiones'
);

COMMIT;
