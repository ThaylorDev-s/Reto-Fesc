# Terminal Rescue — Reto FESC

## Descripción

Sistema reparado del cierre mensual de afiliados de una Caja de Compensación Familiar. Genera el archivo de afiliados activos que usa Subsidios, reporta las excepciones de calidad de datos, cruza el extracto de Caja Oriente y expone una API de consulta de afiliados. El entorno heredado no arrancaba, la API fallaba y los totales no cuadraban con la hoja de control de Operaciones; ahora todo corre en Docker de forma repetible.

## Integrantes

- Mack Thaylor Barbosa Perez
- Alejandro Jaimes Rayon

## Requisitos

- Docker con Docker Compose v2 (probado con Docker 29 y Compose v5).
- Bash, Git y Python 3.8 o superior para `run.sh` y el validador.
- Linux, macOS o Windows con WSL2 (probado en Ubuntu sobre WSL2).

## Instalación y ejecución

Desde una copia limpia del repositorio se crea el archivo de configuración, se levantan los servicios y se ejecuta el cierre:

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
./run.sh
```

Para volver al estado inicial (borra contenedores, volúmenes y `output/`) se usa `./reset.sh` y luego se ejecuta de nuevo `./run.sh`.

## Configuración

Variables de `.env` (se copia de `.env.example`; `.env` no se versiona):

| Variable | Para qué sirve | Ejemplo |
|---|---|---|
| `POSTGRES_DB` | Nombre de la base que crea el contenedor `cierre-db` | `cierre` |
| `POSTGRES_USER` | Usuario dueño de la base en `cierre-db` | `cierre` |
| `POSTGRES_PASSWORD` | Contraseña de ese usuario (definir una propia en `.env`) | `cambiar-clave` |
| `DATABASE_HOST` | Host de la base para la API y el worker: el nombre del servicio de Compose | `cierre-db` |
| `DATABASE_PORT` | Puerto de PostgreSQL dentro de la red de Compose | `5432` |
| `DATABASE_NAME` | Base a la que se conectan la API y el worker | `cierre` |
| `DATABASE_USER` | Usuario con el que se conectan la API y el worker | `cierre` |
| `DATABASE_PASSWORD` | Contraseña de la conexión; debe ser igual a `POSTGRES_PASSWORD` | `cambiar-clave` |
| `API_PORT` | Puerto del host donde se publica `cierre-api` | `8081` |
| `WORKER_INTERVAL_SECONDS` | Segundos entre conciliaciones del worker; debe ser un entero sin unidad | `30` |

## Arquitectura

El entorno tiene tres servicios definidos en `docker-compose.yml` que se comunican por la red interna de Docker Compose usando el nombre del servicio como host:

- `cierre-db`: PostgreSQL 16. Al iniciar carga los CSV de `data/` (`db/init/02_load.sql`) y corrige la calidad de datos (`db/init/03_limpieza.sql`: elimina duplicados y normaliza fechas).
- `cierre-api`: servicio Python que consulta `cierre-db` y publica `GET /afiliados/{documento}` en el puerto 8081.
- `cierre-worker`: proceso Python que cada `WORKER_INTERVAL_SECONDS` concilia el conteo de afiliados contra `cierre-db`.

El cierre (`run.sh` → `scripts/cierre.sh` → `scripts/procesar_cierre.py`) lee los CSV de `data/` sin modificarlos, aplica las reglas de `docs/diccionario.md` y escribe los resultados en `output/`.

## Uso

Consultar un afiliado en la API con `GET /afiliados/{documento}`:

```bash
curl http://localhost:8081/afiliados/1098765432
```

Respuesta: `{"documento": "1098765432", "nombre": "JUAN CARLOS PEREZ GOMEZ", "estado": "ACTIVO", "empresa": "EMPRESA ABC"}`. Un documento inexistente responde `404`.

`./run.sh` genera en `output/`:

- `output/afiliados_activos.csv`: afiliados activos con empresa válida, cantidad de beneficiarios y último aporte (`YYYY-MM`).
- `output/excepciones.csv`: `DUPLICADO`, `SIN_EMPRESA`, `BENEFICIARIO_HUERFANO`, `CODIGO_INVALIDO`, `FECHA_INVALIDA` y `CRUCE_NO_COINCIDE`.
- `output/totales.txt`: `total_afiliados`, `activos`, `inactivos` y `excepciones`.
- `output/top_error.txt`: código de error más frecuente en los logs y su número de ocurrencias.

## Pruebas

Con los servicios arriba, `./validator check` ejecuta las pruebas del contrato y debe mostrar 10/10 pruebas y 625/625 puntos. `./validator entregables` revisa los documentos. Para comprobar la repetibilidad se ejecuta `./run.sh` dos veces y `md5sum output/*` debe dar lo mismo, también después de `./reset.sh`.

## Documentación

- [Informe de incidentes](incident-report.md)
- [Evidencia por incidente](evidence/)
- [Uso de inteligencia artificial](AI_USAGE.md)
- [Diccionario de datos](docs/diccionario.md)

## Qué resolvimos

Resolvimos los diez incidentes: el worker caía por un intervalo con texto, la API apuntaba a un host inexistente, el cierre leía una ruta antigua y los scripts no tenían permiso de ejecución. Identificamos CIE-4012 como el error más frecuente, corregimos el error 500 de la API, reportamos duplicados, códigos inválidos, afiliados sin empresa, huérfanos, fechas inválidas y cruces con Caja Oriente, y logramos totales iguales a la hoja de control con un cierre repetible.

## Limitaciones y pendientes

Los casos irreparables (estados inválidos, afiliados sin empresa, beneficiarios huérfanos y fechas imposibles) solo se reportan: Operaciones debe corregirlos en el sistema origen. El extracto de Caja Oriente se procesa con el formato actual; si cambia sus columnas habría que ajustar el cierre.
