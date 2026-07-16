"""SCR-014 — Ayudas y subvenciones reales (Base de Datos Nacional de Subvenciones).

La BDNS es obligatoria por ley (Ley 38/2003 General de Subvenciones): toda
ayuda pública española, la dé quien la dé, tiene que registrarse ahí para
ser válida. API pública, sin robots.txt en el dominio, documentada de forma
extraoficial en https://github.com/cruzlorite/bdns-fetch (el proyecto oficial
no publica un spec claro, se ha verificado cada parámetro a mano contra la
API real antes de escribir esto).

Alcance de este scraper (v1): SOLO nivel local —
  · Ayudas y convenios de los propios ayuntamientos de los 12 pilotos.
  · Ayudas de las 4 diputaciones (Valladolid, Palencia, León, Zamora), que en
    la BDNS están clasificadas como tipoAdministracion='L' igual que los
    ayuntamientos. Suelen ser justo las que apuntan a pueblos pequeños (ver
    el "Plan Bienal" que pidió Mayorga en scrapers/plenos_sedelectronica.py).
    Como una ayuda de diputación no es "de" un pueblo concreto sino de toda
    la provincia, se trata como contenido COMÚN de la comarca (igual que la
    huerta o la agenda en sitegen/build.py), no se atribuye a un municipio.

Lo autonómico (JCyL) y nacional queda FUERA por ahora a propósito: hay más de
6.000 convocatorias activas solo en Castilla y León, la mayoría irrelevantes
para un vecino de Tierra de Campos (subvenciones a hospitales, universidades,
fundaciones de otras provincias...). Filtrarlo bien necesita un filtro de
materia/sector, no solo de administración — pendiente como fase 2.

Dos llamadas por resultado: /convocatorias/busqueda para listar (barato, un
municipio o diputación entera de una vez) y /convocatorias?numConv=X para el
detalle completo (importe, plazo, beneficiarios, bases) de cada una que de
verdad nos interesa — no se piden detalles de todo lo que devuelve la
búsqueda, solo de lo que ya ha pasado el filtro de entidad.

Uso:
    python -m scrapers.bdns --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from scrapers.common import ERR_NETWORK, REQUEST_TIMEOUT, ScraperError, sha256, strip_accents

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

API = "https://www.pap.hacienda.gob.es/bdnstrans/api"
# El WAF de Hacienda es más permisivo que el del INE, pero por si acaso se usa
# el mismo tipo de User-Agent de navegador (nada de "bot" en el nombre).
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ElTerracampino/0.1; +https://elterracampino.es)"}

# id de "región de impacto" en la BDNS para cada provincia (ver /organos y /regiones).
REGION_PROVINCIA = {"Valladolid": 37, "Palencia": 33, "León": 32, "Zamora": 38}
DIPUTACIONES = {p: f"DIPUTACIÓN PROVINCIAL DE {strip_accents(p).upper()}" for p in REGION_PROVINCIA}

# Cuántas convocatorias recientes (ordenadas por fecha desc) se revisan por
# provincia en cada pasada: las propias de un ayuntamiento pequeño son raras,
# con esto basta para no perderse nada de las últimas semanas sin traerse
# las 5.000+ convocatorias históricas de cada provincia.
PAGINA_RECIENTE = 250


def _get(url: str) -> dict:
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise ScraperError(ERR_NETWORK, f"{type(exc).__name__}: {exc}") from exc
    if r.status_code >= 400:
        raise ScraperError(ERR_NETWORK, f"HTTP {r.status_code} en {url}")
    return r.json()


def _listado_provincia(provincia: str) -> list[dict]:
    region = REGION_PROVINCIA[provincia]
    url = (f"{API}/convocatorias/busqueda?vpd=GE&pageSize={PAGINA_RECIENTE}&page=0"
           f"&regiones={region}&tipoAdministracion=L&order=fechaRecepcion&direccion=desc")
    return _get(url).get("content", [])


def _detalle(num_convocatoria: str) -> dict:
    return _get(f"{API}/convocatorias?vpd=GE&numConv={num_convocatoria}")


def _texto_ayuda(detalle: dict) -> str:
    """Todo lo relevante del detalle, en texto plano, para pasárselo a la IA
    (mismo patrón que doc['acta_texto'] en scrapers/plenos_sedelectronica.py:
    no se inventa nada, se le da a la IA el material real y que redacte)."""
    partes = [f"Título: {detalle.get('descripcion', '')}"]
    if detalle.get("descripcionFinalidad"):
        partes.append(f"Finalidad: {detalle['descripcionFinalidad']}")
    beneficiarios = ", ".join(b["descripcion"] for b in detalle.get("tiposBeneficiarios", []))
    if beneficiarios:
        partes.append(f"Quién puede pedirla: {beneficiarios}")
    if detalle.get("presupuestoTotal"):
        partes.append(f"Presupuesto total: {detalle['presupuestoTotal']} €")
    if detalle.get("fechaInicioSolicitud") or detalle.get("fechaFinSolicitud"):
        partes.append(f"Plazo de solicitud: del {detalle.get('fechaInicioSolicitud', '?')} "
                       f"al {detalle.get('fechaFinSolicitud', '?')}")
    partes.append(f"Abierto ahora mismo: {'sí' if detalle.get('abierto') else 'no'}")
    if detalle.get("descripcionBasesReguladoras"):
        partes.append(f"Bases reguladoras: {detalle['descripcionBasesReguladoras']}")
    return "\n".join(partes)


def _titulo_es(s: str) -> str:
    """Title-case a la española: minúscula en preposiciones/artículos cortos,
    salvo la primera palabra. .title() de Python capitaliza 'De'/'La' y queda mal."""
    minusculas = {"de", "la", "el", "los", "las", "y"}
    palabras = s.lower().split(" ")
    return " ".join(p if i > 0 and p in minusculas else p.capitalize() for i, p in enumerate(palabras))


def _a_documento(item: dict, detalle: dict, *, municipio_slug: str | None, entidad: str) -> dict:
    return {
        "municipality_slug": municipio_slug,  # None = contenido común de la comarca (ver docstring)
        "municipality_name": _titulo_es(entidad.removeprefix("AYUNTAMIENTO DE ")),
        "title": detalle.get("descripcion", "").strip(),
        "source_type": "subvencion",
        "url_original": f"https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/{item['id']}",
        "file_url": None,
        "published_at": item.get("fechaRecepcion"),
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "ayuda_texto": _texto_ayuda(detalle),
        "ayuda_abierta": bool(detalle.get("abierto")),
        "presupuesto_total": detalle.get("presupuestoTotal"),
        "hash": sha256(f"bdns-{item['id']}"),
        "confidence": "high",
        "requires_review": True,
        "status": "new",
        "metadata": {"organismo": entidad, "codigoBDNS": item.get("numeroConvocatoria"), "scraper": "SCR-014"},
    }


def fetch_ayudas(municipios: list[tuple[str, str]]) -> dict[str, list[dict]]:
    """Devuelve {'<slug>': [...]} para ayudas propias de cada ayuntamiento, más
    una clave especial 'comarca' con las de las 4 diputaciones (sin municipio
    concreto). `municipios` es una lista de (nombre, slug).

    Una diputación provincial publica cientos de decretos/convenios rutinarios
    que no tienen nada que ver con Tierra de Campos (asociaciones de la capital,
    trámites internos...) — de ahí SOLO se guardan los que citan expresamente
    a uno de nuestros pueblos en el título; el resto se descarta como ruido,
    no como "toda ayuda de la diputación", que sería demasiado."""
    por_provincia: dict[str, list] = {}
    for provincia in REGION_PROVINCIA:
        por_provincia[provincia] = _listado_provincia(provincia)

    entidad_a_slug = {f"AYUNTAMIENTO DE {strip_accents(nombre).upper()}": slug for nombre, slug in municipios}
    nombres_pueblos = [strip_accents(nombre).upper() for nombre, _ in municipios]
    # Nombres de OTROS municipios (no nuestros) que contienen el nombre de un
    # piloto como subcadena (p.ej. 'Saelices de Mayorga' contiene 'Mayorga') —
    # mismo problema ya visto en scrapers/bocyl.py. Se quitan del título ANTES
    # de buscar, para no confundir una mención al pueblo ajeno con el nuestro.
    FALSOS_AMIGOS = ["SAELICES DE MAYORGA", "VEGA DE VILLALOBOS"]

    resultado: dict[str, list[dict]] = {"comarca": []}
    vistos: set[str] = set()
    for provincia, items in por_provincia.items():
        diputacion = DIPUTACIONES[provincia]
        for item in items:
            entidad = (item.get("nivel3") or "").strip()
            entidad_norm = strip_accents(entidad).upper()
            slug = entidad_a_slug.get(entidad_norm)
            es_diputacion = entidad_norm == strip_accents(diputacion).upper()
            if not slug and not es_diputacion:
                continue  # no es ninguna de nuestras entidades: se descarta

            titulo_norm = strip_accents(item.get("descripcion") or "").upper()
            for falso_amigo in FALSOS_AMIGOS:
                titulo_norm = titulo_norm.replace(falso_amigo, "")
            if es_diputacion and not any(p in titulo_norm for p in nombres_pueblos):
                continue  # decreto/convenio de diputación que no cita a ningún pueblo nuestro

            clave = item.get("numeroConvocatoria") or str(item["id"])
            if clave in vistos:
                continue
            vistos.add(clave)

            detalle = _detalle(clave)
            doc = _a_documento(item, detalle, municipio_slug=slug, entidad=entidad)
            resultado.setdefault(slug or "comarca", []).append(doc)
    return resultado


def main() -> int:
    from scrapers.common import load_municipios

    ap = argparse.ArgumentParser(description="SCR-014 — Ayudas y subvenciones (BDNS)")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime (no hay escritura en BD todavía)")
    ap.parse_args()

    from sitegen.build import PILOTS
    municipios = [(m.name, m.slug) for m in load_municipios() if m.slug in PILOTS]

    try:
        por_slug = fetch_ayudas(municipios)
    except ScraperError as exc:
        print(f"ERROR [{exc.error_type}] {exc}", file=sys.stderr)
        return 1

    total = 0
    for slug, docs in por_slug.items():
        if not docs:
            continue
        total += len(docs)
        print(f"\n== {slug} — {len(docs)} ayudas ==")
        for d in docs:
            print(f"  · {d['published_at']}  [{d['metadata']['organismo']}] {d['title'][:70]}")
    print(f"\nTotal: {total} ayudas relevantes encontradas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
