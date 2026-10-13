# Informe de incidentes — Terminal Rescue

Diagnóstico y reparación del cierre mensual de afiliados. Cada incidente indica el síntoma
observado, cómo se diagnosticó desde la terminal, los comandos usados, la solución aplicada
y el archivo de `evidence/` con la salida de terminal antes y después del arreglo.

## Incidente 1
- **Síntoma:** `docker compose ps` muestra `cierre-worker  Exited (1)` pocos segundos después de levantar el entorno.
- **Diagnóstico:** el log del worker reporta `CIE-1107 WORKER_INTERVAL_SECONDS debe ser un entero de segundos; valor recibido: '30s'`. En `.env.example` la variable traía el sufijo `s` y `worker.py` hace `int()` sobre el valor, por eso termina con código 1.
- **Comandos:** `docker compose ps -a`, `docker compose logs cierre-worker | tail -5`, `grep WORKER_INTERVAL_SECONDS .env.example`
- **Solución:** `WORKER_INTERVAL_SECONDS=30` (entero, sin unidad) en `.env.example` y `.env`; `docker compose up -d` y el worker queda `Up` conciliando cada 30 s.
- **Evidencia:** evidence/01-worker.txt

## Incidente 2
- **Síntoma:** `curl http://localhost:8081/afiliados/1098765432` responde `503 {"error": "base de datos no disponible"}`.
- **Diagnóstico:** el log de la API muestra `CIE-2210 ... could not translate host name "cierre-database"`. Entre contenedores el host es el nombre del servicio de `docker-compose.yml` (`cierre-db`); `cierre-database` no existe en la red de Compose.
- **Comandos:** `curl -s -w "%{http_code}" http://localhost:8081/afiliados/1098765432`, `docker compose logs cierre-api | grep CIE-2210`, `grep DATABASE_HOST .env.example`, `docker compose config --services`
- **Solución:** `DATABASE_HOST=cierre-db` en `.env.example` y `.env`; tras `docker compose up -d` la API responde 200 con los datos del afiliado.
- **Evidencia:** evidence/02-api-db.txt

## Incidente 3
- **Síntoma:** `./run.sh` termina con código 2: `awk: fatal: cannot open file /opt/cierre/entrada/AFI_MAE.csv`.
- **Diagnóstico:** `scripts/cierre.sh` usaba la ruta del servidor antiguo `/opt/cierre/entrada`, que no existe; con `find` se ubicó el archivo real en `data/`. Además `run.sh`, `reset.sh`, `scripts/cierre.sh` y `validator` estaban versionados con modo 100644 (sin permiso de ejecución).
- **Comandos:** `bash ./run.sh`, `grep -n ENTRADA= scripts/cierre.sh`, `find . -name "AFI_MAE.csv"`, `git ls-files -s run.sh`, `chmod +x run.sh reset.sh scripts/cierre.sh validator`
- **Solución:** `ENTRADA=data` en el script de cierre y permiso de ejecución (`chmod +x` y `git update-index --chmod=+x`) para todos los scripts; `./run.sh` termina con código 0.
- **Evidencia:** evidence/03-entrada-cierre.txt

## Incidente 4
- **Síntoma:** los tres logs suman 11 515 líneas con miles de errores y no se sabía cuál era el más frecuente.
- **Diagnóstico:** se extrajeron los códigos `CIE-####` de los tres logs (los `W-###` son avisos, no errores) y se contaron. El más frecuente es `CIE-4012` (lote rechazado por afiliado sin empresa) con 1424 ocurrencias: 1068 en `worker.log` y 356 en `api.log`.
- **Comandos:** `wc -l logs/*.log`, `grep -ohE "CIE-[0-9]{4}" logs/*.log | sort | uniq -c | sort -rn`, `grep -c CIE-4012 logs/*.log`
- **Solución:** `scripts/cierre.sh` calcula el conteo con `grep | sort | uniq -c | sort` y escribe `output/top_error.txt` con `codigo_error=CIE-4012` y `ocurrencias=1424`.
- **Evidencia:** evidence/04-top-error.txt

## Incidente 5
- **Síntoma:** la base tenía 1520 registros para 1500 documentos, estados distintos de A/I, activos sin empresa y beneficiarios sin afiliado.
- **Diagnóstico:** con `psql` se contaron 20 documentos duplicados, 14 afiliados con `EST_AFI` inválido (`Z`, `P`, `9`, `X`), 18 activos con `COD_EMP` vacío o inexistente y 15 beneficiarios huérfanos; `uniq -d` confirmó los duplicados en el CSV.
- **Comandos:** `docker compose exec cierre-db psql -U cierre -d cierre -c "SELECT count(*), count(DISTINCT nro_doc) FROM afi_mae"`, `cut -d, -f1 data/AFI_MAE.csv | sort | uniq -d | wc -l`, `cut -d, -f2 output/excepciones.csv | sort | uniq -c`
- **Solución:** `db/init/03_limpieza.sql` elimina los duplicados en la base conservando la primera aparición (queda 1500/1500). Lo irreparable se reporta en `output/excepciones.csv` como `DUPLICADO`, `CODIGO_INVALIDO`, `SIN_EMPRESA` y `BENEFICIARIO_HUERFANO`, y se excluye de los activos según el diccionario.
- **Evidencia:** evidence/05-calidad-datos.txt

