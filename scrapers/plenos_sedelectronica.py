"""SCR-013 — Actas de pleno reales desde el portal de transparencia (espublico/sedelectronica.es).

ACCESO AUTORIZADO EXPRESAMENTE, NO POR DEFECTO. El robots.txt de sedelectronica.es
prohíbe el rastreo de todo lo que no sea la portada:

    User-agent: *
    Disallow: /*
    Allow: /info$
    Allow: /info.0$
    Allow: /$

Por eso este scraper NO se activa por defecto: solo lee municipios listados en
SITIOS, y cada entrada debe tener una autorización explícita y verificable del
propio ayuntamiento (no basta con "es dato público", el robots.txt del
proveedor dice lo contrario). Antes de añadir un municipio nuevo aquí, pedir
permiso igual que se hizo con Mayorga — no asumir que vale para los demás
pueblos de la plataforma solo porque comparten proveedor.

  · Mayorga: autorización verbal explícita del alcalde al usuario del
    proyecto (2026-07-13). El usuario asume la responsabilidad de este acceso.

Por qué hace falta un navegador de verdad (Playwright) y no solo requests:
el listado de actas por año no es un enlace normal, es una llamada AJAX de
Wicket con un token de sesión firmado (`wicketAjaxGet('...?x=<token>'...)`)
que solo se genera correctamente ejecutando el JavaScript de la página; un
GET directo a esa URL con requests devuelve la pantalla de identificación,
no el listado. Una vez tenemos el enlace final a cada documento
(`/preview-document/<uuid>`), esa parte SÍ funciona con requests normales
(devuelve un iframe con un PDF tokenizado, se resuelve con una sola sesión
de cookies, sin necesidad de navegador).

Fase actual (v1): capturamos fecha, tipo de sesión y enlace al PDF de cada
acta — no el contenido. Es un enlace real y verificable, como BOP/BOCyL.
Extraer el texto del PDF para sacar los acuerdos concretos (fase 2, más
jugosa para redactar titulares) queda pendiente.

Uso:
    python -m scrapers.plenos_sedelectronica --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

import requests
from playwright.sync_api import sync_playwright

from scrapers.common import ERR_NETWORK, REQUEST_TIMEOUT, USER_AGENT, ScraperError, sha256

SITIOS = {
    "mayorga": {
        "listado_url": "https://mayorga.sedelectronica.es/transparency/53907f69-f524-430f-b6cd-25b084600825/",
        "nombre": "Ayuntamiento de Mayorga",
    },
}

# Cuántas carpetas de año recorrer (la más reciente primero): para noticias del
# día a día basta con el año en curso y el anterior, no hace falta bajar a 2017.
ANIOS_A_LEER = 2

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _tipo_sesion(titulo: str) -> str:
    t = titulo.lower()
    if "constitutiv" in t:
        return "Sesión constitutiva del Ayuntamiento"
    if "extraordinaria y urgente" in t or "extraordinario y urgente" in t:
        return "Pleno extraordinario y urgente"
    if "extraordinari" in t:
        return "Pleno extraordinario"
    if "ordinari" in t:
        return "Pleno ordinario"
    return "Pleno municipal"


def _fecha_sesion_de_titulo(titulo: str) -> str | None:
    """Intenta leer la fecha DE LA SESIÓN (no la de creación del documento) a
    partir del nombre del archivo, para el titular. Es orientativa: la fecha
    fiable para published_at es 'Fecha de creación' del propio documento."""
    m = re.search(r"(\d{1,2})\s*(?:de\s+)?([a-záéíóú]+)\s*(?:de\s+)?(\d{4})", titulo, re.I)
    if m:
        dia, mes_txt, anio = m.groups()
        mes = MESES.get(mes_txt.lower())
        if mes:
            return f"{int(dia)} de {mes_txt.lower()} de {anio}"
    return None


def _fecha_creacion(session: requests.Session, preview_url: str) -> str | None:
    """'Fecha de creación' del documento en el portal (cuándo se hizo público),
    formato dd-mmm-yyyy. Es la fecha fiable para ordenar/mostrar, a falta de
    parsear el PDF para la fecha exacta de la sesión."""
    try:
        r = session.get(preview_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise ScraperError(ERR_NETWORK, f"{type(exc).__name__}: {exc}") from exc
    m = re.search(r"Fecha de creaci[oó]n\D*(\d{2}-\w{3}-\d{4})", r.text, re.I)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d-%b-%Y").date().isoformat()
    except ValueError:
        return None


def _listar_documentos(listado_url: str, anios: int) -> list[dict]:
    """Usa un navegador real para expandir los N años más recientes y recoger
    (título, enlace a preview-document) de cada acta. Ver docstring del módulo:
    esta parte no se puede hacer con requests, el listado es AJAX firmado."""
    encontrados: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        try:
            page.goto(listado_url, wait_until="networkidle", timeout=30000)
            enlaces_anio = page.locator("a.gIconLink.exp").all_text_contents()
            for texto in enlaces_anio[:anios]:
                with page.expect_navigation(wait_until="networkidle", timeout=20000):
                    page.click(f"text={texto}", timeout=10000)
                docs = page.eval_on_selector_all(
                    'a[href*="preview-document"]',
                    "els => els.map(e => ({href: e.href, texto: e.textContent.trim()}))",
                )
                encontrados.extend(docs)
                page.go_back(wait_until="networkidle", timeout=20000)
        finally:
            browser.close()
    return encontrados


def fetch_plenos(municipio_slug: str) -> list[dict]:
    sitio = SITIOS.get(municipio_slug)
    if not sitio:
        return []

    documentos = _listar_documentos(sitio["listado_url"], ANIOS_A_LEER)

    session = requests.Session()
    detected_at = datetime.now(timezone.utc).isoformat()
    out: list[dict] = []
    for d in documentos:
        titulo_original = d["texto"]
        if "plantilla" in titulo_original.lower():
            continue  # plantilla en blanco subida por error, no es un acta real

        fecha = _fecha_creacion(session, d["href"])
        if not fecha:
            continue  # sin fecha fiable, no se publica (mejor omitir que inventar)

        fecha_sesion = _fecha_sesion_de_titulo(titulo_original)
        tipo = _tipo_sesion(titulo_original)
        titulo = f"{tipo} de {sitio['nombre'].removeprefix('Ayuntamiento de ')}"
        if fecha_sesion:
            titulo += f", sesión del {fecha_sesion}"

        out.append({
            "municipality_slug": municipio_slug,
            "municipality_name": sitio["nombre"].removeprefix("Ayuntamiento de "),
            "title": titulo,
            "source_type": "municipal_plenary",
            "url_original": d["href"],
            "file_url": d["href"],
            "published_at": fecha,
            "detected_at": detected_at,
            "hash": sha256(d["href"]),
            "confidence": "high",
            "requires_review": True,
            "status": "new",
            "metadata": {
                "organismo": sitio["nombre"],
                "titulo_original": titulo_original,
                "scraper": "SCR-013",
                "autorizacion": "acceso autorizado expresamente por el ayuntamiento, ver docstring del módulo",
            },
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-013 — Actas de pleno (sedelectronica.es, solo municipios autorizados)")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime (no hay escritura en BD todavía)")
    ap.parse_args()

    exit_code = 0
    for slug in SITIOS:
        try:
            docs = fetch_plenos(slug)
        except ScraperError as exc:
            print(f"ERROR [{exc.error_type}] {slug}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        print(f"\n== {slug} — {len(docs)} actas ==")
        for d in docs:
            print(f"  · {d['published_at']}  {d['title']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
