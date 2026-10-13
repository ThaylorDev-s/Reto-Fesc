#!/usr/bin/env python3
"""Procesa el cierre mensual de afiliados a partir de los CSV del sistema origen.

Uso: procesar_cierre.py <carpeta_entrada> <carpeta_salida>

Lee los archivos sin modificarlos y escribe en la carpeta de salida:
  afiliados_activos.csv, excepciones.csv y totales.txt
Las reglas están en docs/diccionario.md. La salida es determinística: correr el
cierre varias veces con la misma entrada produce archivos idénticos.
"""

import csv
import os
import re
import sys
from datetime import datetime

COLUMNAS_ACTIVOS = ["documento", "nombre", "estado", "cod_empresa", "empresa", "beneficiarios", "ultimo_aporte"]
COLUMNAS_EXCEPCIONES = ["documento", "tipo", "detalle"]
ESTADOS = {"A": "ACTIVO", "I": "INACTIVO"}
SITUACION_ORIENTE = {"VIGENTE": "A", "RETIRADO": "I"}


def leer_csv(ruta, separador=","):
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return [{k.strip(): (v or "").strip() for k, v in fila.items()} for fila in csv.DictReader(archivo, delimiter=separador)]


def normalizar_fecha(texto):
    """Devuelve la fecha en YYYY-MM-DD, o None si no es una fecha real en un formato aceptado."""
    formatos = (
        (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),  # formato oficial
        (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
        (r"^\d{8}$", "%Y%m%d"),
    )
    for patron, formato in formatos:
        if re.match(patron, texto):
            try:
                return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
            except ValueError:
                return None  # forma correcta pero fecha imposible (ej. 2025-02-30)
    return None


def nombre_completo(fila):
    partes = (fila["NOM1"], fila["NOM2"], fila["APE1"], fila["APE2"])
    return " ".join(parte for parte in partes if parte)


def main(entrada, salida):
    afiliados = leer_csv(os.path.join(entrada, "AFI_MAE.csv"))
    empresas = {fila["COD_EMP"]: fila["NOM_EMP"] for fila in leer_csv(os.path.join(entrada, "EMPRESA.csv"))}
    beneficiarios = leer_csv(os.path.join(entrada, "AFI_BEN.csv"))
    aportes = leer_csv(os.path.join(entrada, "APORTES.csv"))
    extracto = leer_csv(os.path.join(entrada, "extracto_caja_oriente.csv"), separador=";")

    excepciones = []

    # Regla 1. Universo: un afiliado por documento, se conserva la primera aparición
    universo = {}
    duplicados = []
    for fila in afiliados:
        documento = fila["NRO_DOC"]
        if documento not in universo:
            universo[documento] = fila
        elif documento not in duplicados:
            duplicados.append(documento)
    for documento in duplicados:
        veces = sum(1 for fila in afiliados if fila["NRO_DOC"] == documento)
        excepciones.append([documento, "DUPLICADO", "aparece {0} veces en AFI_MAE; se conserva la primera".format(veces)])

    # Regla 2. Solo A e I son estados válidos
    for documento, fila in universo.items():
        if fila["EST_AFI"] not in ESTADOS:
            excepciones.append([documento, "CODIGO_INVALIDO", "EST_AFI='{0}' no es A ni I".format(fila["EST_AFI"])])

    # Regla 3. Un activo debe tener una empresa existente
    sin_empresa = set()
    for documento, fila in universo.items():
        if fila["EST_AFI"] == "A" and fila["COD_EMP"] not in empresas:
            sin_empresa.add(documento)
            detalle = "COD_EMP vacío" if not fila["COD_EMP"] else "COD_EMP='{0}' no existe en EMPRESA".format(fila["COD_EMP"])
            excepciones.append([documento, "SIN_EMPRESA", detalle])

    # Regla 4. Beneficiarios cuyo afiliado no existe
    for fila in beneficiarios:
        if fila["NRO_DOC_AFI"] not in universo:
            excepciones.append([fila["NRO_DOC_BEN"], "BENEFICIARIO_HUERFANO", "afiliado {0} no existe en AFI_MAE".format(fila["NRO_DOC_AFI"])])

    cantidad_beneficiarios = {}
    for fila in beneficiarios:
        cantidad_beneficiarios[fila["NRO_DOC_AFI"]] = cantidad_beneficiarios.get(fila["NRO_DOC_AFI"], 0) + 1

    ultimo_aporte = {}
    for fila in aportes:
        if fila["PERIODO"] > ultimo_aporte.get(fila["NRO_DOC"], ""):
            ultimo_aporte[fila["NRO_DOC"]] = fila["PERIODO"]

    # Regla 5. Fechas: se normalizan los formatos conocidos; lo que no es una fecha real se reporta.
    # La fecha no excluye al afiliado de los totales.
    for documento, fila in universo.items():
        normalizada = normalizar_fecha(fila["FEC_AFI"])
        if normalizada is None:
            excepciones.append([documento, "FECHA_INVALIDA", "FEC_AFI='{0}' no es una fecha válida".format(fila["FEC_AFI"])])
        else:
            fila["FEC_AFI"] = normalizada

    # Regla 6. Cruce con el extracto de Caja Oriente (separador ';', documento de 12 dígitos
    # con ceros a la izquierda, situación VIGENTE/RETIRADO). Solo se reporta: el archivo
    # de activos conserva su formato.
    for fila in extracto:
        documento = fila["id_afiliado"].lstrip("0")
        situacion = fila["situacion"].upper()
        if documento not in universo:
            excepciones.append([documento, "CRUCE_NO_COINCIDE", "Caja Oriente lo reporta {0}; no existe en AFI_MAE".format(situacion)])
        elif SITUACION_ORIENTE.get(situacion) != universo[documento]["EST_AFI"]:
            excepciones.append([documento, "CRUCE_NO_COINCIDE", "Caja Oriente lo reporta {0}; nuestro estado es {1}".format(situacion, universo[documento]["EST_AFI"])])

    # Regla 7. Archivo de activos: solo activos con empresa válida
    activos = []
    for documento, fila in universo.items():
        if fila["EST_AFI"] == "A" and documento not in sin_empresa:
            activos.append([
                documento,
                nombre_completo(fila),
                "ACTIVO",
                fila["COD_EMP"],
                empresas.get(fila["COD_EMP"], ""),
                cantidad_beneficiarios.get(documento, 0),
                ultimo_aporte.get(documento, ""),
            ])

    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(salida, "afiliados_activos.csv"), "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo, lineterminator="\n")
        escritor.writerow(COLUMNAS_ACTIVOS)
        escritor.writerows(activos)
    with open(os.path.join(salida, "excepciones.csv"), "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo, lineterminator="\n")
        escritor.writerow(COLUMNAS_EXCEPCIONES)
        escritor.writerows(excepciones)
    with open(os.path.join(salida, "totales.txt"), "w", encoding="utf-8", newline="\n") as archivo:
        archivo.write("total_afiliados={0}\n".format(len(universo)))
        archivo.write("activos={0}\n".format(len(activos)))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
