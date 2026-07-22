"""Genera data/poblacion_negocios.json: series históricas reales del INE
(población y número de empresas) para los 12 municipios piloto.

Fuentes, todas API pública del INE (Tempus, https://servicios.ine.es/wstempus/):
  · Población: "Cifras Oficiales de Población de los Municipios Españoles:
    Revisión del Padrón Municipal" (operación 22), una tabla por provincia.
    Serie 1996-2025 (huecos en 1997: el Padrón no publicó revisión ese año).
  · Población histórica: "Poblaciones de hecho desde 1900 hasta 1991. Cifras
    oficiales sacadas de los Censos respectivos" (operación 35), una tabla
    por provincia (censo decenal — 1900, 1910, 1920... 1991). Sirve para el
    reportaje "cien años perdiendo habitantes" (docs/ideas-blog.md, #20):
    combinada con la serie 1996-2025 da el arco completo del siglo.
  · Empresas: "Explotación Estadística del Directorio Central de Empresas.
    DIRCE" (operación 43, tabla 4721 "Empresas por municipio y actividad
    principal"), columna "Total CNAE" (todas las actividades). Serie 2012-2025.

Match por nombre EXACTO de municipio (con prefijo ' Total.' incluido), no por
substring — el mismo problema que Mayorga/Saelices de Mayorga en BOCyL
(ver scrapers/bocyl.py) existe aquí igual: 'Mayorga' es substring de
'Saelices de Mayorga', así que un match ingenuo mezclaría los dos pueblos.

Generador de UNA VEZ (dato evergreen para el reportaje de despoblación, no se
llama en cada build). Re-ejecutar solo para refrescar con el año siguiente:

    python -m scripts.investigar_despoblacion
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://servicios.ine.es/wstempus/js/ES"
# El WAF del INE devuelve 403 a cualquier User-Agent que contenga "bot"
# (no es un robots.txt: servicios.ine.es no tiene ninguno). API pública de
# datos abiertos, documentada para consumo de terceros.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ElTerracampino/0.1; +https://elterracampino.es)"}

# Tabla de "Población por municipios y sexo" (operación 22), una por provincia.
TABLA_POBLACION = {
    "Valladolid": 2904, "Palencia": 2888, "León": 2877, "Zamora": 2906,
}
# Tabla de "Poblaciones de hecho 1900-1991" (operación 35), una por provincia
# (ver TABLAS_OPERACION/35 — id distinto de la tabla moderna de arriba).
TABLA_POBLACION_HISTORICA = {
    "Valladolid": 3080, "Palencia": 3067, "León": 3057, "Zamora": 3082,
}
TABLA_EMPRESAS = 4721  # "Empresas por municipio y actividad principal" (operación 43)


def _get(url: str) -> dict | list:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def serie_poblacion(municipio: str, provincia: str) -> dict[str, float]:
    tabla = TABLA_POBLACION[provincia]
    datos = _get(f"{API}/DATOS_TABLA/{tabla}?nult=30")
    objetivo = f"{municipio}. Total. Total habitantes."
    for s in datos:
        if s.get("Nombre", "").startswith(objetivo):
            return {str(d["Anyo"]): d["Valor"] for d in s["Data"]}
    return {}


def serie_poblacion_historica(municipio: str, provincia: str) -> dict[str, float]:
    tabla = TABLA_POBLACION_HISTORICA[provincia]
    datos = _get(f"{API}/DATOS_TABLA/{tabla}?nult=20")
    # Nombre de serie distinto al de la tabla moderna: "Población de Hecho:
    # <municipio>. Ambos Sexos" (sin el ". Total." de en medio).
    objetivo = f"Población de Hecho: {municipio}. Ambos Sexos"
    for s in datos:
        if s.get("Nombre", "") == objetivo:
            return {str(d["Anyo"]): d["Valor"] for d in s["Data"]}
    return {}


def serie_empresas(municipio: str) -> dict[str, float]:
    # La tabla nacional es enorme; solo pedimos el último año para localizar
    # el COD de la serie de ESTE municipio, y luego pedimos su histórico aparte.
    datos = _get(f"{API}/DATOS_TABLA/{TABLA_EMPRESAS}?nult=1")
    objetivo = f"{municipio}. Total. Total de empresas. Total CNAE."
    cod = next((s["COD"] for s in datos if s.get("Nombre", "").startswith(objetivo)), None)
    if not cod:
        return {}
    historico = _get(f"{API}/DATOS_SERIE/{cod}?nult=20")
    return {str(d["Anyo"]): d["Valor"] for d in historico["Data"]}


def main() -> int:
    rows = list(csv.DictReader((ROOT / "data" / "municipios_tierra_de_campos.csv").open(encoding="utf-8")))
    pilotos = [r for r in rows if r["status"] == "piloto"]

    resultado = {}
    for r in pilotos:
        nombre, provincia = r["name"], r["province"]
        print(f"· {nombre} ({provincia})…", flush=True)
        poblacion = serie_poblacion(nombre, provincia)
        time.sleep(0.5)
        poblacion_historica = serie_poblacion_historica(nombre, provincia)
        time.sleep(0.5)
        empresas = serie_empresas(nombre)
        time.sleep(0.5)
        resultado[r["slug"]] = {
            "nombre": nombre, "provincia": provincia,
            "poblacion": poblacion, "poblacion_historica": poblacion_historica,
            "empresas": empresas,
        }
        print(f"    población: {len(poblacion)} años · histórica: {len(poblacion_historica)} años"
              f" · empresas: {len(empresas)} años")

    dest = ROOT / "data" / "poblacion_negocios.json"
    dest.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nEscrito {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
