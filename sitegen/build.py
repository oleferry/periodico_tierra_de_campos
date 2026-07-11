"""Generador del sitio estático de El Terracampino.

Construye una web REAL con datos reales:
  · Tiempo por municipio vía Open-Meteo (scrapers/weather_openmeteo.py), en modo artículo.
  · Anuncios del BOP de Valladolid del día (scrapers/bop_valladolid.py).

Salida en web/ (index.html + web/municipio/<slug>.html). Reejecutable:
    python -m sitegen.build

`depth` = niveles por debajo de web/ (home=0, ficha de municipio=1).
"""

from __future__ import annotations

import csv
import html
import sys
from datetime import date
from pathlib import Path

from scrapers.bop_valladolid import SUMARIO_URL, parse_sumario
from scrapers.common import ScraperError, fetch
from scrapers.weather_openmeteo import geocode, weather_for

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Enlaces oficiales de los pilotos (fuente: config/municipios_piloto.yml).
MUNI_LINKS = {
    "mayorga": {"Web municipal": "https://mayorga.ayuntamientosdevalladolid.es/",
                "Plenos": "https://mayorga.ayuntamientosdevalladolid.es/el-ayuntamiento/organizacion-municipal/plenos-municipales",
                "Sede electrónica": "https://mayorga.sedelectronica.es/"},
    "villalon-de-campos": {"Web municipal": "https://villalondecampos.ayuntamientosdevalladolid.es/",
                "Plenos": "https://villalondecampos.ayuntamientosdevalladolid.es/el-ayuntamiento/organizacion-municipal/plenos-municipales",
                "Sede electrónica": "https://villalondecampos.sedelectronica.es/"},
    "villada": {"Web municipal": "https://villada.es/",
                "Actas de pleno": "https://villada.es/categoria/ayuntamiento/actas-de-pleno/",
                "Sede electrónica": "https://villada.sedelectronica.es/"},
    "medina-de-rioseco": {"Web municipal": "https://medinaderioseco.org/",
                "Plenos": "https://medinaderioseco.org/organizacion-municipal/plenos-municipales/",
                "Sede electrónica": "https://medinaderioseco.sedelectronica.es/"},
    "sahagun": {"Web municipal": "https://www.aytosahagun.es/",
                "Normativa municipal": "https://www.aytosahagun.es/ayuntamiento/normativa-municipal/",
                "Sede electrónica": "https://sahagun.sedelectronica.es/"},
    "valderas": {"Web municipal": "https://www.aytovalderas.es/",
                "Normativa municipal": "https://www.aytovalderas.es/ayuntamiento/normativa-municipal/",
                "Sede electrónica": "https://aytovalderas.sedelectronica.es/"},
    "carrion-de-los-condes": {"Web municipal": "https://carriondeloscondes.org/"},
    "paredes-de-nava": {"Web municipal": "https://paredesdenava.es/"},
    "villalpando": {"Web municipal": "https://villalpando.es/"},
    "becerril-de-campos": {"Web municipal": "https://becerrildecampos.es/"},
    "fuentes-de-nava": {"Web municipal": "https://fuentesdenava.es/"},
    "villarramiel": {"Web municipal": "https://villarramiel.es/"},
}
PILOTS = list(MUNI_LINKS.keys())

E = html.escape


def fecha_larga(d: date) -> str:
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def load_municipios() -> dict[str, dict]:
    out = {}
    with (ROOT / "data" / "municipios_tierra_de_campos.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["slug"]] = row
    return out


# --------------------------------------------------------------- plantilla

def shell(title: str, body: str, depth: int) -> str:
    css_site = "../" * depth + "assets/site.css"
    to_brand = "../" * (depth + 1) + "brand"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(title)}</title>
<link rel="icon" href="{to_brand}/logos/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@600;700&family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{to_brand}/web/brand-tokens.css">
<link rel="stylesheet" href="{css_site}">
</head>
<body class="tc-furrows">
{header(depth)}
{body}
{footer(depth)}
</body>
</html>
"""


def logo_svg() -> str:
    return """<svg width="34" height="34" viewBox="0 0 512 512" aria-hidden="true">
    <rect x="32" y="32" width="448" height="448" fill="none" stroke="#251F1A" stroke-width="16"/>
    <path d="M128 128 H384 V174 H282 V356 H230 V174 H128 Z" fill="#251F1A"/>
    <g stroke="#A65F2A" stroke-width="10" stroke-linecap="square">
      <line x1="112" y1="386" x2="400" y2="386"/><line x1="128" y1="416" x2="384" y2="416"/><line x1="148" y1="446" x2="364" y2="446"/>
    </g></svg>"""


def header(depth: int) -> str:
    home = "../" * depth + "index.html"
    return f"""<header class="tc-header"><div class="tc-wrap tc-header-inner">
  <a href="{home}" class="tc-logo">{logo_svg()}
    <span><span class="tc-logo-text" style="display:block;">El Terracampino</span>
    <span class="tc-logo-desc">Tierra de Campos en limpio</span></span></a>
  <nav class="tc-nav">
    <a href="{home}#tiempo">A ras de tierra</a>
    <a href="{home}#ayuntamiento">Ayuntamiento en limpio</a>
  </nav>
