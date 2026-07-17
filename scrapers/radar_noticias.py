"""SCR-016 — Radar de noticias locales: pistas de otros medios de la zona.

NO es un scraper de contenido: es un radar de PISTAS. Detecta titulares de
medios locales que citan a pueblos de la comarca y los deja en una cola de
revisión. El texto ajeno nunca se copia — con la pista, El Terracampino
redacta su propia pieza a partir de los hechos, citando y enlazando la
fuente original ("según informa Sahagún Digital…").

Además, la política editorial (editorial/politica_editorial.md) prohíbe
publicar sucesos de forma automática, y buena parte de lo que cazará este
radar son sucesos (incendios, accidentes…) — otra razón por la que esto
alimenta una cola de revisión humana y no publica nada solo.

Fuentes (robots.txt verificado una a una el 2026-07-16):
  · La Mar de Campos (lamardecampos.org) — Tierra de Campos vallisoletana y
    parte de Zamora. RSS. robots.txt solo bloquea /wp-admin/.
  · Palencia en la Red (palenciaenlared.es) — provincia de Palencia. RSS.
  · Sahagún Digital (sahagundigital.com) — Sahagún y sureste de León. Sin
    RSS: se leen los enlaces /art/ de la portada. Su plataforma (folioepress)
    permite bots (sin regla User-agent: * y con Allow explícito a bots de IA).
  · Leonsur Digital (leonsurdigital.com) — sur de León (Valderas…). Ídem.
  · InterBenavente (interbenavente.es) — Zamora, con sección propia de
    Tierra de Campos. Ídem.

Grandes medios provinciales (El Norte de Castilla, Diario de León,
Leonoticias…) también permiten rastreo, pero cubren mucho más ruido que
señal para 12 pueblos — quedan fuera de la v1 a propósito.

Uso:
    python -m scrapers.radar_noticias --dry-run
    python -m scrapers.radar_noticias --guardar   # persiste la cola en data/radar/pistas.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapers.common import (
    ERR_STRUCTURE,
    ROOT,
    ScraperError,
    fetch,
    load_municipios,
    match_municipio,
    sha256,
)

# Cola de trabajo interna, en .gitignore: guarda titulares y extractos ajenos
# como pista para el redactor. El repo es público — subirla sería republicar
# texto con derechos de otros medios, justo lo que este diseño evita.
PISTAS_PATH = ROOT / "data" / "radar" / "pistas.json"

FUENTES = [
    {
        "slug": "lamardecampos",
        "nombre": "La Mar de Campos",
        "tipo": "rss",
        "url": "https://www.lamardecampos.org/feed/",
    },
    {
        "slug": "palenciaenlared",
        "nombre": "Palencia en la Red",
        "tipo": "rss",
        "url": "https://www.palenciaenlared.es/feed/",
    },
    {
        "slug": "sahagundigital",
        "nombre": "Sahagún Digital",
        "tipo": "html_folioepress",
        "url": "https://sahagundigital.com/",
    },
    {
        "slug": "leonsurdigital",
        "nombre": "Leonsur Digital",
        "tipo": "html_folioepress",
        # La portada de Leonsur no lista artículos (solo secciones): se lee
        # su sección de pueblos, que sí trae los enlaces /art/.
        "url": "https://leonsurdigital.com/sec/pueblos",
    },
    {
        "slug": "interbenavente",
        "nombre": "InterBenavente",
        "tipo": "html_folioepress",
        "url": "https://interbenavente.es/sec/comarca-tierra-de-campos",
    },
]

# Municipios del CSV maestro que NO deben usarse para casar titulares:
# 'Palencia' es también la capital (todo el feed provincial la cita) y
# 'Prado' es palabra común ("el prado del pueblo") — más ruido que señal.
SLUGS_EXCLUIDOS = {"palencia", "prado"}


def _limpiar_html(texto: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto or "")).strip()


def _items_rss(xml_text: str) -> list[dict]:
    """Items de un feed RSS 2.0: título, enlace, fecha y descripción."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ScraperError(ERR_STRUCTURE, f"RSS ilegible: {exc}") from exc
    items = []
    for item in root.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        enlace = (item.findtext("link") or "").strip()
        if not titulo or not enlace:
            continue
        publicado = None
        pub_date = item.findtext("pubDate")
        if pub_date:
            try:
                publicado = parsedate_to_datetime(pub_date).isoformat()
            except (TypeError, ValueError):
                pass
        items.append({
            "titulo": titulo,
            "url": enlace,
            "publicado": publicado,
            "resumen": _limpiar_html(item.findtext("description"))[:300],
        })
    return items


