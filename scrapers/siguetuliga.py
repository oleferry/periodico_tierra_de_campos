"""SCR-015 — Resultados y próximo partido de clubes de liga provincial, vía
siguetuliga.com.

Futbolme (scrapers/futbolme.py) solo cubre categorías nacionales/regionales
(Tercera Federación para abajo hasta Regional). Los clubes de las ligas
provinciales de aficionados (donde juegan la mayoría de nuestros pueblos)
NO están en Futbolme. La RFCYLF (federación oficial, rfcylf.es) SÍ tiene esos
datos y con URLs muy simples (?CodCompeticion=...), pero su robots.txt
bloquea a cualquier bot (`User-agent: * / Disallow: /`, solo permite
Googlebot/Twitterbot) — queda descartada por política del proyecto, aunque
sea la fuente más fácil técnicamente.

siguetuliga.com sí lo permite: su robots.txt solo bloquea rutas concretas
(admin, /api/, /ws/, /foro/, /gestion-club/, URLs con "?") — las páginas de
equipo y liga que usamos aquí son rutas limpias, sin query string.

Cobertura: comunitaria, no oficial — cada liga la mantiene un administrador
voluntario, así que el nivel de actualización varía (alguna liga puede
quedarse desactualizada una temporada). Por eso, igual que en futbolme.py,
solo se añaden aquí clubes verificados a mano uno a uno (nombre real
del club, no solo "suena parecido" — ver aviso de "Medinense" más abajo).

Aviso de "falso amigo" ya detectado al construir esta lista: el club
"Medinense" en Primera Provincial Valladolid es de MEDINA DEL CAMPO, no de
Medina de Rioseco (uno de nuestros pilotos) — se descartó. El equipo real de
Medina de Rioseco es "CD Rioseco".

Uso:
    python -m scrapers.siguetuliga --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime

from bs4 import BeautifulSoup

from scrapers.common import ERR_STRUCTURE, MESES, ScraperError, fetch, sha256, strip_accents

EQUIPO_URL = "https://www.siguetuliga.com/equipo/{slug}"

# Clubes con calendario verificado a mano en siguetuliga.com (nombre real del
# club confirmado contra fuentes externas, no solo por parecido de nombre).
# Añadir aquí solo tras comprobar que el club es realmente del municipio.
CLUBES = {
    "villada": {
        "slug_siguetuliga": "cd-villada",
        "nombre": "CD Villada",
        "competicion": "Primera División Provincial Palencia",
    },
    "carrion-de-los-condes": {
        "slug_siguetuliga": "cd-carrion",
        "nombre": "CD Carrión",
        "competicion": "Primera División Provincial Palencia",
    },
    "paredes-de-nava": {
        "slug_siguetuliga": "cf-carejas",
        "nombre": "CFC Paredes",
        "competicion": "Primera División Provincial Palencia",
    },
    "medina-de-rioseco": {
        "slug_siguetuliga": "cd-rioseco",
        "nombre": "CD Rioseco",
        "competicion": "Segunda División Provincial Valladolid",
    },
    "villalon-de-campos": {
        "slug_siguetuliga": "cp-villalon-campos",
        "nombre": "CP Villalón",
        "competicion": "Segunda División Provincial Valladolid A",
    },
}
# Pendientes (club localizado pero SIN calendario utilizable en
# siguetuliga.com al revisar — cobertura comunitaria, no oficial, así que
# varía por equipo):
#   · Mayorga: club real es "R Mayorga" (racing-mayorga), su ficha existe
#     pero no tiene liga asignada esta temporada.
#   · Villalpando: club real es "CD Villalpando" (cd-villalpando), su ficha
#     tampoco tiene liga asignada, y no aparece en la clasificación actual
#     de Primera Provincial Zamora (el resultado de búsqueda que lo situaba
#     ahí era de una temporada antigua).
# Revisar de nuevo más adelante por si el administrador de esas ligas las
# actualiza.
#
# No encontrados / fuera de esta plataforma:
#   · Becerril de Campos: ya cubierto en Futbolme (Tercera Federación).
#   · Sahagún: ficha en siguetuliga sin liga asignada esta temporada.
#   · Valderas: su liga real es la "Liga de la Amistad" de León, otra
#     plataforma (ligadelaamistadleon.es) — pendiente de scraper propio.
#   · Fuentes de Nava y Villarramiel: no localizados en fútbol federado 11
#     en ninguna plataforma revisada; puede que solo compitan en fútbol sala.

_JORNADA_RE = re.compile(r"Jornada\s+\d+.*?(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.IGNORECASE)


def _fecha_de_jornada(texto: str) -> date | None:
    m = _JORNADA_RE.search(texto)
    if not m:
        return None
    dia, mes_nombre, anio = m.groups()
    mes = MESES.get(strip_accents(mes_nombre).lower())
    if not mes:
        return None
    return date(int(anio), mes, int(dia))


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_TXT = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_humana(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES_TXT[d.month]}"


def parse_calendario(html_text: str, nombre_club: str) -> list[dict]:
    """Extrae los partidos del calendario de un equipo. Devuelve lista ordenada
    por fecha. Cada jornada agrupa sus partidos bajo un panel
    'div.panelListaResultados' (cabecera con fecha + lista de partidos)."""
    soup = BeautifulSoup(html_text, "html.parser")
    paneles = soup.select("div.panelListaResultados")
    if not paneles:
        raise ScraperError(ERR_STRUCTURE, "No se encontró ningún 'div.panelListaResultados'")

    partidos: list[dict] = []
    for panel in paneles:
        cabecera = panel.select_one(".panel-heading")
        if not cabecera:
            continue
        fecha = _fecha_de_jornada(cabecera.get_text(" ", strip=True))
        if not fecha:
            continue  # cabecera sin fecha reconocible: se ignora, no se adivina

        for fila in panel.select("li.filaPartido"):
            nombres = [s.get_text(" ", strip=True) for s in fila.select(".nombreEquipoResultados")]
            if len(nombres) != 2:
                continue
            local, visitante = nombres

            goles = fila.select_one(".resultado_partido")
            local_score = visitante_score = None
            jugado = False
            if goles:
                local_span = goles.select_one('[id^="golesEquipoLocal-"]')
                visit_span = goles.select_one('[id^="golesEquipoVisitante-"]')
                if local_span and visit_span:
                    l_txt, v_txt = local_span.get_text(strip=True), visit_span.get_text(strip=True)
                    if l_txt.isdigit() and v_txt.isdigit():
                        local_score, visitante_score = int(l_txt), int(v_txt)
                        jugado = True

            partidos.append({
                "local": local,
                "visitante": visitante,
                "match_at": datetime(fecha.year, fecha.month, fecha.day),
                "jugado": jugado,
                "local_score": local_score,
                "visitante_score": visitante_score,
                "es_local": nombre_club in local,
                "hash": sha256(f"{local}|{visitante}|{fecha.isoformat()}"),
            })

    partidos.sort(key=lambda p: p["match_at"])
    return partidos


def _texto_resultado(club: dict, p: dict) -> str:
    nombre = club["nombre"]
    rival = p["visitante"] if p["es_local"] else p["local"]
    a_favor = p["local_score"] if p["es_local"] else p["visitante_score"]
    en_contra = p["visitante_score"] if p["es_local"] else p["local_score"]
    lugar = "en casa" if p["es_local"] else f"en campo del {rival}"
    fecha = _fecha_humana(p["match_at"].date())
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
    fecha = _fecha_humana(p["match_at"].date())
    return f"El próximo partido del {nombre} es el {fecha}, {lugar} frente al {rival}."


def marcador_for(municipio_slug: str, hoy: date | None = None) -> dict | None:
    """Devuelve {'club', 'competicion', 'ultimo': {...}|None, 'proximo': {...}|None}
    para el municipio, o None si no hay club verificado en esta lista.
    No lanza si siguetuliga falla: quien llame decide el fallback (ScraperError se propaga)."""
    club = CLUBES.get(municipio_slug)
    if not club:
        return None
    hoy = hoy or date.today()

    url = EQUIPO_URL.format(slug=club["slug_siguetuliga"])
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
    ap = argparse.ArgumentParser(description="SCR-015 — Marcador de clubes de liga provincial (siguetuliga.com)")
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
