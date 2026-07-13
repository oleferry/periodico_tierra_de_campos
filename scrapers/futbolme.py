"""SCR-011 — Resultados y próximo partido del club local, vía Futbolme.

Futbolme (robots.txt lo permite fuera de /panelBack/, /json/, etc.) publica el
calendario de cada equipo con datos estructurados schema.org/SportsEvent
(meta itemprop="name"/"startDate"), lo que permite leer nombre de los dos
equipos, fecha y resultado sin adivinar nada.

Cobertura actual: solo clubes que compiten en categorías nacionales/regionales
que Futbolme indexa (ligas de Tercera Federación para abajo hasta Regional).
La RFCYLF (federación oficial) bloquea todo bot en robots.txt, así que no hay
alternativa "oficial" scrapeable. Clubes de ligas provinciales de aficionados
(p. ej. C.D. Villa de Paredes, en Primera Provincial Palencia) NO están en
Futbolme — para esos habría que mirar otra fuente (siguetuliga.com verificado
como permitido, pendiente de scraper propio).

Uso:
    python -m scrapers.futbolme --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from bs4 import BeautifulSoup

from scrapers.common import ERR_STRUCTURE, ScraperError, fetch, sha256

CALENDARIO_URL = "https://futbolme.com/resultados-directo/equipo/{slug}/{team_id}/calendario"

# Clubes con calendario real verificado en Futbolme. Añadir aquí cuando se
# confirme (a mano, como se hizo con estos dos) que el club/id es el correcto:
# comprobar que la "Localidad" de la ficha /datos coincide con el municipio.
CLUBES = {
    "becerril-de-campos": {
        "slug_futbolme": "cd-becerril",
        "team_id": 1041,
        "nombre": "CD Becerril",
        "competicion": "Tercera Federación — Grupo 8",
    },
}

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_humana(dt: datetime) -> str:
    return f"{DIAS[dt.weekday()]} {dt.day} de {MESES[dt.month]}"


def parse_calendario(html_text: str, nombre_club: str) -> list[dict]:
    """Extrae los partidos del calendario. Devuelve lista ordenada por fecha."""
    soup = BeautifulSoup(html_text, "html.parser")
    bloques = soup.select("div.cajaGlobalPartidos")
    if not bloques:
        raise ScraperError(ERR_STRUCTURE, "No se encontró ningún 'div.cajaGlobalPartidos' en el calendario")

    partidos: list[dict] = []
    for b in bloques:
        name_meta = b.select_one('meta[itemprop="name"]')
        start_meta = b.select_one('meta[itemprop="startDate"]')
        if not name_meta or not start_meta:
            continue  # bloque sin la estructura esperada: se ignora, no se adivina
        nombres = name_meta.get("content", "").split(" - ")
        if len(nombres) != 2:
            continue
        local, visitante = (n.strip() for n in nombres)

        try:
            match_at = datetime.fromisoformat(start_meta["content"])
        except ValueError:
            continue

        marcador = [s.get_text(strip=True) for s in b.select(".resultadoPartido span")]
        jugado = len(marcador) == 2 and all(x.isdigit() for x in marcador)

        partidos.append({
            "local": local,
            "visitante": visitante,
            "match_at": match_at,
            "jugado": jugado,
            "local_score": int(marcador[0]) if jugado else None,
            "visitante_score": int(marcador[1]) if jugado else None,
            "es_local": nombre_club in local,
            "hash": sha256(f"{local}|{visitante}|{match_at.date().isoformat()}"),
        })

    partidos.sort(key=lambda p: p["match_at"])
    return partidos


def _texto_resultado(club: dict, p: dict) -> str:
    nombre = club["nombre"]
    rival = p["visitante"] if p["es_local"] else p["local"]
    a_favor = p["local_score"] if p["es_local"] else p["visitante_score"]
    en_contra = p["visitante_score"] if p["es_local"] else p["local_score"]
    lugar = "en casa" if p["es_local"] else f"en campo del {rival}"
    fecha = _fecha_humana(p["match_at"])
    if a_favor > en_contra:
        resultado = f"ganó {a_favor}-{en_contra}"
    elif a_favor < en_contra:
        resultado = f"cayó {en_contra}-{a_favor}" if p["es_local"] else f"perdió {a_favor}-{en_contra}"
    else:
        resultado = f"empató {a_favor}-{en_contra}"
    return f"El {fecha}, el {nombre} {resultado} {lugar} frente al {rival}."


def _texto_proximo(club: dict, p: dict) -> str:
    nombre = club["nombre"]
    rival = p["visitante"] if p["es_local"] else p["local"]
    lugar = "en casa" if p["es_local"] else f"fuera, en campo del {rival}"
    fecha = _fecha_humana(p["match_at"])
    return f"El próximo partido del {nombre} es el {fecha}, {lugar} frente al {rival}."


def marcador_for(municipio_slug: str, hoy: date | None = None) -> dict | None:
    """Devuelve {'club', 'competicion', 'ultimo': {...}|None, 'proximo': {...}|None}
    para el municipio, o None si no hay club con calendario cubierto en Futbolme.
    No lanza si Futbolme falla: quien llame decide el fallback (ScraperError se propaga)."""
    club = CLUBES.get(municipio_slug)
    if not club:
        return None
    hoy = hoy or date.today()

    url = CALENDARIO_URL.format(slug=club["slug_futbolme"], team_id=club["team_id"])
    partidos = parse_calendario(fetch(url), club["nombre"])

    pasados = [p for p in partidos if p["jugado"] and p["match_at"].date() <= hoy]
    futuros = [p for p in partidos if not p["jugado"] and p["match_at"].date() >= hoy]

    ultimo = pasados[-1] if pasados else None
    proximo = futuros[0] if futuros else None

    return {
        "club": club["nombre"],
        "competicion": club["competicion"],
        "ultimo": {**ultimo, "texto": _texto_resultado(club, ultimo)} if ultimo else None,
        "proximo": {**proximo, "texto": _texto_proximo(club, proximo)} if proximo else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-011 — Marcador de clubes locales (Futbolme)")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime, no hace nada más (no hay escritura en BD todavía)")
    ap.parse_args()

    exit_code = 0
    for slug in CLUBES:
        try:
            m = marcador_for(slug)
        except ScraperError as exc:
            print(f"ERROR [{exc.error_type}] {slug}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        print(f"\n== {slug} — {m['club']} ({m['competicion']}) ==")
        print("Último:", m["ultimo"]["texto"] if m["ultimo"] else "(sin partidos jugados en el calendario)")
        print("Próximo:", m["proximo"]["texto"] if m["proximo"] else "(sin próximo partido publicado todavía)")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
