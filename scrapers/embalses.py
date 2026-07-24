"""SCR-020 — Situación de los embalses que riegan Tierra de Campos (SAIH Duero).

En una comarca cerealista de secano, el agua embalsada no es un dato ambiental
abstracto: marca la campaña de riego del año y es conversación de bar en verano.
La Confederación Hidrográfica del Duero publica los datos semanales de todos sus
embalses; aquí se filtran los sistemas que de verdad riegan la comarca.

Fuente: saihduero.es/situacion-embalses. Su robots.txt solo bloquea /css/, /js/
y /scss/. Los datos son provisionales y sujetos a revisión (lo advierte la
propia CHD), así que se cita siempre la fecha y se enlaza al original.

Qué sistemas se miran y por qué (verificado el 2026-07-24):
  · LEÓN (SISTEMA ESLA Y ÓRBIGO) — riega la Tierra de Campos leonesa: Sahagún,
    Valderas, El Burgo Ranero, y por el Esla llega hasta Villalpando (Zamora).
  · PALENCIA (SISTEMA CARRIÓN) — Carrión de los Condes, Villada, Paredes de
    Nava, Becerril, Fuentes de Nava.
  · PALENCIA (SISTEMA PISUERGA) — alimenta el Canal de Castilla y el Canal de
    Campos, de los que bebe buena parte de la comarca vallisoletana.
Se descartan a propósito Arlanza (Burgos), Alto Duero (Soria), los de Segovia y
Ávila, y los de Salamanca: están en la misma cuenca pero no riegan aquí.

Uso:
    python -m scrapers.embalses --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

from bs4 import BeautifulSoup

from scrapers.common import ERR_STRUCTURE, ScraperError, fetch

URL = "https://www.saihduero.es/situacion-embalses"

SISTEMAS_COMARCA = {
    "LEÓN (SISTEMA ESLA Y ÓRBIGO)": "Esla y Órbigo",
    "PALENCIA (SISTEMA CARRIÓN)": "Carrión",
    "PALENCIA (SISTEMA PISUERGA)": "Pisuerga",
}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

_FECHA_RE = re.compile(r"a d[íi]a\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.IGNORECASE)


def _numero(txt: str) -> float | None:
    """'1.288,4' -> 1288.4 (formato español). None si no es un número."""
    limpio = (txt or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def _fecha_datos(soup: BeautifulSoup) -> str | None:
    m = _FECHA_RE.search(soup.get_text(" ", strip=True))
    if not m:
        return None
    try:
        mes = MESES.index(m.group(2).lower()) + 1
        return date(int(m.group(3)), mes, int(m.group(1))).isoformat()
    except (ValueError, IndexError):
        return None


def situacion() -> dict:
    """{'fecha': 'YYYY-MM-DD', 'sistemas': [...]} con los sistemas de la comarca.

    Cada sistema trae sus embalses y su total, con el volumen actual, el del año
    pasado y la media de los diez años anteriores — que es lo que permite decir
    si el año va bien o mal, en vez de soltar un hm3 sin contexto."""
    soup = BeautifulSoup(fetch(URL), "html.parser")
    tabla = soup.select_one("table")
    if not tabla:
        raise ScraperError(ERR_STRUCTURE, "No se encontró la tabla de embalses")

    sistemas: list[dict] = []
    actual: dict | None = None
    for tr in tabla.select("tr"):
        celdas = [td.get_text(" ", strip=True) for td in tr.select("th,td")]
        if not celdas:
            continue

        # Fila de cabecera de sistema: una sola celda con el nombre.
        if len(celdas) == 1:
            nombre = celdas[0].strip()
            actual = None
            if nombre in SISTEMAS_COMARCA:
                actual = {"sistema": SISTEMAS_COMARCA[nombre], "nombre_oficial": nombre,
                          "embalses": [], "total": None}
                sistemas.append(actual)
            continue

        if actual is None or len(celdas) < 6:
            continue

        capacidad, hm3, pct, anio_ant, media10 = (_numero(c) for c in celdas[1:6])
        if hm3 is None or pct is None:
            continue
        fila = {
            "nombre": celdas[0].strip(),
            "capacidad_hm3": capacidad,
            "actual_hm3": hm3,
            "actual_pct": pct,
            "anio_anterior_hm3": anio_ant,
            "media_10_anios_hm3": media10,
        }
        if fila["nombre"].lower() == "total":
            actual["total"] = fila
        else:
            actual["embalses"].append(fila)

    if not sistemas:
        raise ScraperError(ERR_STRUCTURE, "No se reconoció ningún sistema de la comarca")
    return {"fecha": _fecha_datos(soup), "sistemas": sistemas, "url": URL}


def resumen(datos: dict) -> dict | None:
    """Agrega los tres sistemas en una cifra comarcal: cuánta agua hay y cómo va
    frente al año pasado y a la media de diez años."""
    totales = [s["total"] for s in datos["sistemas"] if s.get("total")]
    if not totales:
        return None
    cap = sum(t["capacidad_hm3"] or 0 for t in totales)
    act = sum(t["actual_hm3"] or 0 for t in totales)
    ant = sum(t["anio_anterior_hm3"] or 0 for t in totales)
    med = sum(t["media_10_anios_hm3"] or 0 for t in totales)
    return {
        "capacidad_hm3": round(cap, 1),
        "actual_hm3": round(act, 1),
        "actual_pct": round(act / cap * 100, 1) if cap else None,
        "vs_anio_anterior_pct": round((act - ant) / ant * 100, 1) if ant else None,
        "vs_media_pct": round((act - med) / med * 100, 1) if med else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-020 — Embalses que riegan Tierra de Campos")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime")
    ap.parse_args()

    datos = situacion()
    print(f"Datos del {datos['fecha']}")
    for s in datos["sistemas"]:
        print(f"\n== {s['sistema']} ==")
        for e in s["embalses"]:
            print(f"  {e['nombre']:20} {e['actual_hm3']:>8.1f} hm3  ({e['actual_pct']:>5.1f}%)"
                  f"   año ant.: {e['anio_anterior_hm3']}")
        if s["total"]:
            t = s["total"]
            print(f"  {'TOTAL':20} {t['actual_hm3']:>8.1f} hm3  ({t['actual_pct']:>5.1f}%)")

    r = resumen(datos)
    if r:
        print(f"\nComarca: {r['actual_hm3']} hm3 de {r['capacidad_hm3']} ({r['actual_pct']}%)")
        print(f"  frente al año pasado: {r['vs_anio_anterior_pct']:+}%")
        print(f"  frente a la media de 10 años: {r['vs_media_pct']:+}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
