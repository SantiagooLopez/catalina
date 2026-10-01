BEGIN;

-- ============================================================
-- Catalina
-- Migración: 7.3.1
-- Descripción: índice único para búsqueda segura de refresh tokens
-- ============================================================

CREATE UNIQUE INDEX uq_sesiones_auth_refresh_token_hash
    ON catalina.sesiones_auth (refresh_token_hash);

INSERT INTO catalina.migraciones_esquema (
    version,
    descripcion
)
VALUES (
    '7.3.1',
    'Índice único para búsqueda de sesiones por refresh token'
);

COMMIT;
