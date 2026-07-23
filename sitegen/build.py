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
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

from scrapers.bocyl import buscar as bocyl_buscar, to_documents as bocyl_docs
from scrapers.bop_valladolid import SUMARIO_URL, parse_sumario
from scrapers.common import ScraperError, fetch, strip_accents
from scrapers.futbolme import marcador_for as marcador_for_futbolme
from scrapers.siguetuliga import marcador_for as marcador_for_siguetuliga
from scrapers.municipal_wp import fetch_noticias as municipal_noticias
from scrapers.bdns import fetch_ayudas
from scrapers.plenos_sedelectronica import fetch_plenos
from scrapers.weather_openmeteo import geocode, weather_for
from sitegen import almacen_fotos, cache, ia
from sitegen.contenido import (
    PUEBLOS_INFO,
    almanaque_del_dia,
    eventos_comarca,
    huerta_del_mes,
    leyenda_de,
    proximas_fiestas,
)
from sitegen.redactor import redactar

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
BRAND = ROOT / "brand"
FOTOS_DIR = ROOT / "data" / "fotos"

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


_DIAS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MESES_EN = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rfc822(fecha_iso: str) -> str:
    """'2026-07-22' -> 'Wed, 22 Jul 2026 00:00:00 GMT' (pubDate de RSS 2.0,
    que exige inglés fijo — con strftime('%a')/('%b') saldría en español si
    el sistema tiene esa locale, así que se listan los nombres a mano)."""
    d = date.fromisoformat(fecha_iso)
    return f"{_DIAS_EN[d.weekday()]}, {d.day:02d} {_MESES_EN[d.month]} {d.year} 00:00:00 GMT"


def fecha_larga(d: date) -> str:
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def fuente_label(d: dict) -> str:
    if d.get("source_type") == "bop":
        return "BOP Valladolid"
    if d.get("source_type") == "municipal_news":
        return "Web municipal"
    if d.get("source_type") == "municipal_plenary":
        return "Acta de pleno"
    if d.get("source_type") == "subvencion":
        return "Ayudas y subvenciones"
    return "BOCyL"


def articulo_path(d: dict) -> str:
    return f"noticia/{d['hash'][:16]}.html"


def doc_row(d: dict, *, show_muni: bool, depth: int) -> str:
    r = redactar(d)
    muni = f"{E(d['municipality_name'])} · " if show_muni else ""
    # Si hay artículo propio (cuerpo redactado de verdad, no solo titular+entradilla),
    # la tarjeta lleva a NUESTRA página, no directa al PDF/HTML oficial — ver
    # render_pleno_articulo(). Si no hay cuerpo (sin IA, o la IA falló), se cae
    # al enlace externo de siempre: mejor eso que fingir un artículo que no existe.
    if r.get("cuerpo"):
        up = "../" * depth
        href, target = f"{up}{articulo_path(d)}", "_self"
        more = "Leer la noticia completa →"
    else:
        href, target = d["url_original"], "_blank"
        more = "Leer en la fuente oficial →"
    rel = ' rel="noopener"' if target == "_blank" else ""
    return f"""<a class="tc-news" href="{E(href)}" target="{target}"{rel}>
      <span class="tc-news-kicker">{muni}{fuente_label(d)} · {d['published_at']}</span>
      <span class="tc-news-titular">{E(r['titular'])}</span>
      <span class="tc-news-entradilla">{E(r['entradilla'])}</span>
      <span class="tc-news-more">{more}</span>
    </a>"""


def render_articulo(d: dict, r: dict) -> str:
    cuerpo_html = "".join(f'<p class="tc-articulo-parrafo">{E(p)}</p>' for p in r["cuerpo"])

    if d.get("source_type") == "municipal_plenary":
        kicker = f"Acta de pleno · {d['municipality_name']} · {d['published_at']}"
        fuente_txt = f"acta de la sesión plenaria del Ayuntamiento de {d['municipality_name']}."
        fuente_cta = "Ver el documento original (PDF) →"
    elif d.get("source_type") == "subvencion":
        kicker = f"Ayudas y subvenciones · {d['municipality_name']} · {d['published_at']}"
        fuente_txt = f"convocatoria oficial de {d['municipality_name']}, registrada en la Base de Datos Nacional de Subvenciones (BDNS)."
        fuente_cta = "Ver la convocatoria oficial →"
    else:
        kicker = f"{fuente_label(d)} · {d['published_at']}"
        fuente_txt = "fuente oficial."
        fuente_cta = "Ver la fuente oficial →"

    if d.get("municipality_slug"):
        volver_href = f'../municipio/{d["municipality_slug"]}.html'
        volver_txt = f"Volver a {d['municipality_name']}"
    else:
        volver_href, volver_txt = "../index.html", "Volver a portada"

    body = f"""<article class="tc-wrap tc-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-azul-bop);">{E(kicker)}</span>
  <h1>{E(r['titular'])}</h1>
  <p class="tc-articulo-entradilla">{E(r['entradilla'])}</p>
  {cuerpo_html}
  <div class="tc-source-box">
    <strong>Fuente oficial:</strong> {E(fuente_txt)}
    <a href="{E(d['url_original'])}" target="_blank" rel="noopener">{E(fuente_cta)}</a>
  </div>
  <p class="tc-item-meta"><a href="{E(volver_href)}">← {E(volver_txt)}</a></p>
</div></article>"""
    return shell(f"{r['titular']} — El Terracampino", body, depth=1, desc=r["entradilla"][:150])


def blog_articulo_path(slug: str) -> str:
    return f"blog/{slug}.html"


def render_blog_articulo(slug: str, art: dict, *, tema: str, tiene_imagen: bool) -> str:
    """Artículo largo de investigación (ver ia.py:redactar_investigacion).
    `art['secciones']` ya viene emparejado subtítulo+párrafos — no hay que
    adivinar dónde va cada uno."""
    secciones_html = "".join(
        f'<h2 class="tc-blog-subtitulo">{E(s["subtitulo"])}</h2>' +
        "".join(f'<p class="tc-articulo-parrafo">{E(p)}</p>' for p in s["parrafos"])
        for s in art["secciones"]
    )
    imagen_html = (
        f'<img class="tc-blog-imagen" src="../assets/blog/{E(slug)}.jpg" alt="{E(art["titular"])}">'
        if tiene_imagen else ""
    )
    fuentes_html = "".join(f"<li>{E(f)}</li>" for f in art.get("fuentes_usadas", []))
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-azul-bop);">Investigación · {E(tema)}</span>
  <h1>{E(art['titular'])}</h1>
  <p class="tc-articulo-entradilla">{E(art['entradilla'])}</p>
  {imagen_html}
  {secciones_html}
  <div class="tc-source-box">
    <strong>Fuentes:</strong>
    <ul class="tc-links-list">{fuentes_html}</ul>
  </div>
  <p class="tc-item-meta"><a href="../index.html">← Volver a portada</a></p>
