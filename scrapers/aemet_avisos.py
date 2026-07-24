"""SCR-019 — Avisos de fenómenos meteorológicos adversos (AEMET Meteoalerta).

Esto NO es el parte del tiempo (eso es scrapers/weather_openmeteo.py, que da
temperaturas y previsión). Esto es la alerta: nivel amarillo, naranja o rojo
por calor, helada, tormenta, viento o nieve. Es el único contenido del sitio
que puede ser urgente de verdad, y el que más justifica avisar por Telegram.

Fuente: RSS oficial de AEMET por provincia (Plan Meteoalerta). No necesita la
clave de OpenData: son ficheros públicos. El robots.txt de aemet.es permite
esta ruta y pide un ritmo de peticiones bajo — aquí se hacen 4 peticiones (una
por provincia) una vez por ejecución, muy por debajo de su límite.

Los códigos son AFAP67 + código INE de provincia, y las zonas AFAZ67 + provincia
+ nº de zona (verificado el 2026-07-24 contra el mapa de zonas de AEMET).

IMPORTANTE — filtro por zona, no solo por provincia: cada provincia se divide
en zonas de aviso, y las nuestras son solo las "Meseta de…". Un aviso rojo en
la Cordillera Cantábrica de Palencia o en el Bierzo NO afecta a ningún pueblo
de Tierra de Campos, y darlo como propio sería alarmismo — justo lo que la
política editorial prohíbe. Por eso ZONAS_COMARCA es una lista blanca.

Uso:
    python -m scrapers.aemet_avisos --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

from scrapers.common import ERR_STRUCTURE, ScraperError, fetch

RSS = "https://www.aemet.es/documentos_d/eltiempo/prediccion/avisos/rss/CAP_AFAP67{prov}_RSS.xml"

# Código INE de provincia -> nombre, para las cuatro que tocan la comarca.
PROVINCIAS = {"24": "León", "34": "Palencia", "47": "Valladolid", "49": "Zamora"}

# Zonas de aviso de AEMET que SÍ contienen pueblos de Tierra de Campos.
# Las descartadas a propósito (verificadas el 2026-07-24): Cordillera Cantábrica
# de León, Bierzo de León, Cordillera Cantábrica de Palencia y Sanabria — son
# montaña y quedan fuera de la comarca.
ZONAS_COMARCA = {
    "Meseta de León",
    "Meseta de Palencia",
    "Meseta de Valladolid",
    "Meseta de Zamora",
}

NIVELES = {"amarillo": 1, "naranja": 2, "rojo": 3}

# "Aviso. Nivel amarillo. Temperaturas máximas. Meseta de Valladolid"
_TITULO_RE = re.compile(
    r"Aviso\.\s*Nivel\s+(?P<nivel>\w+)\.\s*(?P<fenomeno>[^.]+)\.\s*(?P<zona>.+)$",
    re.IGNORECASE,
)
# "…de 13:00 23-07-2026 CEST (UTC+2) a 20:59 23-07-2026 CEST (UTC+2)."
_RANGO_RE = re.compile(
    r"de\s+(\d{2}:\d{2})\s+(\d{2}-\d{2}-\d{4}).*?\s+a\s+(\d{2}:\d{2})\s+(\d{2}-\d{2}-\d{4})",
    re.IGNORECASE | re.DOTALL,
)


def _momento(hora: str, dia: str) -> datetime | None:
    try:
        return datetime.strptime(f"{dia} {hora}", "%d-%m-%Y %H:%M")
    except ValueError:
        return None


def _avisos_de(prov: str) -> list[dict]:
    try:
        root = ET.fromstring(fetch(RSS.format(prov=prov)))
    except ET.ParseError as exc:
        raise ScraperError(ERR_STRUCTURE, f"RSS de avisos ilegible ({prov}): {exc}") from exc

    out = []
    for item in root.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        # El primer item de cada feed es un tar.gz con "el estado completo",
        # no un aviso: no aporta nada legible y se descarta.
        if not titulo or titulo.startswith("Estado completo"):
            continue
        m = _TITULO_RE.match(titulo)
        if not m:
            continue
        zona = m.group("zona").strip()
        if zona not in ZONAS_COMARCA:
            continue

        descripcion = (item.findtext("description") or "").strip()
        rango = _RANGO_RE.search(descripcion)
        inicio = fin = None
        if rango:
            inicio = _momento(rango.group(1), rango.group(2))
            fin = _momento(rango.group(3), rango.group(4))

        nivel = m.group("nivel").lower()
        out.append({
            "nivel": nivel,
            "gravedad": NIVELES.get(nivel, 0),
            "fenomeno": m.group("fenomeno").strip(),
            "zona": zona,
            "provincia": PROVINCIAS[prov],
            "inicio": inicio.isoformat() if inicio else None,
            "fin": fin.isoformat() if fin else None,
            "url": (item.findtext("link") or "").strip(),
        })
    return out


def avisos(ahora: datetime | None = None, *, solo_vigentes: bool = True) -> list[dict]:
    """Avisos que afectan a la comarca, del más grave al menos.

    `solo_vigentes` descarta los ya terminados: AEMET los mantiene un rato en
    el feed y publicar "aviso naranja por calor" cuando acabó ayer sería
    desinformar. Un aviso aún no empezado SÍ se incluye — avisar de la helada
    de mañana es justo la utilidad de esto."""
    ahora = ahora or datetime.now()
    todos: list[dict] = []
    for prov in PROVINCIAS:
        try:
            todos.extend(_avisos_de(prov))
        except ScraperError as exc:
            print(f"  aviso: AEMET {PROVINCIAS[prov]} falló ({exc})", file=sys.stderr)

    if solo_vigentes:
        vivos = []
        for a in todos:
            if a["fin"] and datetime.fromisoformat(a["fin"]) < ahora:
                continue
            vivos.append(a)
        todos = vivos

    todos.sort(key=lambda a: (-a["gravedad"], a["inicio"] or ""))
    return todos


EMOJI = {"amarillo": "🟡", "naranja": "🟠", "rojo": "🔴"}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def clave(a: dict) -> str:
    """Identifica un aviso concreto, para no publicarlo dos veces. Incluye el
    nivel a propósito: si AEMET sube un amarillo a naranja, eso sí es noticia y
    debe volver a avisarse."""
    return f"{a['zona']}|{a['fenomeno']}|{a['nivel']}|{a['inicio']}"


def _cuando(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return f"{DIAS[d.weekday()]} a las {d.strftime('%H:%M')}"


def mensaje_telegram(a: dict) -> str:
    """Texto del aviso para el canal. Se reproduce lo que dice AEMET (nivel,
    fenómeno, zona, horas) y se enlaza a AEMET; nada de adornos ni dramatismo
    (política editorial: prohibido el alarmismo)."""
    emoji = EMOJI.get(a["nivel"], "⚠️")
    inicio, fin = _cuando(a.get("inicio")), _cuando(a.get("fin"))
    periodo = ""
    if inicio and fin:
        periodo = f"\nDesde el {inicio} hasta el {fin}."
    elif inicio:
        periodo = f"\nDesde el {inicio}."
    return (
        f"{emoji} *Aviso {a['nivel']}* por {a['fenomeno'].lower()}\n"
        f"{a['zona']} ({a['provincia']}).{periodo}\n\n"
        f"Fuente: AEMET, Plan Meteoalerta.\n"
        f"https://www.aemet.es/es/eltiempo/prediccion/avisos"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-019 — Avisos meteorológicos de AEMET para la comarca")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime")
    ap.add_argument("--todos", action="store_true", help="incluye también los avisos ya terminados")
    args = ap.parse_args()

    lista = avisos(solo_vigentes=not args.todos)
    if not lista:
        print("Sin avisos meteorológicos vigentes en Tierra de Campos.")
        return 0
    for a in lista:
        print(f"  [{a['nivel'].upper():8}] {a['fenomeno']} — {a['zona']} ({a['provincia']})")
        print(f"             de {a['inicio']} a {a['fin']}")
    print(f"\n{len(lista)} aviso(s) que afectan a la comarca.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
