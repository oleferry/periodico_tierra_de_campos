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
  · Paredes de Nava, Sahagún y Villalón de Campos: confirmación telefónica de
    cada ayuntamiento al usuario del proyecto (2026-11-24): "no hay problema en
    leerlo, es público". El usuario asume la responsabilidad de este acceso.

Cada sede ordena las actas a su manera y el listado las admite todas:
carpetas por año en cualquier orden (Mayorga, de nueva a vieja; Sahagún, de
vieja a nueva), actas sueltas en la propia carpeta (Paredes, Villalón y las de
2026 de Sahagún) y el botón "Mostrar más", que pagina de 10 en 10.

Por qué hace falta un navegador de verdad (Playwright) y no solo requests:
el listado de actas por año no es un enlace normal, es una llamada AJAX de
Wicket con un token de sesión firmado (`wicketAjaxGet('...?x=<token>'...)`)
que solo se genera correctamente ejecutando el JavaScript de la página; un
GET directo a esa URL con requests devuelve la pantalla de identificación,
no el listado. Una vez tenemos el enlace final a cada documento
(`/preview-document/<uuid>`), esa parte SÍ funciona con requests normales
(devuelve un iframe con un PDF tokenizado, se resuelve con una sola sesión
de cookies, sin necesidad de navegador).

Además de fecha, tipo de sesión y enlace al PDF, se extrae el TEXTO del acta
(son PDF nativos, no escaneados: pypdf lee el texto directamente, sin OCR) y
se guarda en doc['acta_texto'] para que sitegen/ia.py:redactar_pleno() saque
de ahí el titular real (qué se aprobó, qué se denegó) en vez de solo "hubo un
pleno". Si el PDF no da texto legible, se deja tal cual — no se inventa.

Uso:
    python -m scrapers.plenos_sedelectronica --dry-run
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, sync_playwright
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from scrapers.common import ERR_NETWORK, REQUEST_TIMEOUT, USER_AGENT, ScraperError, sha256