</div></article>"""
    return shell(f"{art['titular']} — El Terracampino", body, depth=1, desc=art["entradilla"][:150])


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
    # favicon.svg quedó obsoleto: era el símbolo "T sobre surcos" descartado en
    # 2026-07-12 a favor del logo ilustrado (pastor+oveja+espiga) — se sustituye
    # aquí por el favicon PNG real del logo vigente (kit de marca v1.2).
    shutil.copy(BRAND / "logos" / "favicon-32.png", dst / "favicon-32.png")
    shutil.copy(BRAND / "logos" / "favicon-192.png", dst / "favicon-192.png")
    shutil.copy(BRAND / "logos" / "el-terracampino-ilustrado-transparente.png", dst / "logo.png")

    # Las fotos de vecinos ya no se copian aquí: las descarga del almacén
    # compartido cargar_fotos_aprobadas(), directamente a web/assets/fotos/.

    # Imágenes de artículos de blog (ver scripts/generar_articulo_blog.py):
    # se generan una vez con OpenAI y quedan en data/blog/imagenes/.
    blog_imagenes = ROOT / "data" / "blog" / "imagenes"
    if blog_imagenes.exists():
        dst_blog = dst / "blog"
        dst_blog.mkdir(parents=True, exist_ok=True)
        for f in blog_imagenes.glob("*.jpg"):
            shutil.copy(f, dst_blog / f.name)


def cargar_fotos_aprobadas() -> dict[str, list[dict]]:
    """Fotos de vecinos ya revisadas, agrupadas por municipio. Vienen del
    almacén compartido en Supabase (sitegen/almacen_fotos.py) porque el bot
    que las recibe corre en Railway, no aquí. Se descargan a
    web/assets/fotos/ para servirlas como ficheros estáticos del sitio.

    Si el almacén no está configurado o falla, se sigue sin fotos: no vale la
    pena tumbar el build entero del sitio por esto."""
    if not almacen_fotos.disponible():
        return {}
    try:
        aprobadas = almacen_fotos.listar_aprobadas()
    except almacen_fotos.AlmacenError as exc:
        print(f"  aviso: sin fotos de vecinos ({exc})", file=sys.stderr)
        return {}

    destino = WEB / "assets" / "fotos"
    destino.mkdir(parents=True, exist_ok=True)
    por_slug: dict[str, list[dict]] = {}
    for foto in aprobadas:
        archivo = f"{foto['id']}.jpg"
        ruta = destino / archivo
        if not ruta.exists():  # ya descargada en un build anterior
            ruta.write_bytes(almacen_fotos.descargar(f"aprobadas/{foto['id']}.jpg"))
        por_slug.setdefault(foto["pueblo_slug"], []).append({
            "id": foto["id"], "archivo": archivo,
            "pie": foto.get("pie", ""), "fecha": foto.get("fecha", ""),
        })
    if aprobadas:
        print(f"  {len(aprobadas)} fotos de vecinos aprobadas")
    return por_slug


def cargar_noticias_propias() -> dict[str, list[dict]]:
    """Piezas propias desarrolladas desde el radar (scripts/desarrollar_pista.py),
    agrupadas por municipio. Solo las marcadas 'publicado': un borrador nunca
    llega a la web.

    Van SOLO a la ficha de su pueblo, nunca a la portada (ver main(): no se
    añaden al `feed`) — a un vecino de Villada no le interesa mucho lo que pasa
    en Sahagún, y la portada no debe volverse un cajón de sastre."""
    manifest = ROOT / "data" / "noticias" / "propias.json"
    if not manifest.exists():
        return {}
    por_slug: dict[str, list[dict]] = {}
    for d in json.loads(manifest.read_text(encoding="utf-8")):
        if d.get("estado") == "publicado":
            por_slug.setdefault(d["municipality_slug"], []).append(d)
    return por_slug


CATEGORIAS_DIRECTORIO = {
    "sanidad": "Sanidad",
    "alimentacion": "Alimentación",
    "hosteleria": "Hostelería y alojamiento",
    "oficios": "Oficios y talleres",
    "peluqueria": "Peluquería y estética",
    "taxi": "Taxi",
    "otros": "Otros servicios",
}


def cargar_directorio_servicios() -> dict[str, list[dict]]:
    """Directorio de servicios y profesionales por pueblo (data/directorio_servicios.json).
    Investigado a mano en fuentes públicas (Páginas Amarillas, webs municipales,
    Google Business) — NO es un scraper automático: no hay fuente única fiable
    para esto, así que se actualiza por rondas de investigación puntuales, no
    en cada build. Los teléfonos/direcciones con fuentes contradictorias se
    omitieron ya en el propio JSON en vez de arriesgar un dato erróneo."""
    path = ROOT / "data" / "directorio_servicios.json"
    if not path.exists():
        return {}
    datos = json.loads(path.read_text(encoding="utf-8"))
    datos.pop("_notas", None)
    return datos


def cargar_blog_articulos() -> list[dict]:
    """Artículos de blog/investigación ya publicados (ver scripts/generar_articulo_blog.py).
    Es un índice ligero: el HTML de cada artículo ya está escrito en web/blog/,
    esto solo sirve para listarlos en portada."""
    manifest = ROOT / "data" / "blog" / "articulos.json"
    if not manifest.exists():
        return []
    return json.loads(manifest.read_text(encoding="utf-8"))


def render_feed_rss(articulos: list[dict]) -> str:
    """RSS 2.0 de las investigaciones publicadas (solo blog, no las noticias
    del día a día — son las piezas que de verdad merece la pena compartir en
    redes). Pensado para conectar con Zapier ("New Item in Feed" → Facebook
    Pages "Create Page Post"): Zapier ya tiene su propia app aprobada por
    Meta, así que autorizar la Página se hace desde el propio Zapier sin
    pasar por ninguna revisión nuestra.

    Cada item ya viene con titular+entradilla redactados y revisados por un
    humano antes de fusionarse a main (ver docs de scripts/desarrollar_pista.py
    y scripts/generar_articulo_blog.py) — este feed no añade riesgo editorial
    nuevo, solo sindica lo que ya está publicado."""
    base = "https://elterracampino.es"
    items = "".join(f"""  <item>
    <title>{E(a['titular'])}</title>
    <link>{base}/blog/{E(a['slug'])}.html</link>
    <guid isPermaLink="true">{base}/blog/{E(a['slug'])}.html</guid>
    <description>{E(a['entradilla'])}</description>
    <pubDate>{rfc822(a['fecha'])}</pubDate>
  </item>
