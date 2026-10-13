# Uso de inteligencia artificial

## Uso 1
- Herramienta: Claude Code (Claude Opus 5.5)
- Para qué se usó: diagnosticar por qué cierre-worker quedaba en Exited (1) y la API no conectaba a la base
- Prompt principal (resumido): "el worker sale con código 1 y la API responde 503, revisa docker compose logs y el .env.example"
- Qué produjo: leyó los logs, encontró CIE-1107 por WORKER_INTERVAL_SECONDS=30s y CIE-2210 por el host cierre-database
- Qué modificó o corrigió el equipo: la IA aplicó el arreglo solo en el .env local; el equipo decidió llevarlo a .env.example porque el calificador copia ese archivo desde cero

## Uso 2
- Herramienta: Claude Code (Claude Opus 5.5)
- Para qué se usó: identificar el error más frecuente en los tres logs
- Prompt principal (resumido): "cuenta los códigos de error de logs/ con grep, sort y uniq"
- Qué produjo: el pipeline grep -ohE "CIE-[0-9]{4}" logs/*.log | sort | uniq -c | sort -rn con CIE-4012 en 1424 ocurrencias
- Qué modificó o corrigió el equipo: verificamos que contar solo worker.log daba 1068, un resultado incorrecto, y dejamos el conteo sobre los tres logs excluyendo los avisos W-###

## Uso 3
- Herramienta: Claude Code (Claude Opus 5.5)
- Para qué se usó: normalizar las fechas de afiliación en la base sin romper la carga inicial
- Prompt principal (resumido): "normaliza FEC_AFI de DD/MM/YYYY y YYYYMMDD a YYYY-MM-DD en db/init y reporta las fechas imposibles"
- Qué produjo: un UPDATE con to_date() en db/init/03_limpieza.sql
- Qué modificó o corrigió el equipo: to_date falla con fechas como 31/13/2024 y detendría toda la carga de la base, así que se reemplazó por una función con manejo de excepción

## Uso 4
- Herramienta: Claude Code (Claude Opus 5.5)
- Para qué se usó: planificar el reto antes de empezar a corregir
- Prompt principal (resumido): "antes de resolver ayúdame a planificar todo lo que hay que hacer: incidentes, entregables, commits y pitch"
- Qué produjo: un plan por fases con orden de incidentes, entregables, reparto de commits y horario
- Qué modificó o corrigió el equipo: detuvimos a la IA, que ya estaba resolviendo sin plan, y repartimos los commits para que cada integrante tuviera al menos tres propios