## Incidente 6
- **Síntoma:** `GET /afiliados/3756530718` responde `500 {"error": "error interno"}`; `api.log` registra 700 errores `CIE-5003`.
- **Diagnóstico:** el traceback de `docker compose logs cierre-api` muestra `TypeError: can only concatenate str (not "NoneType")`: 588 afiliados no tienen segundo nombre o apellido (NULL). También fallaban los estados inválidos (`KeyError`) y el `JOIN` devolvía 404 para afiliados sin empresa.
- **Comandos:** `docker compose logs cierre-api | grep -A8 CIE-5003`, `grep -c CIE-5003 logs/api.log`, `awk -F, 'NR>1 && ($4=="" || $6=="")' data/AFI_MAE.csv | wc -l`, `docker compose up -d --build cierre-api`
- **Solución:** en `services/api/app.py` el nombre se arma solo con las partes no vacías, el estado usa `ESTADOS.get()` y la consulta usa `LEFT JOIN empresa`. La API responde 200 con datos correctos y 404 para documentos inexistentes.
- **Evidencia:** evidence/06-api-500.txt

## Incidente 7
- **Síntoma:** el worker registra 298 errores `CIE-3301` (fecha con formato no soportado) y `FEC_AFI` trae varios formatos.
- **Diagnóstico:** con `sed` se agruparon los patrones de fecha: además de `YYYY-MM-DD` hay `DD/MM/YYYY`, `YYYYMMDD` y valores que no son fechas reales (`2025-02-30`, `31/13/2024`, `SIN FECHA`, `N/A`, `15-15-2019`, `2023/02/29`, `00000000`).
- **Comandos:** `grep -c CIE-3301 logs/worker.log`, `awk -F, 'NR>1{print $9}' data/AFI_MAE.csv | sed -E 's/[0-9]/9/g' | sort | uniq -c`, `psql` con conteo de formatos de `fec_afi`
- **Solución:** `scripts/procesar_cierre.py` y `db/init/03_limpieza.sql` normalizan `DD/MM/YYYY` y `YYYYMMDD` a `YYYY-MM-DD`; las 12 fechas imposibles se reportan como `FECHA_INVALIDA` y el afiliado sigue contando en los totales.
- **Evidencia:** evidence/07-fechas.txt

## Incidente 8
- **Síntoma:** el extracto de Caja Oriente no se cruzaba: usa separador `;`, documentos de 12 dígitos con ceros a la izquierda y situación `VIGENTE`/`RETIRADO`.
- **Diagnóstico:** comparando encabezados con `head` y contando situaciones con `cut | sort | uniq -c` se identificaron las diferencias de formato frente a `AFI_MAE.csv`.
- **Comandos:** `head -3 data/extracto_caja_oriente.csv`, `cut -d";" -f3 data/extracto_caja_oriente.csv | sort | uniq -c`, `grep -c CRUCE_NO_COINCIDE output/excepciones.csv`
- **Solución:** el cierre quita los ceros a la izquierda, mapea `VIGENTE=A` y `RETIRADO=I` y reporta 25 casos `CRUCE_NO_COINCIDE` (documento inexistente o estado distinto). `afiliados_activos.csv` conserva su encabezado del contrato.
- **Evidencia:** evidence/08-cruce-oriente.txt

## Incidente 9
- **Síntoma:** `output/totales.txt` no traía `inactivos` ni `excepciones` y el conteo directo del CSV (1225 A, 281 I) no cuadraba con la hoja de control.
- **Diagnóstico:** el conteo con `awk | sort | uniq -c` incluía duplicados y no excluía códigos inválidos ni activos sin empresa, como exigen las reglas del diccionario.
- **Comandos:** `cat control/hoja_control.csv`, `awk -F, 'NR>1{print $7}' data/AFI_MAE.csv | sort | uniq -c`, `tail -n +2 output/excepciones.csv | wc -l`, `diff` contra la hoja de control
- **Solución:** los totales se calculan sobre documentos distintos: `total_afiliados=1500`, `activos=1194`, `inactivos=274` (iguales a la hoja de control) y `excepciones=104` (líneas de `excepciones.csv`).
- **Evidencia:** evidence/09-totales.txt

## Incidente 10
- **Síntoma:** la segunda ejecución de `./run.sh` fallaba con `mkdir: output: File exists` y la primera movía `AFI_MAE.csv` a `data/procesados/`.
- **Diagnóstico:** `grep` sobre `scripts/cierre.sh` mostró `mkdir $SALIDA` sin `-p` y un `mv` del archivo de entrada al final del cierre.
- **Comandos:** `./run.sh` dos veces, `grep -nE "mkdir|mv " scripts/cierre.sh`, `md5sum output/*`, `./reset.sh`
- **Solución:** el cierre ya no modifica `data/`, recrea `output/` con `rm -rf` y `mkdir -p`, y genera salidas determinísticas: dos ejecuciones seguidas y una tras `./reset.sh` producen archivos idénticos (mismo md5).
- **Evidencia:** evidence/10-repetible.txt
