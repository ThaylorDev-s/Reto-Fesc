#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Cierre mensual de afiliados activos.
# Lee los CSV de data/ sin modificarlos y genera output/ desde cero en cada
# ejecución, por lo que puede correrse las veces que se necesite.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

ENTRADA=data
SALIDA=output

# Se regenera la salida completa: nada de la ejecución anterior se reutiliza
rm -rf "$SALIDA"
mkdir -p "$SALIDA"

echo "Leyendo afiliados desde $ENTRADA/AFI_MAE.csv"
python3 scripts/procesar_cierre.py "$ENTRADA" "$SALIDA"

# Error más frecuente en los logs de los tres servicios (solo códigos CIE-####; los W-### son avisos)
TOP=$(grep -ohE 'CIE-[0-9]{4}' logs/*.log | sort | uniq -c | sort -k1,1nr -k2,2 | head -n 1)
echo "codigo_error=$(echo "$TOP" | awk '{print $2}')" > "$SALIDA/top_error.txt"
echo "ocurrencias=$(echo "$TOP" | awk '{print $1}')" >> "$SALIDA/top_error.txt"

echo "Cierre terminado"
