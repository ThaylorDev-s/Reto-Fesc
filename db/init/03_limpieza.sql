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
