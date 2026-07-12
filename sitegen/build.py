"""Generador del sitio estático de El Terracampino.

Modelo tipo Patch: la portada es un directorio — eliges tu pueblo y lees su página.
Cada pueblo tiene su artículo del tiempo (estilo eltiempodejavimo) y sus noticias.

Datos REALES:
  · Tiempo por municipio vía Open-Meteo (scrapers/weather_openmeteo.py), en modo artículo.
  · Anuncios del BOP de Valladolid del día (scrapers/bop_valladolid.py).

web/ es AUTOCONTENIDO (los assets de marca se copian a web/assets/), para poder
desplegar en Vercel con Root Directory = web sin rutas que escapen del directorio.

    python -m sitegen.build

`depth` = niveles por debajo de web/ (home=0, ficha de municipio=1).
"""

from __future__ import annotations

import csv
import html
import shutil
import sys
from datetime import date
from pathlib import Path

from scrapers.bocyl import buscar as bocyl_buscar, to_documents as bocyl_docs
from scrapers.bop_valladolid import SUMARIO_URL, parse_sumario
from scrapers.common import ScraperError, fetch, strip_accents
from scrapers.weather_openmeteo import geocode, weather_for
from sitegen import cache, ia
from sitegen.contenido import PUEBLOS_INFO, eventos_comarca, huerta_del_mes, proximas_fiestas
from sitegen.redactor import redactar

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
BRAND = ROOT / "brand"

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

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


def fuente_label(d: dict) -> str:
    return "BOP Valladolid" if d.get("source_type") == "bop" else "BOCyL"


def doc_row(d: dict, *, show_muni: bool) -> str:
    r = redactar(d)
    muni = f"{E(d['municipality_name'])} · " if show_muni else ""
    return f"""<a class="tc-news" href="{E(d['url_original'])}" target="_blank" rel="noopener">
      <span class="tc-news-kicker">{muni}{fuente_label(d)} · {d['published_at']}</span>
      <span class="tc-news-titular">{E(r['titular'])}</span>
      <span class="tc-news-entradilla">{E(r['entradilla'])}</span>
      <span class="tc-news-more">Leer en la fuente oficial →</span>
    </a>"""


def load_municipios() -> dict[str, dict]:
    out = {}
    with (ROOT / "data" / "municipios_tierra_de_campos.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["slug"]] = row
    return out


def copy_assets() -> None:
    """Copia los assets de marca a web/assets/ para que web/ sea autocontenido."""
    dst = WEB / "assets"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(BRAND / "web" / "brand-tokens.css", dst / "brand-tokens.css")
    shutil.copy(BRAND / "logos" / "favicon.svg", dst / "favicon.svg")
    shutil.copy(BRAND / "logos" / "el-terracampino-ilustrado.png", dst / "logo.png")


# --------------------------------------------------------------- plantilla

def shell(title: str, body: str, depth: int, *, desc: str = "") -> str:
    up = "../" * depth  # dentro de web/
    meta_desc = f'<meta name="description" content="{E(desc)}">' if desc else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(title)}</title>
{meta_desc}
<link rel="icon" href="{up}assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Serif:wght@400;700&family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}assets/brand-tokens.css">
<link rel="stylesheet" href="{up}assets/site.css">
</head>
<body class="tc-furrows">
{header(depth)}
{body}
{footer(depth)}
</body>
</html>
"""


def header(depth: int) -> str:
    up = "../" * depth
    home = up + "index.html"
    return f"""<header class="tc-header"><div class="tc-wrap tc-header-inner">
  <a href="{home}" class="tc-logo"><img src="{up}assets/logo.png" alt="El Terracampino" height="52"></a>
  <nav class="tc-nav">
    <a href="{home}">Portada</a>
    <a href="{home}#pueblos">Elige tu pueblo</a>
    <a href="{home}#comarca">La comarca</a>
  </nav>
</div></header>"""


def footer(depth: int) -> str:
    home = "../" * depth + "index.html"
    return f"""<footer class="tc-footer"><div class="tc-wrap">
  <p class="tc-aviso">Este medio resume información pública procedente de fuentes oficiales y abiertas. Los resúmenes no sustituyen al documento original. Ante cualquier trámite, plazo, ayuda o acuerdo municipal, consulta siempre la fuente oficial enlazada.</p>
  <div class="tc-footer-links"><a href="{home}">Portada</a><span>El tiempo: Open-Meteo · Boletines: BOP</span><span>elterracampino.es</span></div>
