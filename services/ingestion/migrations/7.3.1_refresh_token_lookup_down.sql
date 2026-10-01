BEGIN;

DROP INDEX IF EXISTS
    catalina.uq_sesiones_auth_refresh_token_hash;

DELETE FROM catalina.migraciones_esquema
WHERE version = '7.3.1';

COMMIT;
