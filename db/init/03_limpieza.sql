-- Corrección de calidad de datos en la base (se ejecuta después de la carga inicial).
-- Lo reparable se corrige aquí; lo irreparable (estados inválidos, afiliados sin
-- empresa, beneficiarios huérfanos, fechas inválidas) se conserva y el cierre lo
-- reporta en output/excepciones.csv.

-- Duplicados en afi_mae: se conserva la primera aparición de cada documento
DELETE FROM afi_mae a
USING (
    SELECT ctid, row_number() OVER (PARTITION BY nro_doc ORDER BY ctid) AS n
    FROM afi_mae
) d
WHERE a.ctid = d.ctid
  AND d.n > 1;

-- Fechas de afiliación en DD/MM/YYYY o YYYYMMDD se normalizan a YYYY-MM-DD
-- (solo si forman una fecha real; las inválidas se dejan como están y se reportan)
CREATE FUNCTION fecha_segura(anio TEXT, mes TEXT, dia TEXT) RETURNS DATE AS $$
BEGIN
    RETURN make_date(anio::int, mes::int, dia::int);
EXCEPTION WHEN others THEN
    RETURN NULL;  -- fecha imposible (ej. mes 13): no se modifica
END;
$$ LANGUAGE plpgsql;

UPDATE afi_mae
SET fec_afi = fecha_segura(substr(fec_afi, 7, 4), substr(fec_afi, 4, 2), substr(fec_afi, 1, 2))::text
WHERE fec_afi ~ '^\d{2}/\d{2}/\d{4}$'
  AND fecha_segura(substr(fec_afi, 7, 4), substr(fec_afi, 4, 2), substr(fec_afi, 1, 2)) IS NOT NULL;

UPDATE afi_mae
SET fec_afi = fecha_segura(substr(fec_afi, 1, 4), substr(fec_afi, 5, 2), substr(fec_afi, 7, 2))::text
WHERE fec_afi ~ '^\d{8}$'
  AND fecha_segura(substr(fec_afi, 1, 4), substr(fec_afi, 5, 2), substr(fec_afi, 7, 2)) IS NOT NULL;

DROP FUNCTION fecha_segura(TEXT, TEXT, TEXT);