</div></footer>"""


def selector(built: list[dict], depth: int) -> str:
    up = "../" * depth
    opts = "".join(f'<option value="{up}municipio/{m["slug"]}.html">{E(m["name"])}</option>' for m in built)
    return f"""<select class="tc-muni-select" aria-label="Elige tu pueblo" onchange="if(this.value)location.href=this.value;">
    <option value="">Elige tu pueblo…</option>{opts}</select>"""


# Palabras que hacen una noticia más relevante que el trámite repetitivo.
_JUGOSO = [
    ("plan general", 5), ("presupuest", 4), ("modificacion presupuestaria", 4),
    ("licitaci", 5), ("planta", 5), ("industrial", 4), ("poligono industrial", 5),
    ("fotovoltaic", 5), ("eolic", 5), ("solar", 4), ("parque", 3), ("aceite", 4),
    ("cereal", 3), ("legumbre", 3), ("centro", 2), ("empresa", 3), ("s.l.", 3), ("s.a.", 3),
    ("pleno", 3), ("acuerdo", 2), ("subvenci", 4), ("ayuda", 3), ("expropiaci", 3),
    ("electrica", 2), ("agua", 2), ("residuo", 3), ("empleo", 4), ("contrat", 3),
]
_PENALIZA = [("declaracion de ruina", -4), ("uso excepcional de suelo rustico", -2),
             ("via pecuaria", -2), ("correccion de errores", -3)]


def es_pleno(d: dict) -> bool:
    """¿El anuncio es un pleno o acuerdo de gobierno municipal?"""
    t = strip_accents(d.get("title", "")).lower()
    org = strip_accents((d.get("metadata") or {}).get("organismo", "")).lower()
    if "pleno" in t or "junta de gobierno" in t:
        return True
    gobierno = ("presupuest", "ordenanza", "plan general", "cuenta general",
                "plan economico", "modificacion presupuestaria", "credito extraordinario",
                "suplemento de credito", "ordenacion urbana")
    return "ayuntamiento" in org and any(k in t for k in gobierno)


def relevancia(d: dict) -> int:
    t = strip_accents(d.get("title", "")).lower()
    s = 0
    for k, v in _JUGOSO:
        if k in t:
            s += v
    for k, v in _PENALIZA:
        if k in t:
            s += v
    return s


def resumen_tiempo(built: list[dict]) -> dict | None:
    ws = [(m["name"], m["weather"]) for m in built if m.get("weather")]
    if not ws:
        return None
    temps = [(name, w["ahora"]["temp"]) for name, w in ws]
    hot_name, hot_t = max(temps, key=lambda x: x[1])
    from collections import Counter
    desc = Counter(w["ahora"]["desc"] for _, w in ws).most_common(1)[0][0]
    return {
        "tmin": min(t for _, t in temps), "tmax": max(t for _, t in temps),
        "hot_name": hot_name, "hot_t": hot_t, "desc": desc, "n": len(ws),
    }


def tiempo_ia(w: dict, hoy: date) -> None:
    """Reescribe w['articulo'] con la IA (con caché) si hay clave. Si no, lo deja como está."""
    if not w or not ia.disponible():
        return
    clave = f"{ia.PROMPT_VERSION}|{w['municipio']}|{hoy.isoformat()}|{w['ahora']['temp']}|{w['hoy']['max']}|{w['hoy']['min']}|{w['ahora']['desc']}"
    guardado = cache.get("tiempo", clave)
    if guardado:
        w["articulo"] = guardado
        return
    try:
        texto = ia.tiempo(w)
        cache.set("tiempo", clave, texto)
        w["articulo"] = texto
    except Exception as exc:  # noqa: BLE001
        print(f"  aviso: IA no disponible para el tiempo de {w['municipio']} ({exc})", file=sys.stderr)


# --------------------------------------------------------------- portada

def render_home(built: list[dict], feed: list[dict], hoy: date) -> str:
    # Noticias relevantes: se prioriza lo jugoso; se descartan titulares repetidos.
    ordenadas = sorted(feed, key=lambda d: (relevancia(d), d.get("published_at") or ""), reverse=True)
    noticias, vistos = [], set()
    for d in ordenadas:
        tit = redactar(d)["titular"]
        if tit in vistos:
            continue
        vistos.add(tit)
        noticias.append(d)
        if len(noticias) >= 6:
            break
    if noticias:
        items = f'<div class="tc-news-grid">{"".join(doc_row(d, show_muni=True) for d in noticias)}</div>'
    else:
        items = '<p class="tc-pieza-cuerpo">Sin anuncios nuevos de la comarca.</p>'

    # Contenido COMÚN de la comarca (no cambia de un pueblo a otro).
    huerta = huerta_del_mes(hoy)
    nombre_por_slug = {m["slug"]: m["name"] for m in built}
    eventos = eventos_comarca(nombre_por_slug, hoy, n=6)
    agenda_html = "".join(
        f'<li><strong>{E(e["cuando"])}</strong> · {E(e["nombre"])} <span class="tc-agenda-pueblo">{E(e["pueblo"])}</span></li>'
        for e in eventos) or "<li>Sin fiestas próximas registradas.</li>"

    # Resumen del tiempo de la comarca (una línea, no 12 tarjetas).
    r = resumen_tiempo(built)
    if r:
        tiempo_html = f"""<div class="tc-weather-summary">
      <div class="tc-weather-summary-txt">
        <span class="tc-section-label" style="color:var(--tc-azul-bop);">El tiempo en la comarca</span>
        <p>Hoy en Tierra de Campos, <strong>{E(r['desc'])}</strong> y entre <strong>{r['tmin']}°</strong> y <strong>{r['tmax']}°</strong>. El pueblo más caluroso ahora es {E(r['hot_name'])}, con {r['hot_t']}°.</p>
      </div>
      <div class="tc-weather-summary-pick">{selector(built, 0)}</div>
    </div>"""
    else:
        tiempo_html = ""

    body = f"""<section class="tc-masthead"><div class="tc-wrap">
  <p class="tc-hoy-fecha">{fecha_larga(hoy)}</p>
  <h1>El tiempo y las noticias de tu pueblo, en limpio</h1>
  <p class="tc-masthead-sub">Lo que pasa en los pueblos de Tierra de Campos, contado claro y con la fuente al lado.</p>