""" for a in articulos)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>El Terracampino — Investigaciones</title>
  <link>{base}/</link>
  <description>Reportajes de investigación de Tierra de Campos, con datos oficiales y fuente citada.</description>
  <language>es-es</language>
{items}</channel>
</rss>
"""


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
<link rel="icon" href="{up}assets/favicon-32.png" type="image/png" sizes="32x32">
<link rel="icon" href="{up}assets/favicon-192.png" type="image/png" sizes="192x192">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Serif:wght@400;700&family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}assets/brand-tokens.css">
<link rel="stylesheet" href="{up}assets/site.css">
<link rel="alternate" type="application/rss+xml" title="El Terracampino — Investigaciones" href="{up}feed.xml">
</head>
<body class="tc-furrows">
{header(depth)}
{body}
{footer(depth)}
{newsletter_popup(depth)}
<script>window.va = window.va || function () {{ (window.vaq = window.vaq || []).push(arguments); }};</script>
<script defer src="/_vercel/insights/script.js"></script>
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
    <a href="{home}#blog">Investigaciones</a>
    <a href="{up}huerta.html">Huerta</a>
  </nav>
</div></header>"""


def newsletter_popup(depth: int) -> str:
    """Popup de suscripción + cableado de TODOS los formularios .tc-form de la
    página contra /api/suscribir (web/api/suscribir.js, función de Vercel que
    habla con MailerLite en servidor — la clave nunca toca el navegador).

    El popup sale una sola vez por visitante (localStorage), a los 15s, y no
    vuelve a molestar ni aunque cierre sin suscribirse."""
    up = "../" * depth
    return f"""<div class="tc-popup-overlay" id="tc-popup-overlay">
  <div class="tc-popup" role="dialog" aria-label="Suscripción a la newsletter">
    <button class="tc-popup-close" id="tc-popup-close" aria-label="Cerrar">×</button>
    <h2>La semana terracampina</h2>
    <p>Un correo, una vez por semana. Lo que pasa cerca, contado claro. Al suscribirte te mandamos también, uno a uno, los reportajes que ya hemos publicado, empezando por el primero.</p>
    <form class="tc-form"><input class="tc-input" type="email" placeholder="tu@correo.es" aria-label="Correo" required><input type="text" name="web" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px;" aria-hidden="true"><button class="tc-button" type="submit">Suscribirme</button></form>
  </div>
</div>
<script>
(function() {{
  var API = "{up}api/suscribir";
  // Todos los formularios de suscripción de la página (popup + pie) van al
  // mismo endpoint; el resultado se muestra en el propio formulario.
  document.querySelectorAll("form.tc-form").forEach(function(form) {{
    form.addEventListener("submit", function(e) {{
      e.preventDefault();
      var email = form.querySelector('input[type="email"]');
      var honey = form.querySelector('input[name="web"]');
      var btn = form.querySelector("button");
      btn.disabled = true; btn.textContent = "Un momento…";
      fetch(API, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ email: email.value, web: honey ? honey.value : "" }}),
      }}).then(function(r) {{ return r.json().then(function(d) {{ return {{ ok: r.ok, d: d }}; }}); }})
        .then(function(res) {{
          if (res.ok) {{
            form.innerHTML = "<p class=\\"tc-form-ok\\">Hecho. Revisa tu correo — bienvenido.</p>";
            localStorage.setItem("tc_newsletter_popup_visto", "1");
          }} else {{
            btn.disabled = false; btn.textContent = "Suscribirme";
            alert(res.d.error || "No se pudo completar el alta. Inténtalo más tarde.");
          }}
        }})
        .catch(function() {{
          btn.disabled = false; btn.textContent = "Suscribirme";
          alert("No se pudo completar el alta. Inténtalo más tarde.");
        }});
    }});
  }});

  var KEY = "tc_newsletter_popup_visto";
  if (localStorage.getItem(KEY)) return;
  var overlay = document.getElementById("tc-popup-overlay");
  var close = document.getElementById("tc-popup-close");
  function ocultar() {{
    overlay.classList.remove("tc-popup-overlay--visible");
    localStorage.setItem(KEY, "1");
  }}
  setTimeout(function() {{ overlay.classList.add("tc-popup-overlay--visible"); }}, 15000);
  close.addEventListener("click", ocultar);
  overlay.addEventListener("click", function(e) {{ if (e.target === overlay) ocultar(); }});
}})();
</script>"""


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

    # Artículo por día (estilo Javimo) para los días futuros; el de hoy ya está en w['articulo'].
    dias_futuros = w["dias"][1:]
    if not dias_futuros:
        return
    clave_dias = f"{ia.PROMPT_VERSION_DIAS}|{w['municipio']}|" + "|".join(
        f"{d['fecha']}:{d['max']}:{d['min']}:{d['desc']}:{d['prob_lluvia']}" for d in dias_futuros
    )
    guardado_dias = cache.get("tiempo_dias", clave_dias)
    if guardado_dias:
        for d, g in zip(dias_futuros, guardado_dias):
            d["titular"], d["texto"] = g["titular"], g["texto"]
        return
    try:
        resultado = ia.tiempo_dias(w["municipio"], dias_futuros)
        cache.set("tiempo_dias", clave_dias, resultado)
        for d, r in zip(dias_futuros, resultado):
            d["titular"], d["texto"] = r["titular"], r["texto"]
    except Exception as exc:  # noqa: BLE001
        print(f"  aviso: IA no disponible para los días de {w['municipio']} ({exc})", file=sys.stderr)


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
        items = f'<div class="tc-news-grid">{"".join(doc_row(d, show_muni=True, depth=0) for d in noticias)}</div>'
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

    # Blog / investigaciones: piezas largas, generadas aparte (scripts/generar_articulo_blog.py),
    # no en cada build. Se listan aquí si hay alguna publicada.
    blog_articulos = cargar_blog_articulos()
    if blog_articulos:
        tarjetas_blog = "".join(f'''<a class="tc-blog-tarjeta" href="blog/{E(a["slug"])}.html">
      {f'<img src="assets/blog/{E(a["slug"])}.jpg" alt="" loading="lazy">' if a.get("tiene_imagen") else ""}
      <span class="tc-news-titular">{E(a["titular"])}</span>
      <span class="tc-news-entradilla">{E(a["entradilla"])}</span>
    </a>''' for a in blog_articulos[:3])
        blog_html = f"""<section class="tc-wrap" id="blog">
  <h2 class="tc-block-title">Investigaciones</h2>
  <div class="tc-blog-grid">{tarjetas_blog}</div>
