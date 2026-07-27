"""Genera data/agricultura_comarca.json: retrato del campo de los 12 municipios
piloto según el Censo Agrario, con datos reales del INE.

Fuente, API pública del INE (Tempus, https://servicios.ine.es/wstempus/):
  · Censo Agrario (operación 90, IOE 30042), tabla 29006 "Resultados
    municipales". Reúne, por municipio, tres medidas: número de EXPLOTACIONES,
    SAU (Superficie Agrícola Utilizada, en hectáreas) y UNIDADES GANADERAS
    totales. Año de referencia: 2009.

Aviso de comparabilidad (va también DENTRO del dossier): 2009 es la última
edición del Censo Agrario que se publica MUNICIPIO A MUNICIPIO por esta vía
(Tempus). El Censo Agrario 2020 cambió umbrales y metodología y no ofrece una
serie municipal comparable con esta fuente, así que este retrato es una foto
de 2009, no una serie temporal. No debe inferirse de aquí ninguna cifra
posterior a 2009.

La media nacional de 2009 (hectáreas por explotación) se calcula sumando TODOS
los municipios de la misma tabla, para tener un término de comparación de la
misma fuente y el mismo año (no una cifra traída de fuera). Sale ~24 ha/expl.,
que coincide con la media nacional publicada por el INE para 2009.

Match por nombre EXACTO de municipio (con el sufijo '. ' que usa el INE): los
12 nombres piloto son únicos en la tabla y no colisionan con otros municipios
(p. ej. 'Mayorga' no se confunde con 'Saelices de Mayorga', que es otro nombre
completo). Verificado antes de escribir esto.

Generador de UNA VEZ (dato evergreen; el Censo Agrario no cambia cada año).
Reejecutar solo si el INE publicase una nueva edición municipal:

    python -m scripts.investigar_agricultura
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://servicios.ine.es/wstempus/js/ES"
# Mismo motivo que en investigar_despoblacion.py: el WAF del INE devuelve 403 a
# cualquier User-Agent con "bot". API pública de datos abiertos.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ElTerracampino/0.1; +https://elterracampino.es)"}

TABLA_CENSO_AGRARIO = 29006  # "Resultados municipales" (operación 90), año 2009
ANYO = 2009

MEDIDAS = {
    "explotaciones": "Explotaciones",
    "sau_ha": "SAU (ha.)",
    "unidades_ganaderas": "Unidades ganaderas totales",
}


def _get(url: str) -> list | dict:
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.json()


def main() -> int:
    # Nombres bien escritos (con tildes) y provincia, desde el fichero de
    # población ya existente: sus claves de municipio coinciden EXACTAMENTE con
    # los nombres del INE en la tabla del censo agrario (verificado).
    pob_path = ROOT / "data" / "poblacion_negocios.json"
    if not pob_path.exists():
        raise SystemExit(
            "Falta data/poblacion_negocios.json — ejecuta primero:\n"
            "  python -m scripts.investigar_despoblacion"
        )
    pob = json.loads(pob_path.read_text(encoding="utf-8"))
    nombres = {slug: d["nombre"] for slug, d in pob.items()}
    provincias = {slug: d["provincia"] for slug, d in pob.items()}

    print(f"Descargando tabla {TABLA_CENSO_AGRARIO} del Censo Agrario ({ANYO})…", flush=True)
    data = _get(f"{API}/DATOS_TABLA/{TABLA_CENSO_AGRARIO}")
    por_nombre: dict[str, dict[str, float]] = {}
    nacional = {"explotaciones": 0.0, "sau_ha": 0.0}
    for s in data:
        nombre_serie = s.get("Nombre", "")
        datos = s.get("Data") or []
        if not datos:
            continue
        valor = datos[0]["Valor"]
        for clave, etiqueta in MEDIDAS.items():
            pref = f"{etiqueta}. "
            if nombre_serie.startswith(pref) and nombre_serie.endswith(". "):
                municipio = nombre_serie[len(pref):-2]  # quita prefijo y '. ' final
                por_nombre.setdefault(municipio, {})[clave] = valor
                # media nacional del mismo año y fuente: suma de TODOS los municipios
                if clave in nacional:
                    nacional[clave] += valor
                break

    resultado: dict[str, dict] = {}
    for slug, nombre in sorted(nombres.items(), key=lambda kv: kv[1]):
        reg = por_nombre.get(nombre)
        if not reg:
            print(f"  !! sin datos para {nombre}")
            continue
        exp = reg.get("explotaciones")
        sau = reg.get("sau_ha")
        ug = reg.get("unidades_ganaderas")
        resultado[slug] = {
            "nombre": nombre,
            "provincia": provincias[slug],
            "anyo": ANYO,
            "explotaciones": exp,
            "sau_ha": sau,
            "unidades_ganaderas": ug,
            "ha_por_explotacion": round(sau / exp, 1) if exp else None,
        }
        print(f"· {nombre:24} {exp:5.0f} explot. · {sau:8.0f} ha · "
              f"{sau / exp:6.1f} ha/expl · {ug:6.0f} UG")

    media_nacional = round(nacional["sau_ha"] / nacional["explotaciones"], 1)
    salida = {
        "fuente": "INE, Censo Agrario (operación 90), tabla 29006 'Resultados "
                  "municipales', API Tempus. Año de referencia 2009.",
        "anyo": ANYO,
        "nacional": {
            "explotaciones": round(nacional["explotaciones"]),
            "sau_ha": round(nacional["sau_ha"]),
            "ha_por_explotacion": media_nacional,
            "nota": "Media nacional calculada sumando todos los municipios de la "
                    "misma tabla (misma fuente y año que los pueblos).",
        },
        "municipios": resultado,
    }

    dest = ROOT / "data" / "agricultura_comarca.json"
    dest.write_text(json.dumps(salida, ensure_ascii=False, indent=2, sort_keys=False), encoding="utf-8")
    print(f"\nMedia nacional {ANYO}: {media_nacional} ha/explotación "
          f"({round(nacional['explotaciones']):,} explotaciones, "
          f"{round(nacional['sau_ha']):,} ha).")
    print(f"Escrito {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