</div></section>

<section class="tc-wrap" id="tiempo">{tiempo_html}</section>

<section class="tc-wrap" id="comarca">
  <h2 class="tc-block-title">Noticias relevantes de la comarca</h2>
  {items}
</section>

<section class="tc-wrap tc-comun">
  <div class="tc-comun-huerta">
    <h2 class="tc-block-title">Campo y huerta — {E(huerta['mes'])} en la meseta</h2>
    <p class="tc-pieza-cuerpo">{E(huerta['texto'])}</p>
    <p class="tc-item-meta">Común para toda la comarca. Orientación general, no sustituye asesoramiento técnico.</p>
  </div>
  <div class="tc-comun-agenda">
    <h2 class="tc-block-title">Agenda de la comarca</h2>
    <ul class="tc-links-list tc-agenda">{agenda_html}</ul>
  </div>
</section>

<section class="tc-channel"><div class="tc-wrap tc-channel-inner">
  <div><h2>Recibe el tiempo de tu pueblo por WhatsApp o Telegram</h2>
  <p>Un mensaje al día con la previsión de tu pueblo, y un aviso solo cuando de verdad importa: helada, ola de calor o tormenta.</p></div>
  <div class="tc-channel-btns"><span class="tc-button">WhatsApp</span><span class="tc-button tc-button--ghost">Telegram</span></div>
</div></section>

<section class="tc-newsletter"><div class="tc-wrap tc-newsletter-inner">
  <div><h2>La semana terracampina</h2><p>Un correo, una vez por semana. Lo que pasa cerca, contado claro.</p></div>
  <form class="tc-form" onsubmit="return false;"><input class="tc-input" type="email" placeholder="tu@correo.es" aria-label="Correo"><button class="tc-button" type="submit">Suscribirme</button></form>