</section>"""
    else:
        blog_html = ""

    alm = almanaque_del_dia(hoy)
    body = f"""<section class="tc-masthead"><div class="tc-wrap">
  <p class="tc-hoy-fecha">{fecha_larga(hoy)}</p>
  <h1>El tiempo y las noticias de tu pueblo, en limpio</h1>
  <p class="tc-masthead-sub">Lo que pasa en los pueblos de Tierra de Campos, contado claro y con la fuente al lado.</p>
  <p class="tc-almanaque">«{E(alm['refran'])}» <span class="tc-almanaque-sep">·</span> Hoy es {E(alm['santo'])} <span class="tc-almanaque-sep">·</span> {alm['luna']['emoji']} {E(alm['luna']['fase'])}</p>
</div></section>

<section class="tc-wrap" id="tiempo">{tiempo_html}</section>

<section class="tc-wrap" id="comarca">
  <h2 class="tc-block-title">Noticias relevantes de la comarca</h2>
  {items}
</section>

{blog_html}

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
  <div><h2>Entérate de lo de tu pueblo por Telegram</h2>
  <p>El tiempo, las noticias, la agenda de fiestas, alguna historia de aquí y una foto de vez en cuando. Sin ruido de fuera.</p></div>
  <div class="tc-channel-btns"><a class="tc-button" href="https://t.me/elterracampino" target="_blank" rel="noopener">Telegram</a> <a class="tc-button tc-button--ghost" href="https://wa.me/34695645395" target="_blank" rel="noopener">WhatsApp</a></div>
</div></section>

<section class="tc-newsletter"><div class="tc-wrap tc-newsletter-inner">
  <div><h2>La semana terracampina</h2><p>Un correo, una vez por semana. Lo que pasa cerca, contado claro.</p></div>
  <form class="tc-form"><input class="tc-input" type="email" placeholder="tu@correo.es" aria-label="Correo" required><input type="text" name="web" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px;" aria-hidden="true"><button class="tc-button" type="submit">Suscribirme</button></form>
