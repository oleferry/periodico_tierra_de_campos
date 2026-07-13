"""SCR-012 — Noticias municipales de ayuntamientos con web en WordPress.

Investigación previa a este scraper (importante para no repetir el trabajo):
  · Las páginas de "Plenos municipales" de los 6 pilotos originales están
    MUERTAS o VACÍAS: Mayorga y Villada se quedaron en 2015-2017 (dataset
    Liferay abandonado, ver database/migrations y notas del proyecto),
    Villalón de Campos no tiene ni una entrada, Sahagún y Valderas solo listan
    años 2012-2015 en un desplegable que nadie ha vuelto a tocar.
  · Medina de Rioseco publica sus plenos como enlace a vídeo de YouTube (sin
    texto de acuerdos) en una página aparte — no da contenido para redactar.
  · Lo que SÍ está vivo en Medina de Rioseco es su sección "Actualidad
    Municipal" (bandos, licencias, información pública, avisos): WordPress
    con REST API abierta (robots.txt solo prohíbe /wp-admin/), fechas reales
    y recientes. No es "el pleno", pero es la información municipal real que
    el pueblo publica día a día — más cerca de lo que pidió el usuario que
    una página de plenos sin contenido.

La API REST de WordPress (/wp-json/wp/v2/posts) es preferible a scrapear el
HTML: da fecha, título y enlace ya estructurados, sin depender del tema/plugin
de maquetación (aquí Elementor) que cambia con cada actualización de la web.

Cobertura actual: Medina de Rioseco, Carrión de los Condes y Becerril de
Campos. Investigado el resto de pilotos (2026-07-13):
  · Villada, Paredes de Nava, Villarramiel: WordPress pero con la API REST
    desactivada (401 "No REST API") — pendiente de valorar scraping HTML.
  · Fuentes de Nava: no es WordPress, es Joomla — necesitaría un scraper
    distinto (no compatible con este módulo).
  · Villalpando: el dominio redirige a una pantalla de login (/login.php),
    no sirve contenido público por esta vía — descartado por ahora.
  · Mayorga, Villalón, Sahagún, Valderas: ver scrapers/plenos_sedelectronica.py
    (Mayorga) y las notas de plenos muertos/vacíos de arriba; no son WordPress.

Uso:
    python -m scrapers.municipal_wp --dry-run
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import datetime, timezone

from scrapers.common import ERR_STRUCTURE, ScraperError, fetch, sha256

SITIOS = {
    "medina-de-rioseco": {
        "url": "https://medinaderioseco.org",
        "nombre": "Ayuntamiento de Medina de Rioseco",
    },
    "carrion-de-los-condes": {
        "url": "https://carriondeloscondes.org",
        "nombre": "Ayuntamiento de Carrión de los Condes",
    },
    "becerril-de-campos": {
        "url": "https://becerrildecampos.es",
        "nombre": "Ayuntamiento de Becerril de Campos",
    },
}

_TAG_RE = re.compile(r"<[^>]+>")


def _texto_limpio(html_fragment: str) -> str:
    sin_tags = _TAG_RE.sub(" ", html_fragment or "")
    return re.sub(r"\s+", " ", html.unescape(sin_tags)).strip()


def fetch_noticias(municipio_slug: str, *, per_page: int = 10) -> list[dict]:
    """Últimas noticias municipales del ayuntamiento, vía REST API de WordPress."""
    sitio = SITIOS.get(municipio_slug)
    if not sitio:
        return []

    # ?rest_route= en vez de /wp-json/wp/v2/ (path bonito): funciona en todos los
    # sitios probados (con o sin permalinks bonitos activados), así que se usa
    # siempre la misma forma en vez de adivinar cuál necesita cada web.
    url = f"{sitio['url']}/?rest_route=/wp/v2/posts&per_page={per_page}&_fields=id,date,link,title,excerpt"
    body = fetch(url)
    try:
        import json
        posts = json.loads(body)
    except ValueError as exc:
        raise ScraperError(ERR_STRUCTURE, f"Respuesta no-JSON de {url}: {exc}") from exc
    if not isinstance(posts, list):
        raise ScraperError(ERR_STRUCTURE, f"Se esperaba una lista de posts en {url}")

    detected_at = datetime.now(timezone.utc).isoformat()
    out: list[dict] = []
    for p in posts:
        titulo = _texto_limpio(p.get("title", {}).get("rendered", ""))
        if not titulo:
            continue
        try:
            published_at = p["date"][:10]  # WordPress da 'YYYY-MM-DDTHH:MM:SS'
        except (KeyError, TypeError):
            continue
        out.append({
            "municipality_slug": municipio_slug,
            "municipality_name": sitio["nombre"].removeprefix("Ayuntamiento de "),
            "title": titulo,
            "source_type": "municipal_news",
            "url_original": p.get("link", ""),
            "file_url": p.get("link", ""),
            "published_at": published_at,
            "detected_at": detected_at,
            "hash": sha256(f"{municipio_slug}|{p.get('id')}"),
            "confidence": "high",
            "requires_review": True,
            "status": "new",
            "metadata": {"organismo": sitio["nombre"], "wp_id": p.get("id"), "scraper": "SCR-012"},
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-012 — Noticias municipales (WordPress)")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime (no hay escritura en BD todavía)")
    ap.parse_args()

    exit_code = 0
    for slug in SITIOS:
        try:
            docs = fetch_noticias(slug)
        except ScraperError as exc:
            print(f"ERROR [{exc.error_type}] {slug}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        print(f"\n== {slug} — {len(docs)} noticias ==")
        for d in docs:
            # Windows/cp1252 no sabe imprimir algunos emoji que meten los pueblos
            # en sus titulares (📢, etc.); no es motivo para que el scraper falle.
            linea = f"  · {d['published_at']}  {d['title'][:80]}"
            print(linea.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