</div></header>"""


def footer(depth: int) -> str:
    home = "../" * depth + "index.html"
    return f"""<footer class="tc-footer"><div class="tc-wrap">
  <p class="tc-aviso">Este medio resume información pública procedente de fuentes oficiales y abiertas. Los resúmenes no sustituyen al documento original. Ante cualquier trámite, plazo, ayuda o acuerdo municipal, consulta siempre la fuente oficial enlazada.</p>
  <div class="tc-footer-links"><a href="{home}">Portada</a><span>El tiempo: Open-Meteo · Boletines: BOP</span><span>elterracampino.es</span></div>
</div></footer>"""


# --------------------------------------------------------------- páginas

def render_home(built: list[dict], anuncios: list[dict], hoy: date) -> str:
    cards = ""
    for m in built:
        w = m.get("weather")
        if not w:
            continue
        cards += f"""<a class="tc-card tc-weather-card" href="municipio/{m['slug']}.html">
      <p class="tc-muni-tag">{E(m['name'])}</p>
      <p class="tc-weather-temp tc-data">{w['ahora']['temp']}°</p>
      <p class="tc-pieza-cuerpo">{E(w['ahora']['desc'])} · máx {w['hoy']['max']}° / mín {w['hoy']['min']}°</p>
    </a>"""

    if anuncios:
        items = "".join(f"""<div class="tc-item">
        <a class="tc-item-titulo" href="{E(a['url_original'])}" target="_blank" rel="noopener">{E(a['title'])}</a>
        <p class="tc-item-meta">{E(a['municipality_name'])} · BOP Valladolid · {a['published_at']} · <span class="tc-sello tc-sello--auto">Fuente oficial</span></p>
      </div>""" for a in anuncios)
    else:
        items = '<div class="tc-item"><p class="tc-pieza-cuerpo">Sin anuncios nuevos de la comarca en el último boletín.</p></div>'

    n = len(anuncios)
    con_tiempo = sum(1 for m in built if m.get("weather"))
    titular = (f"{n} anuncios de la comarca en el BOP de hoy, y el tiempo de {con_tiempo} pueblos"
               if n else f"El tiempo de {con_tiempo} pueblos de Tierra de Campos, al día")

    body = f"""<section class="tc-hoy"><div class="tc-wrap">
  <p class="tc-hoy-fecha">{fecha_larga(hoy)} — Hoy en Tierra de Campos</p>
  <h1>{E(titular)}</h1>
</div></section>

<section class="tc-wrap" id="tiempo">
  <h2 class="tc-block-title" style="color: var(--tc-azul-bop);">A ras de tierra — el tiempo, pueblo a pueblo</h2>
  <div class="tc-weather-grid">{cards}</div>
</section>

<section class="tc-wrap tc-secciones">
  <div class="tc-seccion-col" id="ayuntamiento">
    <h2 style="color: var(--tc-azul-bop);">Ayuntamiento en limpio</h2>
    {items}
  </div>
</section>

<section class="tc-newsletter"><div class="tc-wrap tc-newsletter-inner">
  <div><h2>La semana terracampina</h2><p>Un correo, una vez por semana. Lo que pasa cerca, contado claro.</p></div>
  <form class="tc-form" onsubmit="return false;"><input class="tc-input" type="email" placeholder="tu@correo.es" aria-label="Correo"><button class="tc-button" type="submit">Suscribirme</button></form>
