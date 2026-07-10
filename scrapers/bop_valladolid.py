"""SCR-006 — BOP de Valladolid (sumario del último boletín).

El BOP de Valladolid no tiene RSS operativo (ver database/migrations/
2026-07-10_fix_bop_valladolid.sql). Se scrapea el sumario HTML de /ultimobop,
que lista cada anuncio como:

    <li class="un_anuncio">
      <p class="bop_tit_articulo">AYUNTAMIENTO DE MAYORGA</p>
      <p class="bop_res_articulo"><a href="...BOPVA-A-2026-02061.pdf">Título…</a></p>
      ...
      <a class="cve_link">PUDLWzRVrrjbWMo0okxCVHM560U=</a>   ← CVE, id oficial único
    </li>

Solo se guardan los anuncios cuyo emisor cita un municipio de Tierra de Campos.
No se descarga ni extrae el PDF todavía: eso es un paso posterior del pipeline.

Uso:
    python -m scrapers.bop_valladolid --dry-run    # sin base de datos
    python -m scrapers.bop_valladolid              # escribe en Supabase
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from scrapers.common import (
    ERR_PARSE,
    ERR_STRUCTURE,
    ScraperError,
    Supabase,
    fetch,
    load_municipios,
    match_municipio,
    parse_spanish_date,
    sha256,
)

SOURCE_SLUG = "bop-valladolid"
SUMARIO_URL = "https://bop.sede.diputaciondevalladolid.es/ultimobop"

# .../boletines/2026/julio/10/BOPVA-A-2026-02061.pdf
PDF_DATE_RE = re.compile(r"/boletines/(\d{4})/([a-zA-Zñáéíóú]+)/(\d{1,2})/", re.IGNORECASE)


def parse_sumario(html: str) -> list[dict]:
    """Extrae los anuncios del sumario. Devuelve el contrato de README_SCRAPERS §3."""
    soup = BeautifulSoup(html, "html.parser")
    anuncios = soup.select("li.un_anuncio")
    if not anuncios:
        raise ScraperError(ERR_STRUCTURE, "No se encontró ningún 'li.un_anuncio' en el sumario")

    municipios = load_municipios(province="Valladolid")
    detected_at = datetime.now(timezone.utc).isoformat()
    out: list[dict] = []

    for li in anuncios:
        emisor_el = li.select_one("p.bop_tit_articulo")
        titulo_el = li.select_one("p.bop_res_articulo a")
        if not emisor_el or not titulo_el:
            continue  # bloque sin la estructura esperada: se ignora, no se adivina

        emisor = emisor_el.get_text(strip=True)
        municipio = match_municipio(emisor, municipios)
        if municipio is None:
            continue  # anuncio fuera de la comarca

        pdf_url = titulo_el.get("href", "").strip()
        titulo = (titulo_el.get("title") or titulo_el.get_text(strip=True)).strip()
        cve_el = li.select_one("a.cve_link")
        cve = cve_el.get_text(strip=True) if cve_el else ""

        m = PDF_DATE_RE.search(pdf_url)
        if not m:
            raise ScraperError(ERR_PARSE, f"No se pudo extraer la fecha de {pdf_url!r}")
        published_at = parse_spanish_date(*m.groups())

        # El CVE es el código oficial de verificación del anuncio: identificador
        # estable. Si faltara, se cae a la URL del PDF, que también es única.
        out.append({
            "municipality_slug": municipio.slug,
            "municipality_name": municipio.name,
            "title": titulo,
            "source_type": "bop",
            "url_original": pdf_url,
            "file_url": pdf_url,
            "published_at": published_at.isoformat(),
            "detected_at": detected_at,
            "hash": sha256(cve or pdf_url),
            "confidence": "high",
            "requires_review": True,
            "status": "new",
            "metadata": {"cve": cve, "emisor": emisor, "scraper": "SCR-006"},
        })
    return out


def to_db_rows(docs: list[dict], source_id: str, muni_ids: dict[str, str]) -> list[dict]:
    rows = []
    for d in docs:
        row = {k: v for k, v in d.items() if k not in ("municipality_slug", "municipality_name")}
        row["source_id"] = source_id
        row["municipality_id"] = muni_ids.get(d["municipality_slug"])
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-006 — BOP de Valladolid")
    ap.add_argument("--dry-run", action="store_true", help="no escribe en la base de datos")
    args = ap.parse_args()

    try:
        html = fetch(SUMARIO_URL)
        docs = parse_sumario(html)
    except ScraperError as exc:
        print(f"ERROR [{exc.error_type}] {exc}", file=sys.stderr)
        return 1

    print(f"Anuncios de Tierra de Campos (Valladolid) en el sumario: {len(docs)}")
    for d in docs:
        print(f"  · {d['municipality_name']:<24} {d['published_at']}  {d['title'][:70]}")

    if args.dry_run:
        print("\n--dry-run: no se escribe en la base de datos.")
        if docs:
            print(json.dumps(docs[0], ensure_ascii=False, indent=2))
        return 0

    try:
        db = Supabase()
        source = db.source_by_slug(SOURCE_SLUG)
        run_id = db.start_run(source["id"])
    except ScraperError as exc:
        print(f"ERROR [{exc.error_type}] {exc}", file=sys.stderr)
        return 1

    try:
        rows = to_db_rows(docs, source["id"], db.municipality_ids())
        nuevos = db.insert_documents(rows)
        db.finish_run(run_id, status="ok", found=len(docs), new=nuevos)
        print(f"\nGuardados {nuevos} documentos nuevos (de {len(docs)} encontrados).")
        return 0
    except ScraperError as exc:
        db.finish_run(run_id, status="error", found=len(docs),
                      error_type=exc.error_type, error_message=str(exc))
        print(f"ERROR [{exc.error_type}] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
