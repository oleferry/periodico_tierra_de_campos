"""SCR-BOCYL — Boletín Oficial de Castilla y León (datos abiertos JCyL).

El BOCyL es regional: cubre las 4 provincias de Tierra de Campos (Valladolid,
Palencia, León, Zamora) desde una sola API de OpenDataSoft. Se busca cada
municipio por su nombre en el título del anuncio, ordenado por fecha.

Fuente: https://analisis.datosabiertos.jcyl.es (dataset "bocyl").
Devuelve el contrato de documento de README_SCRAPERS §3.

Uso:
    python -m scrapers.bocyl --dry-run
    python -m scrapers.bocyl --municipio mayorga
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timezone

import re

from scrapers.common import (
    ERR_NETWORK,
    ScraperError,
    fetch,
    load_municipios,
    normalize_for_match,
    sha256,
)

API = "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/bocyl/records"

# El nombre del pueblo puede aparecer en municipios homónimos de otras comarcas;
# se exige que el organismo o el título lo cite, y se filtra por provincia esperada.
PROV_HINT = {
    "Valladolid": "VALLADOLID", "Palencia": "PALENCIA", "León": "LEÓN", "Zamora": "ZAMORA",
}

_AYUNTAMIENTO_DE = re.compile(r"^AYUNTAMIENTO DE (.+?)(?:\s*\([^)]*\))?\s*$")


def _es_otro_municipio(organismo: str, nombre: str) -> bool:
    """True si el organismo es CLARAMENTE el ayuntamiento de un municipio
    distinto al buscado, aunque el título contenga el nombre buscado.

    'titulo like "%Mayorga%"' también trae anuncios de 'AYUNTAMIENTO DE
    SAELICES DE MAYORGA' (nombre compuesto que contiene el nuestro) y de
    ayuntamientos vecinos que solo citan Mayorga de pasada (p.ej. una vía
    pecuaria compartida) — ninguno de los dos es una noticia de Mayorga.
    Si el organismo no es un ayuntamiento con nombre propio (una consejería,
    un servicio territorial...) no se puede decidir por aquí, así que no se
    descarta: lo sigue filtrando el criterio de provincia de más arriba."""
    m = _AYUNTAMIENTO_DE.match(organismo.strip().upper())
    if not m:
        return False
    return normalize_for_match(m.group(1)) != normalize_for_match(nombre)


def buscar(nombre: str, provincia: str, limit: int = 6) -> list[dict]:
    where = f'titulo like "%{nombre}%"'
    qs = urllib.parse.urlencode({
        "where": where,
        "order_by": "fecha_publicacion desc",
        "limit": limit,
    })
    raw = fetch(f"{API}?{qs}", check_robots=False)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScraperError(ERR_NETWORK, f"BOCyL: respuesta no JSON ({exc})") from exc
    return data.get("results", [])


def to_documents(nombre: str, slug: str, provincia: str, registros: list[dict]) -> list[dict]:
    detected = datetime.now(timezone.utc).isoformat()
    hint = PROV_HINT.get(provincia, "")
    out = []
    for r in registros:
        organismo = (r.get("organismo") or "")
        titulo = (r.get("titulo") or "").strip()
        # Descartar homónimos de otra provincia cuando el organismo es un ayuntamiento
        # que declara su provincia entre paréntesis y NO es la nuestra.
        if "AYUNTAMIENTO" in organismo.upper() and hint and hint not in organismo.upper():
            # el ayuntamiento emisor es de otra provincia → probable homónimo
            if any(p in organismo.upper() for p in PROV_HINT.values()):
                continue
        # Descartar otro municipio de la MISMA provincia que solo comparte
        # parte del nombre o cita al nuestro de pasada (ver _es_otro_municipio).
        if _es_otro_municipio(organismo, nombre):
            continue
        url = r.get("enlace_fichero_html") or r.get("enlace_fichero_pdf") or ""
        out.append({
            "municipality_slug": slug,
            "municipality_name": nombre,
            "title": titulo,
            "source_type": "bocyl",
            "url_original": url,
            "file_url": r.get("enlace_fichero_pdf") or url,
            "published_at": r.get("fecha_publicacion"),
            "detected_at": detected,
            "hash": sha256(url or titulo),
            "confidence": "high",
            "requires_review": True,
            "status": "new",
            "metadata": {"organismo": organismo, "edicion": r.get("no_edicion"), "scraper": "SCR-BOCYL"},
        })
    return out


def for_municipios(municipios: list, limit: int = 6) -> dict[str, list[dict]]:
    """Devuelve {slug: [documentos]} para una lista de Municipio (de common.load_municipios)."""
    res: dict[str, list[dict]] = {}
    for m in municipios:
        registros = buscar(m.name, m.province, limit=limit)
        docs = to_documents(m.name, m.slug, m.province, registros)
        if docs:
            res[m.slug] = docs
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-BOCYL — BOCyL por municipio")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--municipio", help="slug concreto; por defecto, los 12 pilotos")
    ap.add_argument("--limit", type=int, default=4)
    args = ap.parse_args()

    todos = load_municipios()
    if args.municipio:
        objetivo = [m for m in todos if m.slug == args.municipio]
    else:
        from sitegen.build import PILOTS
        objetivo = [m for m in todos if m.slug in PILOTS]

    if not objetivo:
        print("No hay municipios objetivo", file=sys.stderr)
        return 1

    total = 0
    for m in objetivo:
        try:
            docs = to_documents(m.name, m.slug, m.province, buscar(m.name, m.province, args.limit))
        except ScraperError as exc:
            print(f"ERROR [{exc.error_type}] {m.name}: {exc}", file=sys.stderr)
            continue
        total += len(docs)
        print(f"\n=== {m.name} ({m.province}): {len(docs)} anuncios ===")
        for d in docs:
            print(f"  {d['published_at']}  {d['title'][:88]}")

    print(f"\nTotal: {total} anuncios del BOCyL para {len(objetivo)} municipios.")
    if args.dry_run and objetivo:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
