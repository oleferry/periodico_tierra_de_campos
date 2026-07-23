"""Busca en Wikimedia Commons una foto de portada con licencia libre para cada
pueblo que ya tiene ficha, como imagen de cabecera MIENTRAS no haya fotos de
vecinos (ver sitegen/build.py: sección "Fotos de <pueblo>", que sigue siendo
la fuente principal — esto es solo un relleno honesto, nunca sustituye a esa
sección ni se mezcla con ella).

Por qué Wikimedia Commons y no "buscar fotos por internet": la inmensa
mayoría de fotos de un pueblo de 200 habitantes que se encuentran buscando
son de terceros sin licencia clara (turismo autonómico, blogs, Instagram) —
exactamente el mismo riesgo de derechos que ya evitamos con las noticias
(editorial/politica_editorial.md). Commons solo indexa contenido con licencia
libre verificada (CC0, dominio público, CC-BY, CC-BY-SA) y expone esa
licencia y el autor por API, así que se puede dar crédito correcto siempre.

No se usa scrapers.common.fetch(): esto es la API pública de Wikimedia
(api.php), pensada para consumo programático, no una web a la que aplicar
la lógica de robots.txt de un scraper (mismo criterio que scrapers/bdns.py
con la API de la BDNS).

Licencias aceptadas (con atributo, nunca sin él): dominio público, CC0,
CC-BY y CC-BY-SA en cualquier versión. Se descarta cualquier cosa con
cláusula NC (no comercial) o ND (sin obra derivada): un medio de noticias
es uso comercial, y NC/ND no lo permiten sin más permiso.

Uso:
    python -m scripts.buscar_fotos_libres --dry-run
    python -m scripts.buscar_fotos_libres
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests

from scrapers.common import ROOT, load_municipios

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "ElTerracampinoBot/0.1 (+https://elterracampino.es; contacto vía repo GitHub)"}

DESTINO_JSON = ROOT / "data" / "fotos_libres.json"
DESTINO_IMG = ROOT / "web" / "assets" / "fotos-libres"

# Prefijos de licencia aceptados (LicenseShortName normalizado a minúsculas).
# Todo lo demás (NC, ND, o sin extmetadata de licencia) se descarta.
LICENCIAS_OK = ("cc0", "public domain", "pd", "cc-by-4.0", "cc-by-3.0", "cc-by-2.0",
                 "cc-by-sa-4.0", "cc-by-sa-3.0", "cc-by-sa-2.0", "cc by", "cc by-sa")

# Ficheros que casi nunca son "una foto del pueblo": escudos, banderas, mapas,
# logotipos. Se descartan por nombre de archivo antes de gastar una llamada
# de imageinfo en ellos.
DESCARTAR_TITULO = re.compile(
    r"(escudo|coat of arms|bandera|flag|mapa|map of|ubicaci|location|localizaci|"
    r"logo|blazon|situaci�n|situacion)", re.I,
)

# Lo mismo pero mirando las CATEGORÍAS del fichero en vez del título: pilla
# casos como "Escfuen.jpg" (nombre de archivo abreviado, sin "escudo" en el
# título, pero categorizado como "Coats of arms of municipalities...").
DESCARTAR_CATEGORIA = re.compile(
    r"(coats? of arms|blazon|flags? of|maps? of|logo|seal of)", re.I,
)

TAG_RE = re.compile(r"<[^>]+>")

# Para elegir ENTRE varios candidatos válidos: preferir algo reconocible del
# pueblo (iglesia, plaza, ayuntamiento...) antes que la primera foto válida
# por orden alfabético, que puede ser cualquier cosa (un aprovechamiento
# forestal, una nave industrial...) igual de legítima pero menos
# representativa como cabecera de la ficha.
PALABRAS_BUENAS = re.compile(
    r"(iglesia|plaza|castillo|ayuntamiento|puente|ermita|torre|catedral|"
    r"monasterio|panor�mica|panoramica|vista|calle|casco|patrimonio|palacio)",
    re.I,
)


def _limpio(s: str) -> str:
    return TAG_RE.sub("", s or "").strip()


def _get(params: dict) -> dict:
    params = {**params, "format": "json"}
    r = requests.get(API, params=params, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.json()


def _candidatos(nombre_pueblo: str, provincia: str) -> tuple[list[str], bool]:
    """Títulos de fichero candidatos y si vinieron de una CATEGORÍA (fiable:
    un humano clasificó esa foto como "de este pueblo") o de una búsqueda de
    texto libre (menos fiable: puede colar homónimos, como el género de
    insecto "Cea" para el pueblo de Cea). Se devuelve el origen para que
    _mejor_foto solo aplique la comprobación extra de provincia/España al
    camino de búsqueda de texto, sin descartar por error fotos de categoría
    ya bien clasificadas simplemente porque su descripción no repite la
    provincia."""
    # La categoría con provincia va PRIMERO: "Category:Cea" a secas es
    # ambigua en Commons (mezcla el pueblo con un género de insecto llamado
    # igual) mientras que "Category:Cea, León" ya viene desambiguada por
    # humanos. Si se probara al revés, la categoría ambigua "gana" en cuanto
    # tiene algún miembro válido y nunca se llega a la buena.
    for categoria in (f"{nombre_pueblo}, {provincia}", nombre_pueblo):
        data = _get({
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{categoria}", "cmnamespace": "6", "cmlimit": "20",
        })
        miembros = data.get("query", {}).get("categorymembers", [])
        titulos = [m["title"] for m in miembros if not DESCARTAR_TITULO.search(m["title"])]
        if titulos:
            return titulos, True

    data = _get({
        "action": "query", "list": "search",
        "srsearch": f'"{nombre_pueblo}" {provincia} España', "srnamespace": "6", "srlimit": "15",
    })
    resultados = data.get("query", {}).get("search", [])
    return [r["title"] for r in resultados if not DESCARTAR_TITULO.search(r["title"])], False


def _mejor_foto(titulos: list[str], provincia: str, *, via_categoria: bool) -> dict | None:
    """De una lista de ficheros candidatos, la primera que tenga licencia
    libre aceptada, sea una imagen de verdad (no escudo/mapa/logo colado por
    nombre de archivo ambiguo) y, si vino de la búsqueda de texto libre (no
    de categoría), esté realmente ubicada en la provincia correcta (evita
    falsos positivos por homónimos, p. ej. "Cea" pueblo vs. "Cea" género de
    insecto en la taxonomía de Commons)."""
    if not titulos:
        return None
    data = _get({
        "action": "query", "titles": "|".join(titulos[:20]), "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime", "iiurlwidth": "1600",
    })
    paginas = data.get("query", {}).get("pages", {})
    validos = []
    for pagina in paginas.values():
        info_list = pagina.get("imageinfo")
        if not info_list:
            continue
        info = info_list[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        titulo = pagina.get("title", "")
        categorias = meta.get("Categories", {}).get("value", "")
        descripcion = _limpio(meta.get("ImageDescription", {}).get("value", ""))
        if DESCARTAR_CATEGORIA.search(categorias) or DESCARTAR_CATEGORIA.search(titulo):
            continue
        if not via_categoria:
            contexto = f"{categorias} {descripcion} {titulo}"
            if not re.search(rf"{re.escape(provincia)}|Espa.a|Spain", contexto, re.I):
                continue
        licencia_corta = (meta.get("LicenseShortName", {}).get("value") or "").strip().lower()
        if not any(licencia_corta.startswith(p) or p in licencia_corta for p in LICENCIAS_OK):
            continue
        validos.append({
            "titulo": titulo,
            "url_imagen": info.get("thumburl") or info.get("url"),
            "pagina_commons": f"https://commons.wikimedia.org/wiki/{titulo.replace(' ', '_')}",
            "autor": _limpio(meta.get("Artist", {}).get("value", "")) or "Wikimedia Commons",
            "licencia": meta.get("LicenseShortName", {}).get("value", "").strip() or "Dominio público",
            "licencia_url": meta.get("LicenseUrl", {}).get("value", "").strip(),
        })
    if not validos:
        return None
    # Preservar el orden original (más relevante según Commons) salvo que
    # alguno "suene" a monumento reconocible: ese va primero.
    validos.sort(key=lambda f: 0 if PALABRAS_BUENAS.search(f["titulo"]) else 1)
    return validos[0]


def buscar_para(slug: str, nombre: str, provincia: str) -> dict | None:
    titulos, via_categoria = _candidatos(nombre, provincia)
    foto = _mejor_foto(titulos, provincia, via_categoria=via_categoria)
    if not foto:
        return None
    return {"slug": slug, "municipality_name": nombre, **foto}


def main() -> int:
    ap = argparse.ArgumentParser(description="Fotos de portada con licencia libre desde Wikimedia Commons")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime, no descarga ni guarda")
    args = ap.parse_args()

    slugs_con_ficha = sorted(p.stem for p in (ROOT / "web" / "municipio").glob("*.html"))
    municipios = {m.slug: m for m in load_municipios()}

    existentes = json.loads(DESTINO_JSON.read_text(encoding="utf-8")) if DESTINO_JSON.exists() else {}

    encontradas = 0
    for slug in slugs_con_ficha:
        if slug in existentes:
            continue
        m = municipios.get(slug)
        if not m:
            print(f"  aviso: {slug} no está en el CSV maestro, se salta", file=sys.stderr)
            continue
        try:
            foto = buscar_para(slug, m.name, m.province)
        except requests.RequestException as exc:
            print(f"  aviso: fallo consultando Commons para {m.name}: {exc}", file=sys.stderr)
            continue

        if not foto:
            print(f"  · {m.name}: sin foto libre disponible en Commons")
            continue

        print(f"  · {m.name}: {foto['titulo']} — {foto['autor']} ({foto['licencia']})")
        encontradas += 1
        if args.dry_run:
            continue

        DESTINO_IMG.mkdir(parents=True, exist_ok=True)
        archivo = f"{slug}.jpg"
        img = requests.get(foto["url_imagen"], headers=HEADERS, timeout=25)
        img.raise_for_status()
        (DESTINO_IMG / archivo).write_bytes(img.content)
        foto["archivo"] = archivo
        existentes[slug] = foto
        DESTINO_JSON.write_text(json.dumps(existentes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{encontradas} foto(s) libre(s) nueva(s) encontrada(s) de {len(slugs_con_ficha)} pueblos con ficha.")
    if args.dry_run:
        print("(modo --dry-run: no se ha descargado ni guardado nada)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