</div></section>"""
    return shell("El Terracampino — el tiempo y las noticias de tu pueblo",
                 body, depth=0,
                 desc="El tiempo y las noticias de cada pueblo de Tierra de Campos, en limpio.")


# --------------------------------------------------------------- municipio

def weather_block(m: dict) -> str:
    w = m.get("weather")
    if not w:
        return ""
    dias = "".join(f"""<article class="tc-day">
      <span class="tc-day-name">{E(d['dia'].capitalize())}</span>
      <h4 class="tc-day-titular">{E(d['titular'])}</h4>
      <p class="tc-day-texto">{E(d['texto'])}</p>
      <span class="tc-day-temp tc-data">{d['max']}° <span class="tc-day-min">{d['min']}°</span></span>
    </article>""" for d in w["dias"][1:])
    return f"""<div class="tc-weather-hero">
    <div class="tc-weather-now">
      <span class="tc-weather-big tc-data">{w['ahora']['temp']}°</span>
      <span class="tc-weather-desc">{E(w['ahora']['desc'])}</span>
      <span class="tc-sello tc-sello--auto">Automático · Open-Meteo</span>
    </div>
    <p class="tc-weather-article">{E(w['articulo'])}</p>
    <span class="tc-section-label" style="color:var(--tc-azul-bop);">Los próximos días</span>
    <div class="tc-days">{dias}</div>
  </div>"""


def render_municipio(m: dict, anuncios: list[dict], hoy: date) -> str:
    meta = [f"Provincia de {E(m['province'])}"]
    if str(m.get("population", "")).isdigit():
        meta.append(f"{miles(m['population'])} habitantes")
    meta.append(f"Actualizado: {hoy.day}/{hoy.month:02d}/{hoy.year}")
    meta_html = "".join(f"<span>{s}</span>" for s in meta if s)

    noticias = anuncios + m.get("_bocyl", []) + m.get("_municipal", []) + m.get("_plenos", [])
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
        rows = "".join(doc_row(d, show_muni=False, depth=1) for d in plenos)
        ayto += f"""<h2 class="tc-block-title">Plenos y acuerdos municipales</h2>
      <div class="tc-news-grid">{rows}</div>"""
    if otros:
        rows = "".join(doc_row(d, show_muni=False, depth=1) for d in otros)
        ayto += f"""<h2 class="tc-block-title">Otros anuncios oficiales</h2>
      <div class="tc-news-grid">{rows}</div>"""
    if not noticias:
        ayto = """<div class="tc-source-box"><span class="tc-section-label">Ayuntamiento en limpio</span>
      <p style="margin:6px 0 0;">Sin anuncios ni plenos nuevos verificados en los últimos días.</p></div>"""

    # Piezas propias desarrolladas desde el radar (scripts/desarrollar_pista.py):
    # bloque aparte porque no son anuncios oficiales, son noticias del pueblo
    # contadas por nosotros. Solo aquí: no van a la portada.
    propias = m.get("_propias", [])
    propias_html = ""
    if propias:
        propias.sort(key=lambda d: d.get("published_at") or "", reverse=True)
        rows = "".join(doc_row(d, show_muni=False, depth=1) for d in propias)
        propias_html = f"""<h2 class="tc-block-title">Lo que pasa en {E(m['name'])}</h2>
      <div class="tc-news-grid">{rows}</div>"""

    # Ayudas y subvenciones reales (BDNS): propias del ayuntamiento, ver scrapers/bdns.py
    ayudas = m.get("_ayudas", [])
    ayudas_html = ""
    if ayudas:
        rows = "".join(doc_row(d, show_muni=False, depth=1) for d in ayudas)
        ayudas_html = f"""<h2 class="tc-block-title">Ayudas y subvenciones</h2>
      <div class="tc-news-grid">{rows}</div>"""

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
        marcador = m.get("_marcador")
        if marcador:
            partes = [f'<strong>Deporte local:</strong> {E(marcador["club"])} ({E(marcador["competicion"])}).']
            if marcador["ultimo"]:
                partes.append(E(marcador["ultimo"]["texto"]))
            if marcador["proximo"]:
                partes.append(E(marcador["proximo"]["texto"]))
            if not marcador["ultimo"] and not marcador["proximo"]:
                partes.append("Sin partidos publicados por ahora (temporada sin empezar).")
            deporte = f'<p style="margin:8px 0 0; font-size:.88rem;">{" ".join(partes)}</p>'
        elif info.get("club"):
            deporte = (f'<p style="margin:8px 0 0; font-size:.88rem;"><strong>Deporte local:</strong> {E(info["club"])}. '
                       f'Resultados y clasificación, próximamente.</p>')
        else:
            deporte = '<p style="margin:8px 0 0; font-size:.82rem; color:rgba(37,31,26,.6);">Sin club de referencia identificado todavía.</p>'
        sobre_html = f"""<div class="tc-side-block tc-sobre"><h3>Sobre {E(m['name'])}</h3>
      <p style="font-size:.9rem;">{E(info['sobre'])}</p>{deporte}</div>"""
    else:
        sobre_html = ""

    # Leyendas e historias populares: solo si está documentada (ver contenido.py LEYENDAS)
    leyenda = leyenda_de(m["slug"])
    if leyenda:
        leyenda_html = f"""<div class="tc-side-block tc-leyenda"><h3>Leyendas e historias populares</h3>
      <p class="tc-leyenda-titulo">{E(leyenda['titulo'])}</p>
      <p style="font-size:.9rem;">{E(leyenda['texto'])}</p>
      <p class="tc-item-meta">Fuente: {E(leyenda['fuente'])}</p></div>"""
    else:
        leyenda_html = ""

    # Directorio de servicios: investigado a mano (data/directorio_servicios.json),
    # agrupado por categoría. Solo aparece si hay datos para este pueblo — nunca
    # una sección vacía con "todavía no hay nada" (a diferencia del tablón, que sí
    # se explica como vacío porque son anuncios que envía la gente).
    directorio = m.get("_directorio", [])
    if directorio:
        por_categoria: dict[str, list[dict]] = {}
        for neg in directorio:
            por_categoria.setdefault(neg.get("categoria", "otros"), []).append(neg)
        bloques = []
        for cat_slug, etiqueta in CATEGORIAS_DIRECTORIO.items():
            negocios = por_categoria.get(cat_slug)
            if not negocios:
                continue
            items = "".join(
                f'<li><strong>{E(neg["nombre"])}</strong>'
                + (f' — <a href="tel:+34{re.sub(r"[^0-9]", "", neg["telefono"])}">{E(neg["telefono"])}</a>'
                   if neg.get("telefono") else "")
                + (f' · {E(neg["direccion"])}' if neg.get("direccion") else "")
                + "</li>"
                for neg in negocios
            )
            bloques.append(f'<h4 style="margin:14px 0 4px;">{E(etiqueta)}</h4><ul class="tc-links-list">{items}</ul>')
        directorio_html = f"""<div class="tc-card"><h3>Servicios y profesionales de {E(m['name'])}</h3>
      {''.join(bloques)}
      <p class="tc-item-meta" style="margin-top:10px;">Datos investigados en fuentes públicas (Páginas Amarillas, web del
      ayuntamiento, Google Business) en julio de 2026 — pueden quedar desactualizados. ¿Ves un error, un negocio cerrado
      o falta el tuyo? <a href="https://wa.me/34695645395" target="_blank" rel="noopener">Dínoslo por WhatsApp</a>.</p></div>"""
    else:
        directorio_html = ""

    # Negocios y tablón: sección honesta. NO se inventan anuncios; los envían vecinos/comercios.
    tablon_html = f"""<div class="tc-card"><h3>Negocios de aquí · Tablón</h3>
      <p class="tc-pieza-cuerpo">Traspasos, alquiler de locales y de viviendas, aperturas y comercios de {E(m['name'])}. Todavía no hay anuncios publicados.</p>
      <p style="margin:10px 0 6px;"><span class="tc-button">Publicar un anuncio</span></p>
      <p class="tc-item-meta">Los anuncios los envían vecinos y comercios y se publican tras revisión. No se inventan.</p></div>"""

    # Fotos de vecinos, estilo "Destino Tierra de Campos" pero con marco de marca
    # propio: llegan por Telegram, pasan por revisión, se procesan (sitegen/fotos.py)
    # y solo entonces aparecen aquí. Nunca automático.
    fotos = m.get("_fotos", [])
    if fotos:
        tarjetas = "".join(f'''<figure class="tc-foto">
      <img src="../assets/fotos/{E(f['archivo'])}" alt="{E(f['pie'])}" loading="lazy">
      <figcaption>{E(f['pie'])}</figcaption>
    </figure>''' for f in fotos)
        galeria_html = f"""<h2 class="tc-block-title">Fotos de {E(m['name'])}</h2>
    <div class="tc-foto-grid">{tarjetas}</div>"""
    else:
        galeria_html = f"""<div class="tc-card"><h3>Fotos de {E(m['name'])}</h3>
      <p class="tc-pieza-cuerpo">Todavía no hay fotos publicadas de {E(m['name'])}.</p>
      <p style="margin:10px 0 6px;"><span class="tc-button">Manda la primera foto</span></p>
      <p class="tc-item-meta">Las fotos las mandan los vecinos por Telegram y se publican tras revisión.</p></div>"""

    w = m.get("weather")
    tiempo_titular = (f"El tiempo hoy en {E(m['name'])}: {w['ahora']['temp']}° y {E(w['ahora']['desc'])}"
                      if w else f"{E(m['name'])}")

    # Foto de cabecera con licencia libre (scripts/buscar_fotos_libres.py):
    # solo relleno mientras no hay fotos de vecinos propias más abajo. La
    # atribución de autor y licencia es obligatoria (CC-BY/CC-BY-SA), nunca
    # se omite.
    foto_libre = m.get("_foto_libre")
    foto_libre_html = ""
    if foto_libre:
        credito_url = foto_libre.get("licencia_url") or foto_libre["pagina_commons"]
        foto_libre_html = f"""<div class="tc-muni-hero-foto">
    <img src="../assets/fotos-libres/{E(foto_libre['archivo'])}" alt="{E(m['name'])}" loading="lazy">
    <p class="tc-muni-hero-credito">Foto: <a href="{E(foto_libre['pagina_commons'])}" target="_blank" rel="noopener">{E(foto_libre['autor'])}</a>,
      <a href="{E(credito_url)}" target="_blank" rel="noopener">{E(foto_libre['licencia'])}</a>, vía Wikimedia Commons</p>
  </div>"""

    body = f"""<section class="tc-muni-hero"><div class="tc-wrap">
  <span class="tc-section-label">Tu pueblo</span>
  <h1>{E(m['name'])}</h1>
  <div class="tc-muni-meta">{meta_html}</div>
  {foto_libre_html}