SITIOS = {
    "mayorga": {
        "listado_url": "https://mayorga.sedelectronica.es/transparency/53907f69-f524-430f-b6cd-25b084600825/",
        "nombre": "Ayuntamiento de Mayorga",
    },
    # 1.5.1.2. ACTAS de cada portal de transparencia (localizadas 2026-11-24).
    "paredes-de-nava": {
        "listado_url": "https://paredesdenava.sedelectronica.es/transparency/e44e9c40-f899-47e5-94ef-a1a71759ccea/",
        "nombre": "Ayuntamiento de Paredes de Nava",
    },
    "sahagun": {
        "listado_url": "https://sahagun.sedelectronica.es/transparency/c6e6cb6b-76bb-42c4-8605-08cf2a465689/",
        "nombre": "Ayuntamiento de Sahagún",
    },
    "villalon-de-campos": {
        "listado_url": "https://villalondecampos.sedelectronica.es/transparency/3dda524c-c8ba-4f7a-8f38-afc9918e456d/",
        "nombre": "Ayuntamiento de Villalón de Campos",
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
    # "extra" cubre también las abreviaturas de Paredes: "PLENO EXTRA. 30-03-2026",
    # "PLENO EXTRA.URGENTE 29-11-2023".
    if "extra" in t and "urgente" in t:
        return "Pleno extraordinario y urgente"
    if "extra" in t:
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
    # Paredes de Nava: "[PLENO ORDINARIO 18-06-2026]"
    m = re.search(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})(?!\d)", titulo)
    if m:
        dia, mes, anio = (int(x) for x in m.groups())
        if 1 <= mes <= 12 and 1 <= dia <= 31:
            nombre_mes = next(k for k, v in MESES.items() if v == mes)
            return f"{dia} de {nombre_mes} de {anio}"
    return None


# Tope de texto extraído por acta que se manda a la IA: las actas de estos
# plenos son de pocas páginas, esto es margen de sobra sin disparar el coste.
MAX_TEXTO_ACTA = 12000


def _documento(session: requests.Session, preview_url: str) -> dict:
    """Una sola visita a preview-document: de ahí sale la fecha de creación Y
    el enlace tokenizado al PDF real (visor embebido en un iframe)."""
    try:
        r = session.get(preview_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise ScraperError(ERR_NETWORK, f"{type(exc).__name__}: {exc}") from exc

    fecha = None
    m_fecha = re.search(r"Fecha de creaci[oó]n\D*(\d{2}-\w{3}-\d{4})", r.text, re.I)
    if m_fecha:
        try:
            fecha = datetime.strptime(m_fecha.group(1), "%d-%b-%Y").date().isoformat()
        except ValueError:
            pass

    texto = None
    m_pdf = re.search(r'/preview/pdf/[^"\']+\.pdf', r.text)
    if m_pdf:
        try:
            base = f"{urlsplit(preview_url).scheme}://{urlsplit(preview_url).netloc}"
            r_pdf = session.get(base + m_pdf.group(0),
                                 headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
            reader = PdfReader(io.BytesIO(r_pdf.content))
            texto = "\n".join(p.extract_text() or "" for p in reader.pages)[:MAX_TEXTO_ACTA].strip() or None
        except (requests.RequestException, PdfReadError):
            texto = None  # sin texto no se inventa nada; se queda solo con fecha+tipo

    return {"fecha": fecha, "texto": texto}


def _expandir(page) -> None:
    """Pulsa "Mostrar más" (paginación AJAX de 10 en 10) hasta que no quede."""
    for _ in range(40):
        boton = page.locator(".more_results button")
        if boton.count() == 0 or not boton.first.is_visible():
            return
        # Se cuentan actas Y carpetas (las dos llevan .gIconLink): en Mayorga el
        # botón carga más carpetas de años, no actas.
        # Con justo 10 elementos el botón sale igual y al pulsarlo no añade nada,
        # solo desaparece (Mayorga, carpeta de 2026): se espera a lo que pase
        # antes. Si ni eso, se sigue con lo ya cargado en vez de fallar.
        antes = page.locator("a.gIconLink").count()
        boton.first.click()
        try:
            page.wait_for_function(
                "n => document.querySelectorAll('a.gIconLink').length > n"
                " || !document.querySelector('.more_results button')",
                arg=antes, timeout=15000)
        except PlaywrightTimeout:
            return


def _docs(page) -> list[dict]:
    return page.eval_on_selector_all(
        'a[href*="preview-document"]',
        "els => els.map(e => ({href: e.href, texto: e.textContent.trim()}))",
    )


def _anio(texto: str) -> int | None:
    m = re.findall(r"(?<!\d)(20\d{2})(?!\d)", texto) or re.findall(r"(?<!\d)(20\d{2})\d{4}_", texto)
    return int(m[-1]) if m else None


def _listar_documentos(listado_url: str, anios: int) -> list[dict]:
    """Usa un navegador real para recoger (título, enlace a preview-document)
    de las actas recientes. Ver docstring del módulo: esta parte no se puede
    hacer con requests, el listado es AJAX firmado.

    Recientes = de los `anios` últimos años naturales. Vale para las tres
    formas de ordenar que hay: actas sueltas (se filtran por el año que traen
    en el título; si no traen ninguno, se quedan) y carpetas por año (se
    eligen por el número, no por la posición, que en cada sede va al revés)."""
    desde = datetime.now(timezone.utc).year - anios + 1
    encontrados: list[dict] = []
    try:
        with sync_playwright() as p:
            # launch() va DENTRO del try a propósito: si el navegador Chromium no
            # está instalado, launch() lanza aquí y hay que envolverlo igual que
            # un timeout de red. Si quedara fuera, tumbaría el build entero en
            # vez de saltarse solo este municipio. Ver .github/workflows.
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(listado_url, wait_until="networkidle", timeout=30000)
                _expandir(page)
                for d in _docs(page):
                    anio = _anio(d["texto"])
                    if anio is None or anio >= desde:
                        encontrados.append(d)

                carpetas = [t.strip() for t in page.locator("a.gIconLink.exp").all_text_contents()]
                for texto in carpetas:
                    anio = _anio(texto)
                    if anio is None or anio < desde:
                        continue
                    with page.expect_navigation(wait_until="networkidle", timeout=20000):
                        page.click(f"text={texto}", timeout=10000)
                    _expandir(page)
                    encontrados.extend(_docs(page))
                    page.go_back(wait_until="networkidle", timeout=20000)
            finally:
                browser.close()
    except PlaywrightError as exc:
        # Navegador ausente o timeout de red: no puede tumbar el build ENTERO —
        # se envuelve en ScraperError, que el resto del proyecto atrapa y sigue
        # sin este municipio, igual que cualquier otro scraper.
        raise ScraperError(ERR_NETWORK, f"navegador: {exc}") from exc
    vistos: set[str] = set()
    return [d for d in encontrados if not (d["href"] in vistos or vistos.add(d["href"]))]


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

        info = _documento(session, d["href"])
        if not info["fecha"]:
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
            "published_at": info["fecha"],
            "acta_texto": info["texto"],
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
