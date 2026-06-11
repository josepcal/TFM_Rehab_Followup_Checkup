-- Rol de runtime de la app (no superusuario, no dueño de tablas => la RLS le aplica).
-- Los GRANT los pone la migración 0001.
CREATE ROLE ftm_app LOGIN PASSWORD 'ftm';