</div></section>

<div class="tc-wrap tc-muni-grid">
  <main class="tc-muni-main">
    <h2 class="tc-block-title">A ras de tierra — {tiempo_titular}</h2>
    {weather_block(m)}
    <div class="tc-channel tc-channel--inline"><div class="tc-channel-inner">
      <div><h3 style="margin:0 0 4px;">Recibe lo de {E(m['name'])} por Telegram</h3>
      <p style="margin:0; font-size:.9rem;">El tiempo cada mañana, las noticias del pueblo, la agenda, alguna historia de aquí y una foto de vez en cuando.</p></div>
      <div class="tc-channel-btns"><a class="tc-button" href="https://t.me/elterracampino" target="_blank" rel="noopener">Telegram</a> <a class="tc-button tc-button--ghost" href="https://wa.me/34695645395" target="_blank" rel="noopener">WhatsApp</a></div>
    </div></div>
    {propias_html}
    {ayto}
    {ayudas_html}
    {galeria_html}
    {directorio_html}
    {tablon_html}
  </main>
  <aside class="tc-muni-side">
    {sobre_html}
    {leyenda_html}
    <div class="tc-side-block"><h3>Enlaces oficiales</h3><ul class="tc-links-list">{links_html}</ul></div>
    <div class="tc-side-block"><h3>Agenda — fiestas y ferias</h3><ul class="tc-links-list tc-agenda">{agenda_html}</ul></div>
  </aside>
</div>"""
    desc = w["articulo"][:150] if w else f"Noticias y tiempo de {m['name']}, Tierra de Campos."
    return shell(f"{m['name']} — El Terracampino", body, depth=1, desc=desc)


def render_sitemap(paginas: list[tuple[str, str]]) -> str:
    """sitemap.xml estándar: (ruta relativa a web/, fecha ISO de última
    modificación) para cada página real del sitio — portada, fichas de
    municipio, noticias propias e investigaciones. Los anuncios oficiales
    (plenos/BOCyL/BDNS) no tienen página propia, viven dentro de la ficha de
    su municipio, así que no generan entrada aparte."""
    base = "https://elterracampino.es"
    urls = "".join(f"""  <url>
    <loc>{base}/{E(ruta)}</loc>
    <lastmod>{E(lastmod)}</lastmod>
  </url>
""" for ruta, lastmod in paginas)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}</urlset>
"""


def render_robots_txt() -> str:
    return "User-agent: *\nAllow: /\n\nSitemap: https://elterracampino.es/sitemap.xml\n"


GUIA_HUERTA_MESES = [
    ("Enero", "enero", (
        "Es el mes de tocar poco la tierra y planear mucho. La meseta está helada casi a diario y "
        "sacar plantas fuera ahora es tirarlas. Lo que sí se puede: preparar semillero protegido "
        "(alféizar, invernadero casero, un plástico bien puesto) para guisante y haba, revisar y "
        "afilar herramientas, y si hay frutales, aprovechar que están en reposo para podarlos."
    )),
    ("Febrero", "febrero", (
        "Arranca el semillero de tomate, pimiento y berenjena, siempre protegido — aquí no salen al "
        "aire libre hasta bien entrado mayo, así que cuanto antes empiecen dentro, más planta tendrán "
        "cuando llegue su momento. Al aire libre, si el suelo no está encharcado ni helado, ya se "
        "puede sembrar guisante, haba y espinaca, y plantar ajo si no se hizo en otoño."
    )),
    ("Marzo", "marzo", (
        "El suelo empieza a trabajarse mejor, pero las heladas tardías de la meseta no se van todavía "
        "— alguna nevada de marzo no es rara. Se puede sembrar directo zanahoria, remolacha, rábano, "
        "lechuga y acelga en los días buenos. El semillero de tomate y pimiento sigue dentro; aporcar "
        "las habas que ya estén altas."
    )),
    ("Abril", "abril", (
        "Mes de trasplantar lechuga, acelga y cebolla al terreno definitivo, y de sembrar calabacín y "
        "calabaza en semillero. Ojo con las heladas tardías: en años fríos llegan hasta entrado mayo "
        "en esta comarca, así que conviene tener algo con lo que tapar los semilleros por la noche si "
        "se anuncia frío."
    )),
    ("Mayo", "mayo", (
        "El mes clave: cuando ya no hay riesgo real de helada (el dicho de aquí es claro — hasta San "
        "Isidro, 15 de mayo, no te quites el sayo, y en años fríos ni eso), se trasplanta fuera todo "
        "lo que estaba protegido: tomate, pimiento, berenjena, calabacín. Se siembra directo judía "
        "verde, maíz y pepino, y se aporca la patata."
    )),
    ("Junio", "junio", (
        "Con el calor ya instalado, el riego pasa a ser la tarea central — mejor temprano por la "
        "mañana o al atardecer, nunca a pleno sol de mediodía. Se entutoran los tomates para que no se "
        "vengan abajo con el peso, se acolcha el suelo (paja, hierba seca) para que no se seque tan "
        "rápido, y se puede sembrar otra tanda de judía verde escalonada."
    )),
    ("Julio", "julio", (
        "Empieza la recolección fuerte: ajo (se arranca y se pone a secar a la sombra), cebolla "
        "temprana, calabacín, judía verde y los primeros tomates. Es el mes más exigente de riego del "
        "verano castellano — vigilar que el agua llegue de verdad a la raíz, no solo a la superficie. "
        "Buen momento para sembrar en semillero, a resguardo del sol, la lechuga y acelga de otoño."
    )),
    ("Agosto", "agosto", (
        "Recolección plena de tomate, pimiento, pepino, calabacín y judía. Es el mes más seco del año "
        "en la comarca, así que el riego no da tregua. Se empieza a preparar el otoño: trasplantar "
        "puerro y col, y seguir con la lechuga de otoño en semillero a la sombra hasta que baje un "
        "poco el calor."
    )),
    ("Septiembre", "septiembre", (
        "El calor afloja y es un buen momento para trasplantar al terreno lo que se sembró en agosto "
        "(puerro, coles, lechuga de otoño). Se recolecta lo último del verano — tomate, pimiento, "
        "calabaza — antes de que las noches empiecen a refrescar de verdad."
    )),
    ("Octubre", "octubre", (
        "Con las primeras heladas ya posibles en la comarca, toca recoger lo que quede de verano "
        "(calabaza, últimos pimientos) y dejar el terreno preparado para el invierno: limpiar restos "
        "de cosecha y abonar con compost o estiércol bien hecho. Es la época clásica para plantar ajo "
        "de cara a la cosecha del verano que viene."
    )),
    ("Noviembre", "noviembre", (
        "La huerta entra en calma. Poco que sembrar al aire libre con el frío ya asentado — mejor "
        "dejar el terreno descansar con una cubierta (paja, restos vegetales) que lo proteja de la "
        "erosión y el frío directo. Momento de revisar y guardar bien las herramientas."
    )),
    ("Diciembre", "diciembre", (
        "Mes de descanso para la tierra. Si hay frutales, se podan ahora que están parados. Es también "
        "buen momento para planificar el año que viene: qué fue bien, qué no, y dejar listo el rincón "
        "donde en enero arrancará el semillero de guisante y haba."
    )),
]