def _items_folioepress(html_text: str, base_url: str) -> list[dict]:
    """Enlaces de artículo (/art/<id>/<slug>) de una portada o sección
    folioepress. Sin fecha: la plataforma no la expone en el listado."""
    soup = BeautifulSoup(html_text, "html.parser")
    vistos: set[str] = set()
    items = []
    for a in soup.select('a[href*="/art/"], a[href^="art/"]'):
        url = urljoin(base_url, a["href"])
        titulo = a.get_text(" ", strip=True)
        if url in vistos or not titulo or len(titulo) < 15:
            continue  # anclas de imagen/duplicados: el titular real es el ancla larga
        vistos.add(url)
        items.append({"titulo": titulo, "url": url, "publicado": None, "resumen": ""})
    if not items:
        raise ScraperError(ERR_STRUCTURE, "No se encontró ningún enlace /art/ con titular")
    return items


def buscar_pistas() -> list[dict]:
    """Recorre las fuentes y devuelve las pistas que citan a algún municipio
    de la comarca (los 191 del CSV maestro, no solo los 12 pilotos — una
    noticia de un pueblo vecino también puede interesar). Los errores de una
    fuente no tumban a las demás: se registran y se sigue."""
    municipios = [m for m in load_municipios() if m.slug not in SLUGS_EXCLUIDOS]

    pistas: list[dict] = []
    for fuente in FUENTES:
        try:
            html_o_xml = fetch(fuente["url"])
            if fuente["tipo"] == "rss":
                items = _items_rss(html_o_xml)
            else:
                items = _items_folioepress(html_o_xml, fuente["url"])
        except ScraperError as exc:
            print(f"  aviso: {fuente['nombre']} falló ({exc.error_type}: {exc})", file=sys.stderr)
            continue

        for item in items:
            muni = match_municipio(f"{item['titulo']} {item['resumen']}", municipios)
            if not muni:
                continue
            pistas.append({
                "municipality_slug": muni.slug,
                "municipality_name": muni.name,
                "titulo": item["titulo"],
                "url_original": item["url"],
                "fuente": fuente["nombre"],
                "fuente_slug": fuente["slug"],
                "publicado": item["publicado"],
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "hash": sha256(f"radar-{item['url']}"),
                "estado": "pendiente",  # pendiente | descartada | desarrollada
                "resumen": item["resumen"],
            })
    return pistas


def guardar_pistas(nuevas: list[dict]) -> tuple[int, int]:
    """Fusiona con la cola existente sin machacar el estado de revisión de
    las ya conocidas (dedupe por hash). Devuelve (nuevas_añadidas, total)."""
    PISTAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cola = json.loads(PISTAS_PATH.read_text(encoding="utf-8")) if PISTAS_PATH.exists() else []
    conocidos = {p["hash"] for p in cola}
    añadidas = [p for p in nuevas if p["hash"] not in conocidos]
    cola = añadidas + cola
    PISTAS_PATH.write_text(json.dumps(cola, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(añadidas), len(cola)


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-016 — Radar de pistas de noticias locales")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime, no escribe la cola")
    ap.add_argument("--guardar", action="store_true", help="persiste la cola en data/radar/pistas.json")
    args = ap.parse_args()

    pistas = buscar_pistas()
    por_pueblo: dict[str, list[dict]] = {}
    for p in pistas:
        por_pueblo.setdefault(p["municipality_name"], []).append(p)

    for pueblo in sorted(por_pueblo):
        print(f"\n== {pueblo} — {len(por_pueblo[pueblo])} pista(s) ==")
        for p in por_pueblo[pueblo]:
            fecha = (p["publicado"] or "")[:10]
            print(f"  · [{p['fuente']}]{' ' + fecha if fecha else ''} {p['titulo'][:90]}")
            print(f"    {p['url_original']}")

    print(f"\nTotal: {len(pistas)} pistas que citan a pueblos de la comarca.")
    if args.guardar:
        nuevas, total = guardar_pistas(pistas)
        print(f"Cola actualizada: {nuevas} nuevas, {total} en data/radar/pistas.json")
    elif not args.dry_run:
        print("(usa --guardar para persistir la cola de revisión)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