</div></section>"""
    return shell("El Terracampino — el tiempo y las noticias de tu pueblo",
                 body, depth=0,
                 desc="El tiempo y las noticias de cada pueblo de Tierra de Campos, en limpio.")


# --------------------------------------------------------------- municipio

def weather_block(m: dict) -> str:
    w = m.get("weather")
    if not w:
        return ""
    dias = "".join(f"""<div class="tc-day">
      <span class="tc-day-name">{E(d['dia'][:3])}</span>
      <span class="tc-day-desc">{E(d['desc'])}</span>
      <span class="tc-day-temp tc-data">{d['max']}° <span class="tc-day-min">{d['min']}°</span></span>
    </div>""" for d in w["dias"])
    return f"""<div class="tc-weather-hero">
    <div class="tc-weather-now">
      <span class="tc-weather-big tc-data">{w['ahora']['temp']}°</span>
      <span class="tc-weather-desc">{E(w['ahora']['desc'])}</span>
      <span class="tc-sello tc-sello--auto">Automático · Open-Meteo</span>
    </div>
    <p class="tc-weather-article">{E(w['articulo'])}</p>
    <div class="tc-days">{dias}</div>
  </div>"""


def render_municipio(m: dict, anuncios: list[dict], hoy: date) -> str:
    meta = [f"Provincia de {E(m['province'])}"]
    if str(m.get("population", "")).isdigit():
        meta.append(f"{miles(m['population'])} habitantes")
    meta.append(f"Actualizado: {hoy.day}/{hoy.month:02d}/{hoy.year}")
    meta_html = "".join(f"<span>{s}</span>" for s in meta if s)

    noticias = anuncios + m.get("_bocyl", [])
    noticias.sort(key=lambda d: (relevancia(d), d.get("published_at") or ""), reverse=True)
    # Descartar titulares repetidos (p. ej. una resolución y su corrección de errores)
    _vistos, _dedup = set(), []
    for d in noticias:
        tit = redactar(d)["titular"]
        if tit not in _vistos:
            _vistos.add(tit)
            _dedup.append(d)
    noticias = _dedup
    plenos = [d for d in noticias if es_pleno(d)]
    otros = [d for d in noticias if not es_pleno(d)]
    ayto = ""
    if plenos:
        rows = "".join(doc_row(d, show_muni=False) for d in plenos)
        ayto += f"""<h2 class="tc-block-title">Plenos y acuerdos municipales</h2>
      <div class="tc-news-grid">{rows}</div>"""
    if otros:
        rows = "".join(doc_row(d, show_muni=False) for d in otros)
        ayto += f"""<h2 class="tc-block-title">Otros anuncios oficiales</h2>
      <div class="tc-news-grid">{rows}</div>"""
    if not noticias:
        ayto = """<div class="tc-source-box"><span class="tc-section-label">Ayuntamiento en limpio</span>
      <p style="margin:6px 0 0;">Sin anuncios ni plenos nuevos verificados en los últimos días.</p></div>"""

    links = MUNI_LINKS.get(m["slug"], {})
    links_html = "".join(f'<li><a href="{E(u)}" target="_blank" rel="noopener">{E(k)}</a></li>' for k, u in links.items())
    if not links_html:
        links_html = "<li>Enlaces oficiales pendientes de verificar</li>"

    # Agenda: fiestas verificadas del pueblo (fichas municipales / estudio)
    fiestas = proximas_fiestas(m["slug"], hoy)
    if fiestas:
        agenda_html = "".join(f'<li><strong>{E(f["cuando"])}</strong> — {E(f["nombre"])}</li>' for f in fiestas)
    else:
        agenda_html = '<li>Sin fiestas registradas todavía. ¿Falta alguna? Escríbenos.</li>'

    # Sobre el pueblo: contexto evergreen verificado + deporte local
    info = PUEBLOS_INFO.get(m["slug"])
    if info:
        deporte = (f'<p style="margin:8px 0 0; font-size:.88rem;"><strong>Deporte local:</strong> {E(info["club"])}. '
                   f'Resultados y clasificación, próximamente.</p>' if info.get("club")
                   else '<p style="margin:8px 0 0; font-size:.82rem; color:rgba(37,31,26,.6);">Sin club de referencia identificado todavía.</p>')
        sobre_html = f"""<div class="tc-side-block tc-sobre"><h3>Sobre {E(m['name'])}</h3>
      <p style="font-size:.9rem;">{E(info['sobre'])}</p>{deporte}</div>"""
    else:
        sobre_html = ""

    # Negocios y tablón: sección honesta. NO se inventan anuncios; los envían vecinos/comercios.
    tablon_html = f"""<div class="tc-card"><h3>Negocios de aquí · Tablón</h3>
      <p class="tc-pieza-cuerpo">Traspasos, alquiler de locales y de viviendas, aperturas y comercios de {E(m['name'])}. Todavía no hay anuncios publicados.</p>
      <p style="margin:10px 0 6px;"><span class="tc-button">Publicar un anuncio</span></p>
      <p class="tc-item-meta">Los anuncios los envían vecinos y comercios y se publican tras revisión. No se inventan.</p></div>"""

    w = m.get("weather")
    tiempo_titular = (f"El tiempo hoy en {E(m['name'])}: {w['ahora']['temp']}° y {E(w['ahora']['desc'])}"
                      if w else f"{E(m['name'])}")

    body = f"""<section class="tc-muni-hero"><div class="tc-wrap">
  <span class="tc-section-label">Tu pueblo</span>
  <h1>{E(m['name'])}</h1>
  <div class="tc-muni-meta">{meta_html}</div>