def render_huerta() -> str:
    """Guía evergreen de huerta amateur, mes a mes, adaptada al clima de la
    meseta de Tierra de Campos (heladas tardías hasta mayo, veranos secos y
    calurosos, suelo arcilloso). Ver docs/secciones-editoriales.md §3.2:
    contenido diferencial, pensado para quien mantiene un huerto familiar,
    NUNCA para agricultura profesional (esa es otra pieza, "Campo y huerta"
    profesional, con sus propias fuentes AEMET/InfoRiego).

    Deliberadamente sin consejos fitosanitarios cerrados ni promesas de
    cosecha — cada suelo, orientación y microclima del pueblo es distinto;
    esto es orientación general, no una receta."""
    secciones_html = "".join(f"""<h2 class="tc-blog-subtitulo" id="{E(anchor)}">{E(nombre)}</h2>
  <p class="tc-articulo-parrafo">{E(texto)}</p>
""" for nombre, anchor, texto in GUIA_HUERTA_MESES)
    indice_html = "".join(
        f'<a href="#{E(anchor)}" class="tc-button tc-button--ghost" style="margin:0 6px 6px 0;">{E(nombre)}</a>'
        for nombre, anchor, _ in GUIA_HUERTA_MESES
    )
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-verde-regadio);">Campo y huerta</span>
  <h1>Guía de huerta, mes a mes, para Tierra de Campos</h1>
  <p class="tc-articulo-entradilla">Qué sembrar, trasplantar y recolectar cada mes en un huerto
  familiar de la meseta — pensada para quien tiene un huerto de recreo o de toda la vida, no para
  agricultura profesional. Es orientación general: cada parcela, orientación y suelo es un mundo, así
  que tómalo como punto de partida, no como receta cerrada.</p>
  <p style="margin:14px 0 22px;">{indice_html}</p>
  {secciones_html}
  <p class="tc-item-meta" style="margin-top:18px;">¿Aviso de helada o de ola de calor esta semana? Mira
  el tiempo de tu pueblo — la lectura práctica para el huerto (cubrir semilleros, regar antes de que
  apriete el calor) va con el parte de cada ficha de municipio.</p>
  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>"""
    return shell("Guía de huerta — El Terracampino", body, depth=0,
                 desc="Calendario mensual de siembra y cosecha para un huerto familiar en Tierra de Campos.")


def render_404() -> str:
    """Página de error 404. NO puede usar shell() (que resuelve assets con
    rutas relativas tipo '../assets/...' según la profundidad de la página):
    Vercel sirve este mismo fichero para cualquier ruta rota, a cualquier
    profundidad, así que el navegador resuelve las rutas relativas contra la
    URL que el visitante pidió, no contra donde vive 404.html realmente.
    Hacen falta rutas absolutas ('/assets/...')."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Página no encontrada — El Terracampino</title>
<link rel="icon" href="/assets/favicon-32.png" type="image/png" sizes="32x32">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=PT+Serif:wght@400;700&family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/brand-tokens.css">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>
<section class="tc-muni-hero"><div class="tc-wrap">
  <span class="tc-section-label">Vaya</span>
  <h1>Esta página no existe</h1>
  <p style="margin:8px 0 0;">El enlace puede estar mal escrito, o la página ya no está aquí.</p>
  <p style="margin-top:18px;">
    <a class="tc-button" href="/">Portada</a>
    <a class="tc-button tc-button--ghost" href="/index.html#pueblos">Elige tu pueblo</a>
  </p>
