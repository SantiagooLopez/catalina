BEGIN;

DROP TABLE IF EXISTS catalina.sesiones_auth;

DROP INDEX IF EXISTS catalina.uq_usuarios_email_normalizado;
DROP INDEX IF EXISTS catalina.idx_usuarios_activo;
DROP INDEX IF EXISTS catalina.idx_usuarios_rol;

ALTER TABLE catalina.usuarios
    DROP COLUMN IF EXISTS ultimo_acceso;

ALTER TABLE catalina.usuarios
    DROP COLUMN IF EXISTS fecha_actualizacion;

ALTER TABLE catalina.usuarios
    DROP COLUMN IF EXISTS password_hash;

ALTER TABLE catalina.usuarios
    DROP COLUMN IF EXISTS nombre;

ALTER TABLE catalina.usuarios
    DROP COLUMN IF EXISTS email;

DELETE FROM catalina.migraciones_esquema
WHERE version = '7.3.0';

COMMIT;