</div></section>

<div class="tc-wrap tc-muni-grid">
  <main class="tc-muni-main">
    <h2 class="tc-block-title">A ras de tierra — {tiempo_titular}</h2>
    {weather_block(m)}
    <div class="tc-channel tc-channel--inline"><div class="tc-channel-inner">
      <div><h3 style="margin:0 0 4px;">Recibe el tiempo de {E(m['name'])} por canal</h3>
      <p style="margin:0; font-size:.9rem;">La previsión de tu pueblo cada mañana, y aviso si hay helada o calor extremo.</p></div>
      <div class="tc-channel-btns"><span class="tc-button">WhatsApp</span><span class="tc-button tc-button--ghost">Telegram</span></div>
    </div></div>
    {ayto}
    {tablon_html}
  </main>
  <aside class="tc-muni-side">
    {sobre_html}
    <div class="tc-side-block"><h3>Enlaces oficiales</h3><ul class="tc-links-list">{links_html}</ul></div>
    <div class="tc-side-block"><h3>Agenda — fiestas y ferias</h3><ul class="tc-links-list tc-agenda">{agenda_html}</ul></div>
  </aside>
</div>"""
    desc = w["articulo"][:150] if w else f"Noticias y tiempo de {m['name']}, Tierra de Campos."
    return shell(f"{m['name']} — El Terracampino", body, depth=1, desc=desc)


# --------------------------------------------------------------- build

def main() -> int:
    hoy = date.today()
    municipios = load_municipios()
    copy_assets()

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
                tiempo_ia(m["weather"], hoy)
                print(f"· {m['name']}: {m['weather']['ahora']['temp']}° {m['weather']['ahora']['desc']}", flush=True)
        except ScraperError as exc:
            print(f"  aviso: sin tiempo para {m['name']} ({exc})", file=sys.stderr)
        # BOCyL: expedientes regionales que citan el municipio (cubre las 4 provincias)
        try:
            m["_bocyl"] = bocyl_docs(m["name"], slug, m["province"], bocyl_buscar(m["name"], m["province"], limit=5))
        except ScraperError as exc:
            print(f"  aviso: sin BOCyL para {m['name']} ({exc})", file=sys.stderr)
            m["_bocyl"] = []
        m["_anuncios"] = por_muni.get(slug, [])
        built.append(m)

    built.sort(key=lambda x: (-(int(x["population"]) if str(x.get("population", "")).isdigit() else 0), x["name"]))

    # Feed de la comarca para la portada: BOP + BOCyL de todos, lo más reciente arriba.
    feed = list(anuncios)
    for m in built:
        feed.extend(m.get("_bocyl", []))
    feed.sort(key=lambda d: d.get("published_at") or "", reverse=True)
    feed = feed[:80]  # pool amplio; render_home elige las 7 más relevantes

    (WEB / "municipio").mkdir(parents=True, exist_ok=True)
    (WEB / "index.html").write_text(render_home(built, feed, hoy), encoding="utf-8")
    for m in built:
        (WEB / "municipio" / f"{m['slug']}.html").write_text(
            render_municipio(m, m["_anuncios"], hoy), encoding="utf-8")

    cache.flush()
    modo = "IA (Claude)" if ia.disponible() else "reglas (sin ANTHROPIC_API_KEY)"
    print(f"\nGenerado: web/index.html + {len(built)} fichas de municipio. Redacción: {modo}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