</div></section>"""
    return shell("El Terracampino — Tierra de Campos en limpio", body, depth=0)


def render_municipio(m: dict, anuncios: list[dict], hoy: date) -> str:
    w = m.get("weather")
    meta = [f"Provincia de {E(m['province'])}"]
    if str(m.get("population", "")).isdigit():
        meta.append(f"{miles(m['population'])} habitantes")
    if m.get("lat") and m.get("lon"):
        meta.append(f"{m['lat']}, {m['lon']}")
    meta.append(f"Actualizado: {hoy.day}/{hoy.month:02d}/{hoy.year}")
    meta_html = "".join(f"<span>{s}</span>" for s in meta if s)

    if w:
        tiempo_html = f"""<div class="tc-card">
      <span class="tc-sello tc-sello--auto">Automático · Open-Meteo</span>
      <h3>A ras de tierra</h3>
      <p class="tc-weather-lead"><span class="tc-data" style="font-size:2rem;">{w['ahora']['temp']}°</span> {E(w['ahora']['desc'])}</p>
      <p class="tc-pieza-cuerpo">{E(w['articulo'])}</p>
    </div>"""
    else:
        tiempo_html = ""

    if anuncios:
        rows = "".join(f"""<div class="tc-item">
        <a class="tc-item-titulo" href="{E(a['url_original'])}" target="_blank" rel="noopener">{E(a['title'])}</a>
        <p class="tc-item-meta">BOP Valladolid · {a['published_at']} · Fuente oficial</p></div>""" for a in anuncios)
        ayto = f"""<div class="tc-card"><h3>Ayuntamiento en limpio</h3>{rows}</div>"""
    else:
        ayto = """<div class="tc-source-box"><span class="tc-section-label">Ayuntamiento en limpio</span>
      <p style="margin:6px 0 0;">Sin anuncios ni plenos nuevos verificados en los últimos días.</p></div>"""

    links = MUNI_LINKS.get(m["slug"], {})
    links_html = "".join(f'<li><a href="{E(u)}" target="_blank" rel="noopener">{E(k)}</a></li>' for k, u in links.items())
    if not links_html:
        links_html = "<li>Enlaces oficiales pendientes de verificar</li>"

    body = f"""<section class="tc-muni-hero"><div class="tc-wrap">
  <span class="tc-section-label">Ficha de municipio</span>
  <h1>{E(m['name'])}</h1>
  <div class="tc-muni-meta">{meta_html}</div>
</div></section>

<div class="tc-wrap tc-muni-grid">
  <main class="tc-muni-main">{tiempo_html}{ayto}</main>
  <aside class="tc-muni-side">
    <div class="tc-side-block"><h3>Enlaces oficiales</h3><ul class="tc-links-list">{links_html}</ul></div>
    <div class="tc-side-block"><h3>Agenda</h3><ul class="tc-links-list"><li>Sin eventos próximos verificados</li></ul></div>
  </aside>
</div>"""
    return shell(f"{m['name']} — El Terracampino", body, depth=1)


# --------------------------------------------------------------- build

def main() -> int:
    hoy = date.today()
    municipios = load_municipios()

    print("· BOP Valladolid…", flush=True)
    try:
        anuncios = parse_sumario(fetch(SUMARIO_URL))
    except ScraperError as exc:
        print(f"  aviso: BOP no disponible ({exc}); se sigue sin anuncios", file=sys.stderr)
        anuncios = []
    print(f"  {len(anuncios)} anuncios de la comarca")

    por_muni: dict[str, list[dict]] = {}
    for a in anuncios:
        por_muni.setdefault(a["municipality_slug"], []).append(a)

    slugs = list(dict.fromkeys(PILOTS + list(por_muni.keys())))

    built = []
    for slug in slugs:
        if slug not in municipios:
            continue
        m = dict(municipios[slug])
        lat, lon = m.get("lat"), m.get("lon")
        try:
            if not lat or not lon:
                geo = geocode(f"{m['name']}, {m['province']}")
                if geo:
                    lat, lon = geo
            if lat and lon:
                m["weather"] = weather_for(m["name"], float(lat), float(lon))
                print(f"· {m['name']}: {m['weather']['ahora']['temp']}° {m['weather']['ahora']['desc']}")
        except ScraperError as exc:
            print(f"  aviso: sin tiempo para {m['name']} ({exc})", file=sys.stderr)
        m["_anuncios"] = por_muni.get(slug, [])
        built.append(m)

    built.sort(key=lambda x: (-(int(x["population"]) if str(x.get("population", "")).isdigit() else 0), x["name"]))

    (WEB / "municipio").mkdir(parents=True, exist_ok=True)
    (WEB / "index.html").write_text(render_home(built, anuncios, hoy), encoding="utf-8")
    for m in built:
        (WEB / "municipio" / f"{m['slug']}.html").write_text(
            render_municipio(m, m["_anuncios"], hoy), encoding="utf-8")

    print(f"\nGenerado: web/index.html + {len(built)} fichas de municipio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