</div></section>
</body>
</html>
"""


# --------------------------------------------------------------- build

def main() -> int:
    hoy = date.today()
    municipios = load_municipios()
    copy_assets()
    fotos_por_slug = cargar_fotos_aprobadas()
    propias_por_slug = cargar_noticias_propias()
    directorio_por_slug = cargar_directorio_servicios()

    # Foto de cabecera con licencia libre (scripts/buscar_fotos_libres.py):
    # solo relleno honesto mientras no hay fotos de vecinos, con su autor y
    # licencia siempre visibles (obligatorio en CC-BY/CC-BY-SA). Nunca se
    # mezcla con la galería de vecinos, que sigue siendo la sección principal.
    fotos_libres_path = ROOT / "data" / "fotos_libres.json"
    fotos_libres = (json.loads(fotos_libres_path.read_text(encoding="utf-8"))
                     if fotos_libres_path.exists() else {})

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

    # Un pueblo tiene ficha si es piloto, si el BOP trae algo suyo, o si hemos
    # publicado una pieza propia sobre él (radar → scripts/desarrollar_pista.py).
    # Así la cobertura crece donde hay contenido, sin páginas vacías: el tiempo
    # se resuelve solo (geocode más abajo) y el BOCyL funciona para cualquiera.
    slugs = list(dict.fromkeys(PILOTS + list(por_muni.keys()) + list(propias_por_slug.keys())))

    print("· Ayudas y subvenciones (BDNS)…", flush=True)
    try:
        pilotos_nombre_slug = [(municipios[s]["name"], s) for s in PILOTS if s in municipios]
        ayudas_por_slug = fetch_ayudas(pilotos_nombre_slug)
    except ScraperError as exc:
        print(f"  aviso: BDNS no disponible ({exc}); se sigue sin ayudas", file=sys.stderr)
        ayudas_por_slug = {}
    print(f"  {sum(len(v) for v in ayudas_por_slug.values())} ayudas relevantes")

    built = []
    for slug in slugs:
        if slug not in municipios:
            continue
        m = dict(municipios[slug])
        lat, lon = m.get("lat"), m.get("lon")
        try:
            if not lat or not lon:
                geo = geocode(m["name"], m["province"])
                if geo:
                    lat, lon = geo
                else:
                    print(f"  aviso: sin coordenadas para {m['name']} ({m['province']}): "
                          f"su ficha sale sin el tiempo", file=sys.stderr)
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
        # Noticias municipales propias (solo pueblos con web en WordPress cubierta, ver scrapers/municipal_wp.py)
        try:
            m["_municipal"] = municipal_noticias(slug)
        except ScraperError as exc:
            print(f"  aviso: sin noticias municipales para {m['name']} ({exc})", file=sys.stderr)
            m["_municipal"] = []
        # Actas de pleno reales (solo municipios autorizados explícitamente, ver scrapers/plenos_sedelectronica.py)
        try:
            m["_plenos"] = fetch_plenos(slug)
        except ScraperError as exc:
            print(f"  aviso: sin actas de pleno para {m['name']} ({exc})", file=sys.stderr)
            m["_plenos"] = []
        m["_ayudas"] = ayudas_por_slug.get(slug, [])
        m["_propias"] = propias_por_slug.get(slug, [])
        m["_directorio"] = directorio_por_slug.get(slug, [])
        m["_fotos"] = fotos_por_slug.get(slug, [])
        m["_foto_libre"] = fotos_libres.get(slug)
        m["_anuncios"] = por_muni.get(slug, [])
        # Marcador: último resultado y próximo partido del club local (si hay uno
        # cubierto). Futbolme cubre categorías nacionales/regionales; para las
        # ligas provinciales de aficionados se cae a siguetuliga.com — ver
        # scrapers/siguetuliga.py sobre por qué la RFCYLF oficial queda descartada.
        try:
            m["_marcador"] = marcador_for_futbolme(slug, hoy)
        except ScraperError as exc:
            print(f"  aviso: sin marcador (Futbolme) para {m['name']} ({exc})", file=sys.stderr)
            m["_marcador"] = None
        if not m["_marcador"]:
            try:
                m["_marcador"] = marcador_for_siguetuliga(slug, hoy)
            except ScraperError as exc:
                print(f"  aviso: sin marcador (siguetuliga) para {m['name']} ({exc})", file=sys.stderr)
        built.append(m)

    built.sort(key=lambda x: (-(int(x["population"]) if str(x.get("population", "")).isdigit() else 0), x["name"]))

    ayudas_comarca = ayudas_por_slug.get("comarca", [])

    # Feed de la comarca para la portada: BOP + BOCyL de todos, lo más reciente arriba.
    feed = list(anuncios) + list(ayudas_comarca)
    for m in built:
        feed.extend(m.get("_bocyl", []))
        feed.extend(m.get("_municipal", []))
        feed.extend(m.get("_plenos", []))
        feed.extend(m.get("_ayudas", []))
    feed.sort(key=lambda d: d.get("published_at") or "", reverse=True)
    feed = feed[:80]  # pool amplio; render_home elige las 7 más relevantes

    (WEB / "municipio").mkdir(parents=True, exist_ok=True)
    (WEB / "noticia").mkdir(parents=True, exist_ok=True)
    (WEB / "index.html").write_text(render_home(built, feed, hoy), encoding="utf-8")
    blog_articulos = cargar_blog_articulos()
    (WEB / "feed.xml").write_text(render_feed_rss(blog_articulos), encoding="utf-8")

    # Páginas para sitemap.xml: se van acumulando según se escribe cada
    # fichero, así el sitemap nunca puede desincronizarse de lo que hay
    # realmente en disco (nada de reconstruir la lista aparte a mano).
    (WEB / "huerta.html").write_text(render_huerta(), encoding="utf-8")
    paginas_sitemap: list[tuple[str, str]] = [("", hoy.isoformat()), ("huerta.html", hoy.isoformat())]
    paginas_sitemap += [(f"blog/{a['slug']}.html", a.get("fecha", hoy.isoformat())) for a in blog_articulos]

    for m in built:
        (WEB / "municipio" / f"{m['slug']}.html").write_text(
            render_municipio(m, m["_anuncios"], hoy), encoding="utf-8")
        paginas_sitemap.append((f"municipio/{m['slug']}.html", hoy.isoformat()))

    # Artículo propio para cada pleno/ayuda con cuerpo redactado (ver doc_row:
    # solo se enlaza aquí si de verdad hay un artículo, si no se cae a la fuente oficial).
    n_articulos = 0
    todos_los_docs = ayudas_comarca + [
        d for m in built
        for d in (m.get("_plenos", []) + m.get("_ayudas", []) + m.get("_propias", []))
    ]
    print(f"· Redactando {len(todos_los_docs)} artículos (plenos + ayudas + propias)…", flush=True)
    for i, d in enumerate(todos_los_docs, 1):
        print(f"  [{i}/{len(todos_los_docs)}] {d.get('title', '')[:60]}", flush=True)
        r = redactar(d)
        if r.get("cuerpo"):
            (WEB / "noticia" / f"{d['hash'][:16]}.html").write_text(
                render_articulo(d, r), encoding="utf-8")
            paginas_sitemap.append((f"noticia/{d['hash'][:16]}.html", d.get("published_at") or hoy.isoformat()))
            n_articulos += 1

    (WEB / "sitemap.xml").write_text(render_sitemap(paginas_sitemap), encoding="utf-8")
    (WEB / "robots.txt").write_text(render_robots_txt(), encoding="utf-8")
    (WEB / "404.html").write_text(render_404(), encoding="utf-8")

    cache.flush()
    modo = "IA (Claude)" if ia.disponible() else "reglas (sin ANTHROPIC_API_KEY)"
    print(f"\nGenerado: web/index.html + {len(built)} fichas de municipio + "
          f"{n_articulos} artículos (plenos + ayudas) + sitemap.xml ({len(paginas_sitemap)} páginas). "
          f"Redacción: {modo}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
