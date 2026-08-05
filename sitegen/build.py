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
from datetime import date, datetime
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
from scrapers.lonja import cotizaciones as lonja_cotizaciones
from scrapers.aemet_avisos import avisos as aemet_avisos
from scrapers.embalses import situacion as situacion_embalses
from scrapers.paro_sepe import paro_comarca_cacheado
from sitegen import almacen_fotos, cache, ia
from sitegen.contenido import (
    LEYENDAS,
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


def dec(n, decimales: int = 1) -> str:
    """Número con coma decimal, como se escribe en español ('3,2' y no '3.2')."""
    return f"{n:.{decimales}f}".replace(".", ",")


def url_segura(url: str) -> str:
    """Sube a https los enlaces de fuentes oficiales que lo admiten. El BOCyL los
    publica en http y el navegador puede avisar de "sitio no seguro" justo cuando
    el lector va a comprobar la fuente — que es de lo que presume el periódico.
    Verificado que las URLs de documento del BOCyL responden 200 por https."""
    if url.startswith("http://bocyl.jcyl.es"):
        return "https://" + url[len("http://"):]
    return url


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
        href, target = url_segura(d["url_original"]), "_blank"
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
    <a href="{E(url_segura(d['url_original']))}" target="_blank" rel="noopener">{E(fuente_cta)}</a>
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
    # Por defecto la pieza es una investigación; algunas (p. ej. un homenaje) traen
    # su propia etiqueta en art["seccion_label"] para no rotularse como tal.
    seccion_label = art.get("seccion_label") or f"Investigación · {tema}"
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-azul-bop);">{E(seccion_label)}</span>
  <h1>{E(art['titular'])}</h1>
  <p class="tc-articulo-entradilla">{E(art['entradilla'])}</p>
  {imagen_html}
  {secciones_html}
  <div class="tc-source-box">
    <strong>Fuentes:</strong>
    <ul class="tc-links-list">{fuentes_html}</ul>
  </div>
  {bloque_compartir(f"https://elterracampino.es/blog/{slug}.html", art['titular'])}
  <p class="tc-item-meta"><a href="../index.html">← Volver a portada</a></p>
</div></article>"""
    return shell(f"{art['titular']} — El Terracampino", body, depth=1, desc=art["entradilla"][:150])


def bloque_compartir(url: str, titulo: str) -> str:
    """Botón de compartir al final de una pieza. En un periódico de pueblo todo
    circula por el grupo de WhatsApp de la familia: sin esto se renuncia a la
    vía por la que de verdad llegan lectores nuevos."""
    from urllib.parse import quote
    texto = quote(f"{titulo} — {url}")
    return f"""<div class="tc-compartir">
    <span class="tc-section-label" style="color:var(--tc-tinta-tierra);">¿Te ha parecido interesante?</span>
    <p class="tc-pieza-cuerpo">Mándaselo a quien creas que le va a interesar.</p>
    <p><a class="tc-button" href="https://wa.me/?text={texto}" target="_blank" rel="noopener">Compartir por WhatsApp</a>
    <button class="tc-button tc-button--sec" type="button" onclick="navigator.clipboard&amp;&amp;navigator.clipboard.writeText('{url}').then(function(){{this.textContent='¡Enlace copiado!';}}.bind(this));">Copiar el enlace</button></p>
  </div>"""


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


def cargar_esquelas() -> dict[str, list[dict]]:
    """Esquelas ya revisadas por Daniel (sitegen/almacen_esquelas.py), agrupadas
    por municipio. Vienen del formulario de la web (web/api/esquela.js) y pasan
    SIEMPRE por revisión humana antes de publicarse. Si hay foto, se descarga a
    web/assets/esquelas/. Si el almacén no está o falla, se sigue sin esquelas."""
    from sitegen import almacen_esquelas
    if not almacen_esquelas.disponible():
        return {}
    try:
        publicadas = almacen_esquelas.listar_publicadas()
    except almacen_esquelas.AlmacenError as exc:
        print(f"  aviso: sin esquelas ({exc})", file=sys.stderr)
        return {}

    destino = WEB / "assets" / "esquelas"
    por_slug: dict[str, list[dict]] = {}
    for e in publicadas:
        archivo = None
        if e.get("tiene_foto"):
            destino.mkdir(parents=True, exist_ok=True)
            archivo = f"{e['id']}.jpg"
            ruta = destino / archivo
            if not ruta.exists():
                try:
                    ruta.write_bytes(almacen_esquelas.descargar(f"publicadas/{e['id']}.jpg"))
                except almacen_esquelas.AlmacenError:
                    archivo = None
        e["archivo"] = archivo
        # La fecha de referencia para ordenar y decidir "reciente" vs archivo:
        # la del fallecimiento si consta, si no la de aprobación.
        e["_fecha_orden"] = e.get("fecha_fallecimiento") or (e.get("aprobada_en") or "")[:10]
        por_slug.setdefault(e.get("pueblo_slug", ""), []).append(e)
    for lista in por_slug.values():
        lista.sort(key=lambda x: x["_fecha_orden"], reverse=True)
    if publicadas:
        print(f"  {len(publicadas)} esquelas publicadas")
    return por_slug


def cargar_archivo_fotografico() -> dict[str, list[dict]]:
    """Fotos antiguas del archivo comunitario ya revisadas
    (sitegen/almacen_archivo.py), agrupadas por municipio y descargadas a
    web/assets/archivo/. Si el almacén no está o falla, se sigue sin archivo."""
    from sitegen import almacen_archivo
    if not almacen_archivo.disponible():
        return {}
    try:
        publicadas = almacen_archivo.listar_publicadas()
    except almacen_archivo.AlmacenError as exc:
        print(f"  aviso: sin archivo fotográfico ({exc})", file=sys.stderr)
        return {}

    destino = WEB / "assets" / "archivo"
    por_slug: dict[str, list[dict]] = {}
    for f in publicadas:
        destino.mkdir(parents=True, exist_ok=True)
        archivo = f"{f['id']}.jpg"
        ruta = destino / archivo
        if not ruta.exists():
            try:
                ruta.write_bytes(almacen_archivo.descargar(f"publicadas/{f['id']}.jpg"))
            except almacen_archivo.AlmacenError:
                continue
        f["archivo"] = archivo
        por_slug.setdefault(f.get("pueblo_slug", ""), []).append(f)
    # Orden: por año si se puede leer un número, si no las más recientes de envío.
    def _clave(x: dict):
        m = re.search(r"\d{4}", str(x.get("anio") or ""))
        return (0, int(m.group(0))) if m else (1, x.get("aprobada_en", ""))
    for lista in por_slug.values():
        lista.sort(key=_clave)
    if publicadas:
        print(f"  {len(publicadas)} fotos del archivo")
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


def cargar_comentarios_aprobados(limite: int = 12) -> list[dict]:
    """Comentarios del grupo de discusión de Telegram ya moderados por IA
    (scripts/moderar_comentarios.py, ejecución autónoma sin revisión humana —
    ver sitegen/almacen_comentarios.py). Si el almacén no está configurado o
    falla, el sitio sigue sin el tablón: no es motivo para tumbar el build."""
    from sitegen import almacen_comentarios
    if not almacen_comentarios.disponible():
        return []
    try:
        return almacen_comentarios.listar_aprobados()[:limite]
    except almacen_comentarios.AlmacenError as exc:
        print(f"  aviso: sin comentarios del tablón ({exc})", file=sys.stderr)
        return []


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
    datos.pop("_verificado", None)
    return datos


def _mes_anio_verificacion() -> str:
    """'julio de 2026' de la última verificación del directorio, para el aviso
    de frescura de la web. Vacío si no consta."""
    path = ROOT / "data" / "directorio_servicios.json"
    if not path.exists():
        return ""
    fecha = json.loads(path.read_text(encoding="utf-8")).get("_verificado")
    if not fecha:
        return ""
    try:
        d = date.fromisoformat(fecha)
    except ValueError:
        return ""
    return f"{MESES[d.month - 1]} de {d.year}"


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
    """Cabecera con menú. En móvil el menú se despliega a pantalla completa desde
    un botón de tres rayas: antes era una tira con scroll lateral sin ninguna
    pista de que se podía deslizar, así que 7 de las 10 secciones —entre ellas
    Esquelas y Acompañar, las que más busca el público mayor— eran invisibles."""
    up = "../" * depth
    home = up + "index.html"
    return f"""<header class="tc-header"><div class="tc-wrap tc-header-inner">
  <a href="{home}" class="tc-logo"><img src="{up}assets/logo.png" alt="El Terracampino" height="52"></a>
  <button class="tc-nav-toggle" id="tc-nav-toggle" aria-expanded="false" aria-controls="tc-nav">☰ Menú</button>
  <nav class="tc-nav" id="tc-nav">
    <button class="tc-nav-cerrar" id="tc-nav-cerrar" aria-label="Cerrar el menú">×</button>
    <a href="{home}">Portada</a>
    <a href="{home}#pueblos">Elige tu pueblo</a>
    <a href="{home}#comarca">La comarca</a>
    <a href="{home}#blog">Investigaciones</a>
    <a href="{up}huerta.html">Huerta</a>
    <a href="{up}campo.html">El campo</a>
    <a href="{up}leyendas.html">Leyendas</a>
    <a href="{up}esquelas.html">Esquelas</a>
    <a href="{up}acompanar.html">Acompañar</a>
    <a href="{up}archivo.html">Archivo</a>
  </nav>
</div>
<script>
(function() {{
  var b = document.getElementById("tc-nav-toggle"), n = document.getElementById("tc-nav"),
      c = document.getElementById("tc-nav-cerrar");
  if (!b || !n) return;
  function abrir(v) {{
    n.classList.toggle("tc-nav--abierto", v);
    b.setAttribute("aria-expanded", v ? "true" : "false");
    document.body.style.overflow = v ? "hidden" : "";
  }}
  b.addEventListener("click", function() {{ abrir(!n.classList.contains("tc-nav--abierto")); }});
  if (c) c.addEventListener("click", function() {{ abrir(false); }});
  // Al tocar una sección se cierra solo: si no, el menú tapaba la página a la
  // que acabas de saltar cuando el destino está en la misma página (#pueblos).
  n.addEventListener("click", function(e) {{ if (e.target.tagName === "A") abrir(false); }});
  document.addEventListener("keydown", function(e) {{ if (e.key === "Escape") abrir(false); }});
}})();
</script></header>"""


def newsletter_popup(depth: int) -> str:
    """Popup de suscripción + cableado de TODOS los formularios .tc-form de la
    página contra /api/suscribir (web/api/suscribir.js, función de Vercel que
    habla con MailerLite en servidor — la clave nunca toca el navegador).

    El popup sale una sola vez por visitante (localStorage), a los 3s, y no
    vuelve a molestar ni aunque cierre sin suscribirse."""
    up = "../" * depth
    return f"""<div class="tc-popup-overlay" id="tc-popup-overlay">
  <div class="tc-popup" role="dialog" aria-label="Suscripción a la newsletter">
    <button class="tc-popup-close" id="tc-popup-close" aria-label="Cerrar">×</button>
    <h2>La semana terracampina</h2>
    <p>Un correo a la semana con lo que pasa cerca, contado claro. Al apuntarte te mandamos además los cinco reportajes que ya hemos publicado, uno por semana.</p>
    <form class="tc-form"><input class="tc-input" type="email" placeholder="tu@correo.es" aria-label="Correo" required><input type="text" name="web" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px;" aria-hidden="true"><button class="tc-button" type="submit">Suscribirme</button></form>
  </div>
</div>
<script>
// "Otro pueblo…" en los formularios. La comarca tiene 178 municipios y el sitio
// solo hace ficha de unos 20: sin esto, una familia de Cuenca de Campos o de
// Castromocho no podía publicar la esquela de su madre porque, literalmente, no
// había opción que marcar. El pueblo escrito a mano llega en el mismo campo y
// lo ve el revisor humano, que es quien decide.
function puebloElegido(idSelect, idOtro) {{
  var s = document.getElementById(idSelect), o = document.getElementById(idOtro);
  if (s && s.value === "_otro" && o) return (o.value || "").trim();
  return s ? s.value : "";
}}
document.addEventListener("DOMContentLoaded", function() {{
  [["es-pueblo", "es-pueblo-otro"], ["ar-pueblo", "ar-pueblo-otro"],
   ["tc-chiv-pueblo", "tc-chiv-pueblo-otro"]].forEach(function(par) {{
    var s = document.getElementById(par[0]), o = document.getElementById(par[1]);
    if (!s || !o) return;
    s.addEventListener("change", function() {{
      var otro = s.value === "_otro";
      o.hidden = !otro;
      o.required = otro;
      if (otro) o.focus();
    }});
  }});
}});
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
            // Con doble confirmación, un "bienvenido" a secas hacía que la gente
            // diera por hecho que ya estaba y no confirmara nunca. Hay que decir
            // exactamente qué tiene que hacer ahora.
            form.innerHTML = "<p class=\\"tc-form-ok\\">Casi está. Te hemos mandado un correo: <strong>ábrelo y pulsa el enlace para confirmar</strong>. Si no lo ves en unos minutos, mira en la carpeta de spam o correo no deseado.</p>";
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
    document.body.style.overflow = "";
    localStorage.setItem(KEY, "1");
  }}
  // No se lanza encima de un reportaje: es justo el momento en que el lector
  // decide si se queda, y taparle el titular antes de haber leído tres frases
  // es pedirle el correo antes de haberle dado nada.
  if (document.querySelector(".tc-blog-articulo")) return;
  setTimeout(function() {{
    overlay.classList.add("tc-popup-overlay--visible");
    // Bloquear el scroll de detrás: si no, la página se movía por debajo del
    // cartel y se podía mover pero no leer.
    document.body.style.overflow = "hidden";
  }}, 3000);
  close.addEventListener("click", ocultar);
  overlay.addEventListener("click", function(e) {{ if (e.target === overlay) ocultar(); }});
  // Escape y tocar fuera: antes la ÚNICA salida era una "×" diminuta, y quien
  // no la acertaba se quedaba encerrado en el cartel.
  document.addEventListener("keydown", function(e) {{
    if (e.key === "Escape" && overlay.classList.contains("tc-popup-overlay--visible")) ocultar();
  }});
}})();
</script>"""


def footer(depth: int) -> str:
    up = "../" * depth
    home = up + "index.html"
    return f"""<footer class="tc-footer"><div class="tc-wrap">
  <p class="tc-aviso">Este medio resume información pública procedente de fuentes oficiales y abiertas. Los resúmenes no sustituyen al documento original. Ante cualquier trámite, plazo, ayuda o acuerdo municipal, consulta siempre la fuente oficial enlazada.</p>
  <div class="tc-footer-links"><a href="{home}">Portada</a><a href="{up}gente.html">Gente de Campos</a><a href="{up}chivatazo.html">¿Sabes algo? Cuéntanoslo</a><a href="{up}aviso-legal.html">Aviso legal</a><span>El tiempo: Open-Meteo · Boletines: BOP</span><span>elterracampino.es</span></div>
  <div class="tc-footer-redes">Síguenos: <a href="https://www.facebook.com/profile.php?id=61592649658185" target="_blank" rel="noopener">Facebook</a><a href="https://www.instagram.com/elterracampino/" target="_blank" rel="noopener">Instagram</a><a href="https://t.me/elterracampino" target="_blank" rel="noopener">Telegram</a></div>
  <p class="tc-aviso tc-propiedad">El Terracampino es un medio propiedad de María Vega Blanco. Desarrollado por <a href="{up}aviso-legal.html">Naraya Services Cloud Consulting S.L.</a></p>
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

def bloque_paro(paro: dict | None) -> str:
    """Paro registrado en la comarca, con su comparativa interanual.

    Se dice siempre "paro registrado" y no "tasa de paro" (son cosas distintas)
    y se advierte de cuántos pueblos no tienen cifra pública: en más de la mitad
    de la comarca hay menos de 5 parados y el SEPE los oculta por secreto
    estadístico. Sin esa advertencia, el total parecería el de toda la comarca."""
    if not paro:
        return ""
    v = paro.get("vs_hace_un_ano")
    comparativa = ""
    if v and v.get("porcentaje") is not None:
        verbo = "menos" if v["baja"] else "más"
        comparativa = (f", un {dec(abs(v['porcentaje']))}% {verbo} que hace un año "
                       f"en los {v['municipios_comparados']} pueblos comparables")
    return f"""<section class="tc-wrap">
  <div class="tc-card">
    <h3 style="margin-top:0;">El paro en la comarca</h3>
    <p class="tc-pieza-cuerpo"><strong>{miles(paro['total'])}</strong> personas apuntadas al paro en
    {paro['con_dato']} municipios de Tierra de Campos en {E(paro['mes_nombre'])} de {paro['anio']}{E(comparativa)}.</p>
    <p class="tc-item-meta">Paro registrado en las oficinas de empleo (no es la tasa de paro de la EPA).
    Otros {paro['ocultos']} pueblos de la comarca no aparecen: tienen menos de 5 personas apuntadas y el
    SEPE no publica la cifra exacta por secreto estadístico. Fuente:
    <a href="https://www.sepe.es/HomeSepe/que-es-el-sepe/estadisticas/datos-estadisticos/municipios.html"
    target="_blank" rel="noopener">SEPE</a>.</p>
  </div>
</section>"""


def render_home(built: list[dict], feed: list[dict], hoy: date,
                avisos: list[dict] | None = None, cots: list[dict] | None = None,
                paro: dict | None = None) -> str:
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
        # id="pueblos": el enlace "Elige tu pueblo" del menú apunta aquí. Antes no
        # existía ningún elemento con ese id, así que desde la portada el enlace
        # más importante del menú no hacía absolutamente nada.
        tiempo_html = f"""<div class="tc-weather-summary" id="pueblos">
      <div class="tc-weather-summary-txt">
        <span class="tc-section-label" style="color:var(--tc-azul-bop);">El tiempo en la comarca</span>
        <p>Hoy en Tierra de Campos, <strong>{E(r['desc'])}</strong> y entre <strong>{r['tmin']}°</strong> y <strong>{r['tmax']}°</strong>. El pueblo más caluroso ahora es {E(r['hot_name'])}, con {r['hot_t']}°.</p>
      </div>
      <div class="tc-weather-summary-pick">{selector(built, 0)}</div>
    </div>"""
    else:
        # Sin datos de tiempo el selector de pueblo NO puede desaparecer: es la
        # mejor entrada del sitio y el ancla del menú.
        tiempo_html = f"""<div class="tc-weather-summary" id="pueblos">
      <div class="tc-weather-summary-pick">{selector(built, 0)}</div>
    </div>"""

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

    # Tablón de comentarios del grupo de discusión de Telegram, moderados de
    # forma 100% autónoma por IA (sitegen/ia.py:moderar_comentario, ejecutado
    # por scripts/moderar_comentarios.py) — nadie humano revisa esto después,
    # así que solo llegan aquí los que la propia IA ya aprobó. Ver
    # sitegen/almacen_comentarios.py para el porqué del diseño.
    # Precios del cereal: en portada solo el titular (trigo y cebada, que es lo
    # que casi todo el mundo siembra aquí); el detalle vive en /campo.html.
    lonja_html = ""
    destacados = [c for c in (cots or []) if c["slug"] in ("trigo", "cebada")]
    if destacados:
        piezas = []
        for c in destacados:
            d = c["plazas"].get("Valladolid") or next(iter(c["plazas"].values()), None)
            if not d or not d["vigente"]:
                continue
            v = d["vs_anterior"]
            mov = ""
            if v and v["euros"]:
                mov = f' ({"+" if v["sube"] else ""}{v["euros"]:.0f} € respecto a la sesión anterior)'
            piezas.append(f'<li><strong>{E(c["nombre"])}</strong>: {d["precio"]:.0f} €/t{E(mov)}</li>')
        if piezas:
            lonja_html = f"""<section class="tc-wrap">
  <div class="tc-card">
    <h3 style="margin-top:0;">Precios del cereal</h3>
    <ul class="tc-links-list">{''.join(piezas)}</ul>
    <p class="tc-item-meta">Lonja de Valladolid y Palencia ·
    <a href="campo.html">ver todos los precios →</a></p>
  </div>
</section>"""

    comentarios = cargar_comentarios_aprobados()
    if comentarios:
        items_comentarios = "".join(f'''<li class="tc-comentario">
      <span class="tc-comentario-autor">{E(c.get("autor") or "Alguien de la comarca")}</span>
      <p class="tc-comentario-texto">{E(c["texto"])}</p>
      <span class="tc-item-meta">{E((c.get("recibido_en") or "")[:10])}</span>
    </li>''' for c in comentarios)
        comentarios_html = f"""<section class="tc-wrap">
  <div class="tc-card">
    <h3>Se comenta en el canal</h3>
    <ul class="tc-comentarios-lista">{items_comentarios}</ul>
    <p class="tc-item-meta">Mensajes del grupo de Telegram de El Terracampino, filtrados automáticamente
    por IA antes de aparecer aquí — <a href="https://t.me/elterracampino" target="_blank" rel="noopener">únete a la conversación</a>.</p>
  </div>
</section>"""
    else:
        comentarios_html = ""

    alm = almanaque_del_dia(hoy)
    body = f"""<section class="tc-masthead"><div class="tc-wrap">
  <p class="tc-hoy-fecha">{fecha_larga(hoy)}</p>
  <h1>El tiempo y las noticias de tu pueblo, en limpio</h1>
  <p class="tc-masthead-sub">Lo que pasa en los pueblos de Tierra de Campos, contado claro y con la fuente al lado.</p>
  <p class="tc-almanaque">«{E(alm['refran'])}» <span class="tc-almanaque-sep">·</span> Hoy es {E(alm['santo'])} <span class="tc-almanaque-sep">·</span> {alm['luna']['emoji']} {E(alm['luna']['fase'])}</p>
</div></section>

{banda_avisos(avisos or [])}

<section class="tc-wrap" id="tiempo">{tiempo_html}</section>

<section class="tc-wrap" id="comarca">
  <h2 class="tc-block-title">Noticias relevantes de la comarca</h2>
  {items}
</section>

{blog_html}

{comentarios_html}

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

{lonja_html}

{bloque_paro(paro)}

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
        # NUNCA devolver "" aquí. Si Open-Meteo falla para un pueblo, la sección
        # entera desaparecía sin decir nada y la ficha empezaba por la caja de
        # Telegram — justo lo que promete el titular de la portada ("el tiempo de
        # tu pueblo") evaporado en silencio. Mejor decir que ahora no se puede.
        return f"""<section class="tc-wrap tc-weather">
  <span class="tc-section-label" style="color:var(--tc-azul-bop);">A ras de tierra — El tiempo hoy en {E(m['name'])}</span>
  <p class="tc-pieza-cuerpo">Ahora mismo no podemos darte el tiempo de {E(m['name'])}: el servicio
  meteorológico no responde. Vuelve a probar en un rato — se actualiza solo varias veces al día.</p>
</section>"""
    dias = "".join(f"""<article class="tc-day">
      <span class="tc-day-name">{E(d['dia'].capitalize())}</span>
      <h4 class="tc-day-titular">{E(d['titular'])}</h4>
      <p class="tc-day-texto">{E(d['texto'])}</p>
      <span class="tc-day-temp tc-data">{d['max']}° <span class="tc-day-min">{d['min']}°</span></span>
    </article>""" for d in w["dias"][1:])
    lat, lon = m.get("lat"), m.get("lon")
    # El número grande y la descripción de "ahora mismo" quedaban fijados a la
    # hora del último build (una vez al día) y mal etiquetados como en vivo —
    # un vecino que entraba por la tarde veía la temperatura de la mañana. Si
    # hay coordenadas, un script los refresca de verdad al cargar la página,
    # pidiendo el dato actual a Open-Meteo (misma fuente, sin clave, sin
    # servidor propio). El artículo y los próximos días siguen siendo el
    # texto redactado en el build: eso sí tiene sentido que sea del día, no
    # al segundo.
    vivo_html = "" if not (lat and lon) else f"""<script>
(function() {{
  var WMO = {{0:"despejado",1:"casi despejado",2:"nubes y claros",3:"nublado",45:"niebla",48:"niebla helada",
    51:"llovizna débil",53:"llovizna",55:"llovizna intensa",61:"lluvia débil",63:"lluvia",65:"lluvia fuerte",
    66:"lluvia helada",67:"lluvia helada fuerte",71:"nieve débil",73:"nieve",75:"nieve intensa",77:"aguanieve",
    80:"chubascos",81:"chubascos",82:"chubascos fuertes",85:"chubascos de nieve",86:"chubascos de nieve",
    95:"tormenta",96:"tormenta con granizo",99:"tormenta fuerte con granizo"}};
  fetch("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=Europe%2FMadrid")
    .then(function(r) {{ return r.ok ? r.json() : null; }})
    .then(function(d) {{
      if (!d || !d.current) return;
      var big = document.getElementById("tc-weather-big-live");
      var desc = document.getElementById("tc-weather-desc-live");
      var sello = document.getElementById("tc-weather-sello-live");
      if (big) big.textContent = Math.round(d.current.temperature_2m) + "°";
      if (desc) desc.textContent = WMO[d.current.weather_code] || "tiempo variable";
      if (sello) sello.textContent = "En vivo · Open-Meteo";
    }})
    .catch(function() {{ /* si falla, se queda el dato del build — mejor eso que nada */ }});
}})();
</script>"""
    return f"""<div class="tc-weather-hero">
    <div class="tc-weather-now">
      <span class="tc-weather-big tc-data" id="tc-weather-big-live">{w['ahora']['temp']}°</span>
      <span class="tc-weather-desc" id="tc-weather-desc-live">{E(w['ahora']['desc'])}</span>
      <span class="tc-sello tc-sello--auto" id="tc-weather-sello-live">Automático · Open-Meteo</span>
    </div>
    {vivo_html}
    <p class="tc-weather-article">{E(w['articulo'])}</p>
    <span class="tc-section-label" style="color:var(--tc-azul-bop);">Los próximos días</span>
    <div class="tc-days">{dias}</div>
  </div>"""


def render_municipio(m: dict, anuncios: list[dict], hoy: date,
                     avisos: list[dict] | None = None) -> str:
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
        verif = _mes_anio_verificacion()
        sello = f"Datos verificados por última vez en {verif}" if verif else "Datos de fuentes públicas"
        directorio_html = f"""<div class="tc-card"><h3>Servicios y profesionales de {E(m['name'])}</h3>
      {''.join(bloques)}
      <p class="tc-item-meta" style="margin-top:10px;">{E(sello)} (Páginas Amarillas, web del
      ayuntamiento, fichas de negocio) — pueden quedar desactualizados. ¿Ves un error, un negocio cerrado
      o falta el tuyo? <a href="https://wa.me/34695645395" target="_blank" rel="noopener">Dínoslo por WhatsApp</a>.</p></div>"""
    else:
        directorio_html = ""

    # Negocios y tablón: sección honesta. NO se inventan anuncios; los envían vecinos/comercios.
    tablon_html = f"""<div class="tc-card"><h3>Negocios de aquí · Tablón</h3>
      <p class="tc-pieza-cuerpo">Traspasos, alquiler de locales y de viviendas, aperturas y comercios de {E(m['name'])}. Todavía no hay anuncios publicados.</p>
      <p style="margin:10px 0 6px;"><span class="tc-button">Publicar un anuncio</span></p>
      <p class="tc-item-meta">Los anuncios los envían vecinos y comercios y se publican tras revisión. No se inventan.</p></div>"""

    # Esquelas del pueblo (sitegen/almacen_esquelas.py): revisadas a mano, nunca
    # automáticas. Recientes destacadas + archivo "In memoriam".
    esquelas_html = bloque_esquelas_municipio(m.get("_esquelas", []), hoy)

    # Archivo fotográfico: fotos antiguas que aportan los vecinos, revisadas.
    archivo_html = bloque_archivo_municipio(m.get("_archivo", []))

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

{banda_avisos(avisos or [], provincia=m.get("province"))}

<div class="tc-wrap tc-muni-grid">
  <main class="tc-muni-main">
    <h2 class="tc-block-title">A ras de tierra — {tiempo_titular}</h2>
    {weather_block(m)}
    <div class="tc-channel tc-channel--inline"><div class="tc-channel-inner">
      <div><h3 style="margin:0 0 4px;">Recibe las noticias de la comarca por Telegram</h3>
      <p style="margin:0; font-size:.9rem;">Un mensaje al día con el tiempo y lo que pasa en los pueblos de Tierra de Campos —{E(m['name'])} incluido—: plenos, ayudas, agenda y alguna historia de aquí.</p>
      <p style="margin:6px 0 0; font-size:.85rem; color:var(--tc-texto-secundario);">Telegram es una aplicación gratuita, parecida a WhatsApp. Si no la tienes, al pulsar te pedirá instalarla.</p></div>
      <div class="tc-channel-btns"><a class="tc-button" href="https://t.me/elterracampino" target="_blank" rel="noopener">Telegram</a> <a class="tc-button tc-button--ghost" href="https://wa.me/34695645395" target="_blank" rel="noopener">WhatsApp</a></div>
    </div></div>
    {propias_html}
    {ayto}
    {ayudas_html}
    {esquelas_html}
    {galeria_html}
    {archivo_html}
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


def render_chivatazo(built: list[dict]) -> str:
    """Buzón de chivatazos anónimos (web/api/chivatazo.js + sitegen/almacen_chivatazos.py).
    Nunca se publica un chivatazo tal cual — solo alimenta, tras revisión
    editorial de Daniel, hechos que se verifican aparte para una pieza propia
    (mismo criterio que el radar de pistas)."""
    opciones_pueblo = "".join(f'<option value="{E(m["name"])}">{E(m["name"])}</option>' for m in built)
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-tinta-tierra);">Buzón</span>
  <h1>¿Sabes algo? Cuéntanoslo</h1>
  <p class="tc-articulo-entradilla">Una obra rara, una subvención que no cuadra, algo de un pleno que no
  se explicó bien... Si tienes una pista de la comarca, mándala aquí. <strong>No te pedimos el nombre ni el
  correo</strong>: guardamos solo el texto que escribas y el pueblo, si lo indicas.</p>
  <p class="tc-item-meta">Para ser exactos: como en cualquier web, el servidor que recibe el formulario ve tu
  dirección IP de forma momentánea, y esta página carga una medición de visitas. No lo usamos para saber quién
  eres ni lo guardamos junto a tu aviso, pero no podemos prometerte un anonimato absoluto. Si lo que tienes
  entre manos es delicado de verdad, mejor cuéntanoslo en persona.</p>

  <div class="tc-card">
    <form id="tc-chivatazo-form">
      <p style="margin:0 0 6px;"><label for="tc-chiv-pueblo" style="font-weight:700; font-size:.9rem;">Pueblo (opcional)</label></p>
      <select id="tc-chiv-pueblo" name="pueblo" class="tc-muni-select" style="margin-bottom:14px;">
        <option value="">No lo sé / es de toda la comarca</option>{opciones_pueblo}<option value="_otro">Otro pueblo de la comarca…</option>
      </select>
      <input id="tc-chiv-pueblo-otro" class="tc-input" placeholder="Escribe el nombre del pueblo" maxlength="80" hidden style="width:100%; box-sizing:border-box; margin:-6px 0 14px;" aria-label="Nombre del pueblo">
      <p style="margin:0 0 6px;"><label for="tc-chiv-texto" style="font-weight:700; font-size:.9rem;">Cuéntanoslo</label></p>
      <textarea id="tc-chiv-texto" name="texto" class="tc-input" rows="6" required minlength="20" maxlength="4000"
        placeholder="Cuanto más concreto (dónde, cuándo, qué has visto), más fácil es comprobarlo."
        style="width:100%; box-sizing:border-box; font-family:inherit; resize:vertical;"></textarea>
      <input type="text" name="web" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px;" aria-hidden="true">
      <p style="margin:14px 0 0;"><button class="tc-button" type="submit">Enviar de forma anónima</button></p>
      <p class="tc-item-meta" style="margin:10px 0 0;">Al enviarlo aceptas que tratemos estos datos para publicar la pista si se confirma. Cómo lo hacemos y cómo pedir que se borren, en el <a href="aviso-legal.html#privacidad">aviso legal</a>.</p>
      <p id="tc-chiv-resultado" class="tc-item-meta" style="margin-top:10px;"></p>
    </form>
  </div>

  <p class="tc-item-meta" style="margin-top:14px;">Nada se publica directamente desde aquí: una persona del
  equipo valora cada aviso y, si hay algo que investigar, se hacen las comprobaciones necesarias antes de
  escribir nada — igual que con cualquier otra pieza de este periódico. No es un canal de emergencias: para
  algo urgente, llama al 112.</p>
  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>
<script>
(function() {{
  var form = document.getElementById("tc-chivatazo-form");
  form.addEventListener("submit", function(e) {{
    e.preventDefault();
    var texto = document.getElementById("tc-chiv-texto").value;
    var pueblo = puebloElegido("tc-chiv-pueblo", "tc-chiv-pueblo-otro");
    var honey = form.querySelector('input[name="web"]');
    var resultado = document.getElementById("tc-chiv-resultado");
    var btn = form.querySelector("button");
    btn.disabled = true; btn.textContent = "Enviando…";
    fetch("api/chivatazo", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ texto: texto, pueblo: pueblo, web: honey.value }}),
    }})
      .then(function(r) {{ return r.json().then(function(d) {{ return {{ ok: r.ok, body: d }}; }}); }})
      .then(function(res) {{
        if (res.ok) {{
          form.style.display = "none";
          resultado.textContent = "Recibido. Gracias — lo revisamos con calma.";
        }} else {{
          resultado.textContent = res.body.error || "No se pudo enviar. Inténtalo más tarde.";
          btn.disabled = false; btn.textContent = "Enviar de forma anónima";
        }}
      }})
      .catch(function() {{
        resultado.textContent = "No se pudo enviar. Inténtalo más tarde.";
        btn.disabled = false; btn.textContent = "Enviar de forma anónima";
      }});
  }});
}})();
</script>"""
    return shell("¿Sabes algo? Cuéntanoslo — El Terracampino", body, depth=0,
                 desc="Buzón anónimo de chivatazos para El Terracampino, periódico hiperlocal de Tierra de Campos.")


_COLOR_AVISO = {
    "amarillo": "#C9A227",
    "naranja": "#D2691E",
    "rojo": "var(--tc-rojo-aviso, #A32C2C)",
}


def _fecha_aviso(iso: str | None) -> str:
    """'2026-07-25T13:00:00' -> 'el sábado a las 13:00'. Cadena vacía si no hay."""
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return f"el {DIAS[d.weekday()]} a las {d.strftime('%H:%M')}"


def banda_avisos(avisos: list[dict], provincia: str | None = None) -> str:
    """Banda de alerta meteorológica. En la ficha de un pueblo solo se muestran
    los avisos de SU provincia (las zonas de AEMET son 'Meseta de <provincia>',
    ver scrapers/aemet_avisos.py); en portada, todos los de la comarca.

    Es el único elemento del sitio que puede ser urgente, así que va arriba del
    todo — pero sin alarmismo: se dice el nivel, el fenómeno, cuándo y dónde,
    con enlace a AEMET, y nada más."""
    relevantes = [a for a in avisos if provincia is None or a["provincia"] == provincia]
    if not relevantes:
        return ""
    filas = []
    for a in relevantes:
        cuando = _fecha_aviso(a.get("inicio"))
        hasta = _fecha_aviso(a.get("fin"))
        periodo = f" · desde {cuando}" if cuando else ""
        if hasta:
            periodo += f" hasta {hasta}"
        lugar = "" if provincia else f" · {E(a['zona'])}"
        filas.append(
            f'<li><strong>Aviso {E(a["nivel"])}</strong> por {E(a["fenomeno"].lower())}'
            f'{lugar}{E(periodo)}</li>'
        )
    color = _COLOR_AVISO.get(relevantes[0]["nivel"], "#C9A227")
    return f"""<section class="tc-wrap"><div class="tc-card" style="border-left:5px solid {color};">
  <h3 style="margin-top:0;">Avisos de AEMET {'en la comarca' if provincia is None else 'en tu zona'}</h3>
  <ul class="tc-links-list">{''.join(filas)}</ul>
  <p class="tc-item-meta">Fuente: Agencia Estatal de Meteorología (Plan Meteoalerta) ·
  <a href="https://www.aemet.es/es/eltiempo/prediccion/avisos" target="_blank" rel="noopener">ver el detalle en AEMET</a></p>
</div></section>"""


def _fila_lonja(c: dict) -> str:
    """Una fila de la tabla de precios: producto + precio de cada plaza."""
    celdas = []
    for plaza in ("Valladolid", "Palencia"):
        d = c["plazas"].get(plaza)
        if not d:
            celdas.append("<td>—</td>")
            continue
        if not d["vigente"]:
            # Fuera de campaña (típico del girasol): se dice el precio pero se
            # marca con su fecha, para no venderlo como cotización de hoy.
            try:
                f = date.fromisoformat(d["fecha"])
                cuando = f"{f.day} de {MESES[f.month - 1]} de {f.year}"
            except (ValueError, IndexError):
                cuando = d["fecha"]
            celdas.append(f'<td>{d["precio"]:.0f} €/t <span class="tc-item-meta">'
                          f'(último precio, {E(cuando)})</span></td>')
            continue
        v = d["vs_anterior"]
        flecha = ""
        if v and v["euros"]:
            signo = "▲" if v["sube"] else "▼"
            flecha = (f' <span class="tc-item-meta">{signo} {abs(v["euros"]):.0f} €</span>')
        celdas.append(f'<td><strong>{d["precio"]:.0f} €/t</strong>{flecha}</td>')
    return f"<tr><td>{E(c['nombre'])}</td>{''.join(celdas)}</tr>"


def _fecha_lonja(cots: list[dict]) -> str:
    """Fecha de la última sesión con cotización vigente (la más reciente)."""
    fechas = [d["fecha"] for c in cots for d in c["plazas"].values() if d["vigente"]]
    if not fechas:
        return ""
    try:
        return fecha_larga(date.fromisoformat(max(fechas)))
    except ValueError:
        return ""


def bloque_embalses(emb: dict | None) -> str:
    """Situación del agua embalsada en los sistemas que riegan la comarca.
    Se da el porcentaje y, sobre todo, la comparación con el año pasado y con la
    media de diez años: un dato de hm3 suelto no le dice nada a nadie."""
    if not emb or not emb.get("sistemas"):
        return ""
    from scrapers.embalses import resumen as resumen_embalses
    r = resumen_embalses(emb)
    if not r:
        return ""

    def _frase(pct: float | None, referencia: str) -> str:
        if pct is None:
            return ""
        if abs(pct) < 1:
            return f"prácticamente igual que {referencia}"
        return f"un {dec(abs(pct))}% {'más' if pct > 0 else 'menos'} que {referencia}"

    comparativas = [f for f in (
        _frase(r["vs_anio_anterior_pct"], "el año pasado"),
        _frase(r["vs_media_pct"], "la media de los diez últimos años"),
    ) if f]
    filas = "".join(
        f'<tr><td>{E(s["sistema"])}</td>'
        f'<td>{s["total"]["actual_hm3"]:.0f} hm³</td>'
        f'<td>{s["total"]["actual_pct"]:.0f}%</td></tr>'
        for s in emb["sistemas"] if s.get("total")
    )
    fecha = ""
    if emb.get("fecha"):
        try:
            fecha = f" Datos del {fecha_larga(date.fromisoformat(emb['fecha']))}."
        except ValueError:
            pass
    return f"""<h2 class="tc-blog-subtitulo">El agua embalsada</h2>
  <p class="tc-articulo-parrafo">Los embalses que riegan la comarca están al
  <strong>{r['actual_pct']:.0f}%</strong> de su capacidad ({r['actual_hm3']:.0f} hm³ de
  {r['capacidad_hm3']:.0f}){': ' + ' y ' .join(comparativas) if comparativas else ''}.{E(fecha)}</p>
  <div style="overflow-x:auto;">
  <table class="tc-tabla-lonja" style="width:100%; border-collapse:collapse;">
    <thead><tr><th style="text-align:left;">Sistema</th><th style="text-align:left;">Embalsado</th><th style="text-align:left;">Llenado</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>
  </div>
  <p class="tc-item-meta">Sistemas Esla-Órbigo (riega la Tierra de Campos leonesa y, por el Esla,
  Villalpando), Carrión (Carrión, Villada, Paredes, Becerril, Fuentes de Nava) y Pisuerga (que
  alimenta el Canal de Castilla y el Canal de Campos). Fuente:
  <a href="https://www.saihduero.es/situacion-embalses" target="_blank" rel="noopener">SAIH de la
  Confederación Hidrográfica del Duero</a>; datos provisionales sujetos a revisión.</p>"""


def render_lonja(cots: list[dict], emb: dict | None = None) -> str:
    """Página propia con los precios del cereal y su comparativa anual."""
    if not cots:
        cuerpo = '<p class="tc-pieza-cuerpo">Ahora mismo no hay cotizaciones disponibles.</p>'
    else:
        filas = "".join(_fila_lonja(c) for c in cots)
        # Comparativa interanual: solo con los productos vigentes que la tengan.
        comparativas = []
        for c in cots:
            d = c["plazas"].get("Valladolid") or next(iter(c["plazas"].values()), None)
            if not d or not d["vigente"] or not d["vs_hace_un_ano"]:
                continue
            v = d["vs_hace_un_ano"]
            # Concordancia: el artículo, el verbo y la terminación del adjetivo
            # vienen con el producto (ver PRODUCTOS en scrapers/lonja.py).
            adj = ("car" if v["sube"] else "barat") + c.get("adj", "o")
            comparativas.append(
                f'<li>{E(c.get("art", "el").capitalize())} '
                f'<strong>{E(c["nombre"].lower())}</strong> {E(c.get("verbo", "está"))} un '
                f'{dec(abs(v["porcentaje"]))}% más {adj} que hace un año '
                f'({"+" if v["sube"] else ""}{v["euros"]:.0f} €/t)</li>'
            )
        comp_html = ""
        if comparativas:
            comp_html = f"""<h2 class="tc-blog-subtitulo">Comparado con hace un año</h2>
  <ul class="tc-links-list">{''.join(comparativas)}</ul>"""
        cuerpo = f"""<div style="overflow-x:auto;">
  <table class="tc-tabla-lonja" style="width:100%; border-collapse:collapse;">
    <thead><tr><th style="text-align:left;">Producto</th><th style="text-align:left;">Valladolid</th><th style="text-align:left;">Palencia</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>
  </div>
  <p class="tc-item-meta">Precio pagado a la salida del almacén del agricultor, sin transporte,
  subvenciones ni impuestos indirectos. La flecha compara con la sesión anterior.</p>
  {comp_html}"""

    fecha = _fecha_lonja(cots)
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-verde-regadio);">Campo y huerta</span>
  <h1>El campo: precios y agua</h1>
  <p class="tc-articulo-entradilla">Cómo va la campaña en Tierra de Campos: lo que se paga por el
  cereal en la Lonja de Valladolid y Palencia{f', sesión del {E(fecha)}' if fecha else ''}, y cuánta
  agua queda en los embalses que riegan la comarca.</p>
  <h2 class="tc-blog-subtitulo">Precios del cereal</h2>
  {cuerpo}
  <p class="tc-item-meta" style="margin-top:12px;">Fuente:
  <a href="https://lonjavalladolidpalencia.com/cereales/" target="_blank" rel="noopener">Lonja de Valladolid y Palencia</a>.
  Los precios son orientativos y no sustituyen a la cotización oficial de cada sesión.</p>
  {bloque_embalses(emb)}
  <p class="tc-item-meta" style="margin-top:18px;"><a href="index.html">← Volver a portada</a></p>
</div></article>"""
    return shell("El campo: precios y agua — El Terracampino", body, depth=0,
                 desc="Precios del cereal en la Lonja de Valladolid y Palencia y situación de los "
                      "embalses que riegan Tierra de Campos.")


def render_leyendas(built: list[dict]) -> str:
    """Recopilatorio de todas las leyendas e historias populares (sitegen/contenido.py:LEYENDAS),
    hasta ahora escondidas dentro de la barra lateral de cada ficha de municipio —
    sin un sitio propio, nadie que no visitara pueblo a pueblo las encontraba."""
    nombre_por_slug = {m["slug"]: m["name"] for m in built}
    tarjetas = "".join(f"""<article class="tc-card" style="margin-bottom:var(--tc-space-3);">
      <span class="tc-item-meta">{E(nombre_por_slug.get(slug, slug))}</span>
      <h2 class="tc-blog-subtitulo" style="margin-top:4px;">{E(l['titulo'])}</h2>
      <p class="tc-articulo-parrafo">{E(l['texto'])}</p>
      <p class="tc-item-meta">Fuente: {E(l['fuente'])}
      · <a href="municipio/{E(slug)}.html">Ver la ficha de {E(nombre_por_slug.get(slug, slug))} →</a></p>
    </article>""" for slug, l in LEYENDAS.items() if slug in nombre_por_slug)
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-tinta-tierra);">La comarca</span>
  <h1>Leyendas e historias populares de Tierra de Campos</h1>
  <p class="tc-articulo-entradilla">Cuentos de cautivos y milagros, torres que caen, indianos que vuelven a
  probar a los suyos. Solo se cuentan aquí las leyendas que se pueden rastrear a una fuente real —
  tradición oral recogida por turismo oficial, crónicas o estudios locales — nunca inventadas para rellenar.</p>
  {tarjetas}
  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>"""
    return shell("Leyendas e historias populares — El Terracampino", body, depth=0,
                 desc="Leyendas y tradiciones documentadas de los pueblos de Tierra de Campos.")


# Una esquela se considera "reciente" (con el funeral aún próximo o recién
# pasado) durante estos días; después pasa al archivo "In memoriam".
DIAS_ESQUELA_RECIENTE = 30


def _fecha_esquela(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return fecha_larga(date.fromisoformat(iso[:10]))
    except ValueError:
        return ""


def _tarjeta_esquela(e: dict, *, con_pueblo: str = "", depth: int = 1) -> str:
    """Una esquela, siempre sobria. `con_pueblo` añade el nombre del pueblo
    (para la página comarcal); `depth` ajusta la ruta de la foto."""
    up = "../" * depth
    foto = ""
    if e.get("archivo"):
        foto = (f'<img class="tc-esquela-foto" src="{up}assets/esquelas/{E(e["archivo"])}" '
                f'alt="{E(e["nombre"])}" loading="lazy">')
    linea_pueblo = f'<span class="tc-item-meta">{E(con_pueblo)}</span>' if con_pueblo else ""
    edad = f", {E(str(e['edad']))} años" if e.get("edad") else ""
    fall = _fecha_esquela(e.get("fecha_fallecimiento"))
    fall_html = f'<p class="tc-esquela-fecha">Falleció el {E(fall)}</p>' if fall else ""
    funeral = f'<p class="tc-esquela-funeral">{E(e["funeral"])}</p>' if e.get("funeral") else ""
    texto = f'<p class="tc-esquela-texto">{E(e["texto"])}</p>' if e.get("texto") else ""
    return f"""<article class="tc-esquela">
    {foto}
    <div class="tc-esquela-cuerpo">
      {linea_pueblo}
      <h3 class="tc-esquela-nombre">{E(e['nombre'])}{edad}</h3>
      {fall_html}
      {funeral}
      {texto}
    </div>
  </article>"""


def _particion_esquelas(esquelas: list[dict], hoy: date) -> tuple[list[dict], list[dict]]:
    """Separa (recientes, in_memoriam) por la fecha de referencia de cada una."""
    recientes, memoriam = [], []
    for e in esquelas:
        ref = e.get("_fecha_orden") or ""
        es_reciente = False
        try:
            es_reciente = (hoy - date.fromisoformat(ref[:10])).days <= DIAS_ESQUELA_RECIENTE
        except ValueError:
            pass
        (recientes if es_reciente else memoriam).append(e)
    return recientes, memoriam


def bloque_esquelas_municipio(esquelas: list[dict], hoy: date) -> str:
    """Sección de esquelas dentro de la ficha de un pueblo. Sobria, sin foto de
    portada llamativa, sin publicidad. Recientes arriba; el resto, en un archivo
    'In memoriam' plegado."""
    if not esquelas:
        return ""
    recientes, memoriam = _particion_esquelas(esquelas, hoy)
    partes = ['<div class="tc-card tc-esquelas"><h3>Esquelas</h3>']
    if recientes:
        partes.append("".join(_tarjeta_esquela(e, depth=1) for e in recientes))
    if memoriam:
        items = "".join(
            f'<li>{E(e["nombre"])}'
            + (f' <span class="tc-item-meta">· {E(_fecha_esquela(e.get("fecha_fallecimiento")))}</span>'
               if _fecha_esquela(e.get("fecha_fallecimiento")) else "")
            + "</li>"
            for e in memoriam
        )
        partes.append(f"""<details class="tc-memoriam"><summary>In memoriam · quienes nos dejaron</summary>
      <ul class="tc-links-list">{items}</ul></details>""")
    partes.append(
        '<p class="tc-item-meta">¿Quieres publicar el fallecimiento de un familiar? '
        '<a href="../esquela.html">Mándanos el aviso</a>. Cada esquela se revisa antes de publicarse.</p>'
    )
    partes.append("</div>")
    return "".join(partes)


def render_esquelas_pagina(por_slug: dict[str, list[dict]], nombre_por_slug: dict[str, str],
                            hoy: date) -> str:
    """Página comarcal de esquelas: las recientes de todos los pueblos juntas
    (lo que busca la diáspora), y el acceso al archivo de cada pueblo."""
    todas = []
    for slug, lista in por_slug.items():
        for e in lista:
            e = dict(e)
            e["_pueblo_nombre"] = nombre_por_slug.get(slug, slug)
            todas.append(e)
    recientes, memoriam = _particion_esquelas(
        sorted(todas, key=lambda x: x.get("_fecha_orden", ""), reverse=True), hoy)

    if recientes:
        cuerpo = "".join(_tarjeta_esquela(e, con_pueblo=e["_pueblo_nombre"], depth=0) for e in recientes)
    else:
        cuerpo = ('<p class="tc-pieza-cuerpo">No hay esquelas recientes. Cuando una familia nos '
                  'haga llegar un aviso y lo revisemos, aparecerá aquí y en la ficha de su pueblo.</p>')
    memoriam_html = ""
    if memoriam:
        items = "".join(
            f'<li>{E(e["nombre"])} <span class="tc-item-meta">· {E(e["_pueblo_nombre"])}'
            + (f' · {E(_fecha_esquela(e.get("fecha_fallecimiento")))}'
               if _fecha_esquela(e.get("fecha_fallecimiento")) else "")
            + "</span></li>"
            for e in memoriam
        )
        memoriam_html = f"""<h2 class="tc-blog-subtitulo">In memoriam</h2>
  <p class="tc-item-meta">Quienes nos dejaron en los pueblos de la comarca.</p>
  <ul class="tc-links-list">{items}</ul>"""

    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-tinta-tierra);">La comarca</span>
  <h1>Esquelas</h1>
  <p class="tc-articulo-entradilla">Los fallecimientos recientes en los pueblos de Tierra de Campos.
  Cada esquela la envía un familiar o allegado y se revisa antes de publicarse; no recogemos avisos de
  otras webs. Para quien vive lejos y quiere estar al tanto de su pueblo.</p>
  {cuerpo}
  {memoriam_html}
  <div class="tc-card" style="margin-top:var(--tc-space-3);">
    <h3 style="margin-top:0;">Publicar una esquela</h3>
    <p class="tc-pieza-cuerpo">Si quieres que publiquemos el fallecimiento de un familiar, con la
    información del funeral, puedes enviárnoslo. Es gratis y se revisa antes de aparecer.</p>
    <p><a class="tc-button" href="esquela.html">Enviar un aviso</a></p>
  </div>
  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>"""
    return shell("Esquelas — El Terracampino", body, depth=0,
                 desc="Esquelas y fallecimientos recientes en los pueblos de Tierra de Campos.")


def render_esquela_form(built: list[dict]) -> str:
    """Formulario para que una familia envíe una esquela (web/api/esquela.js).
    Nada se publica al enviarlo: entra en una cola de revisión humana."""
    opciones = "".join(f'<option value="{E(m["slug"])}">{E(m["name"])}</option>' for m in built)
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-tinta-tierra);">Esquelas</span>
  <h1>Enviar una esquela</h1>
  <p class="tc-articulo-entradilla">Si ha fallecido un familiar o un allegado y quieres que lo
  publiquemos, rellena estos datos. Lo revisamos antes de publicarlo —puede que te llamemos para
  confirmarlo— y no cuesta nada. Solo publicamos avisos que nos llegan de la familia o allegados.</p>
  <div class="tc-card">
    <form id="tc-esquela-form">
      <p style="margin:0 0 6px;"><label style="font-weight:700; font-size:.9rem;">Nombre de la persona fallecida *</label></p>
      <input id="es-nombre" name="nombre" class="tc-input" required maxlength="120" style="width:100%; box-sizing:border-box;">
      <p style="margin:12px 0 6px;"><label for="es-pueblo" style="font-weight:700; font-size:.9rem;">Pueblo *</label></p>
      <select id="es-pueblo" name="pueblo" class="tc-muni-select" required><option value="">Elige el pueblo…</option>{opciones}<option value="_otro">Otro pueblo de la comarca…</option></select>
      <input id="es-pueblo-otro" class="tc-input" placeholder="Escribe el nombre del pueblo" maxlength="80" hidden style="width:100%; box-sizing:border-box; margin-top:8px;" aria-label="Nombre del pueblo">
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Edad (opcional)</label></p>
      <input id="es-edad" name="edad" class="tc-input" inputmode="numeric" maxlength="3" style="width:120px;">
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Fecha del fallecimiento (opcional)</label></p>
      <input id="es-fecha" name="fecha_fallecimiento" class="tc-input" type="date" style="width:200px;">
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Funeral: día, hora y lugar (opcional)</label></p>
      <input id="es-funeral" name="funeral" class="tc-input" maxlength="200" placeholder="p. ej. Misa el jueves 12 a las 17:00 en la iglesia de Santa María" style="width:100%; box-sizing:border-box;">
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Unas palabras (opcional)</label></p>
      <textarea id="es-texto" name="texto" class="tc-input" rows="3" maxlength="1000" style="width:100%; box-sizing:border-box; font-family:inherit; resize:vertical;"></textarea>
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Foto (opcional)</label></p>
      <input id="es-foto" type="file" accept="image/*">
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Tu contacto (teléfono o correo) *</label></p>
      <input id="es-contacto" name="contacto" class="tc-input" required maxlength="200" style="width:100%; box-sizing:border-box;">
      <p class="tc-item-meta">Tu contacto es solo para que podamos verificar el aviso contigo. No se publica.</p>
      <input type="text" name="web" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px;" aria-hidden="true">
      <p style="margin:16px 0 0;"><button class="tc-button" type="submit">Enviar</button></p>
      <p class="tc-item-meta" style="margin:10px 0 0;">Al enviarlo aceptas que tratemos estos datos para revisar y publicar la esquela. Cómo lo hacemos y cómo pedir que se borren, en el <a href="aviso-legal.html#privacidad">aviso legal</a>.</p>
      <p id="es-resultado" class="tc-item-meta" style="margin-top:10px;"></p>
    </form>
  </div>
  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>
<script>
(function() {{
  var form = document.getElementById("tc-esquela-form");
  var fileInput = document.getElementById("es-foto");

  // Reduce la foto en el propio navegador antes de enviarla (máx. 1000px de
  // lado, JPEG), para no mandar megas ni depender de la conexión del pueblo.
  function leerFoto() {{
    return new Promise(function(resolve) {{
      var f = fileInput.files && fileInput.files[0];
      if (!f) return resolve(null);
      var img = new Image();
      img.onload = function() {{
        var max = 1000, w = img.width, h = img.height;
        if (w > max || h > max) {{ var r = Math.min(max/w, max/h); w = Math.round(w*r); h = Math.round(h*r); }}
        var c = document.createElement("canvas"); c.width = w; c.height = h;
        c.getContext("2d").drawImage(img, 0, 0, w, h);
        resolve(c.toDataURL("image/jpeg", 0.82));
      }};
      img.onerror = function() {{ resolve(null); }};
      var fr = new FileReader();
      fr.onload = function(e) {{ img.src = e.target.result; }};
      fr.readAsDataURL(f);
    }});
  }}

  form.addEventListener("submit", function(e) {{
    e.preventDefault();
    var res = document.getElementById("es-resultado");
    var btn = form.querySelector("button");
    btn.disabled = true; btn.textContent = "Enviando…";
    leerFoto().then(function(fotoB64) {{
      return fetch("api/esquela", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          nombre: document.getElementById("es-nombre").value,
          pueblo: puebloElegido("es-pueblo", "es-pueblo-otro"),
          edad: document.getElementById("es-edad").value,
          fecha_fallecimiento: document.getElementById("es-fecha").value,
          funeral: document.getElementById("es-funeral").value,
          texto: document.getElementById("es-texto").value,
          contacto: document.getElementById("es-contacto").value,
          foto_base64: fotoB64,
          web: form.querySelector('input[name="web"]').value
        }})
      }});
    }}).then(function(r) {{ return r.json().then(function(d) {{ return {{ ok: r.ok, body: d }}; }}); }})
      .then(function(out) {{
        if (out.ok) {{
          form.style.display = "none";
          res.textContent = "Recibido. Gracias — lo revisamos y, si hace falta, te llamamos antes de publicarlo. Te acompañamos en el sentimiento.";
        }} else {{
          res.textContent = out.body.error || "No se pudo enviar. Inténtalo más tarde.";
          btn.disabled = false; btn.textContent = "Enviar";
        }}
      }})
      .catch(function() {{
        res.textContent = "No se pudo enviar. Inténtalo más tarde.";
        btn.disabled = false; btn.textContent = "Enviar";
      }});
  }});
}})();
</script>"""
    return shell("Enviar una esquela — El Terracampino", body, depth=0,
                 desc="Envía el aviso de fallecimiento de un familiar para publicarlo en El Terracampino.")


def _tarjeta_archivo(f: dict, *, con_pueblo: str = "", depth: int = 1) -> str:
    up = "../" * depth
    anio = f'<span class="tc-archivo-anio">{E(str(f["anio"]))}</span>' if f.get("anio") else ""
    pueblo = f'<span class="tc-item-meta">{E(con_pueblo)}</span>' if con_pueblo else ""
    desc = f'<p class="tc-archivo-desc">{E(f["descripcion"])}</p>' if f.get("descripcion") else ""
    credito = (f'<p class="tc-item-meta">Aportada por {E(f["autor"])}</p>'
               if f.get("autor") else '<p class="tc-item-meta">Aportada por un vecino</p>')
    return f"""<figure class="tc-archivo-foto">
    <img src="{up}assets/archivo/{E(f['archivo'])}" alt="{E(f.get('descripcion') or 'Foto antigua')}" loading="lazy">
    <figcaption>{anio}{pueblo}{desc}{credito}</figcaption>
  </figure>"""


def bloque_archivo_municipio(fotos: list[dict]) -> str:
    """Sección 'Fotos de antes' dentro de la ficha de un pueblo."""
    if not fotos:
        return ""
    tarjetas = "".join(_tarjeta_archivo(f, depth=1) for f in fotos)
    return f"""<div class="tc-card"><h3>Fotos de antes</h3>
    <div class="tc-archivo-grid">{tarjetas}</div>
    <p class="tc-item-meta">¿Tienes fotos antiguas del pueblo en un cajón? <a href="../archivo-enviar.html">Compártelas
    con el archivo</a>. ¿Reconoces a alguien o sabes de cuándo es una foto?
    <a href="https://wa.me/34695645395" target="_blank" rel="noopener">Cuéntanoslo por WhatsApp</a>.</p></div>"""


def render_archivo_pagina(por_slug: dict[str, list[dict]], nombre_por_slug: dict[str, str]) -> str:
    """Página comarcal del archivo fotográfico: todas las fotos, por pueblo."""
    bloques = []
    for slug in sorted(por_slug, key=lambda s: nombre_por_slug.get(s, s)):
        fotos = por_slug[slug]
        if not fotos:
            continue
        tarjetas = "".join(_tarjeta_archivo(f, depth=0) for f in fotos)
        bloques.append(f'<h2 class="tc-blog-subtitulo">{E(nombre_por_slug.get(slug, slug))}</h2>'
                       f'<div class="tc-archivo-grid">{tarjetas}</div>')
    if bloques:
        cuerpo = "".join(bloques)
    else:
        cuerpo = ('<p class="tc-pieza-cuerpo">El archivo todavía está vacío. Si tienes fotos antiguas de '
                  'tu pueblo, eres de los primeros: compártelas y empezamos a llenarlo.</p>')
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-tinta-tierra);">La comarca</span>
  <h1>El archivo: fotos de antes</h1>
  <p class="tc-articulo-entradilla">La plaza en los años sesenta, una matanza, la escuela llena de niños, las
  fiestas de hace medio siglo. Fotos antiguas de los pueblos de Tierra de Campos que traen los propios vecinos.
  Si tienes alguna en un cajón, aquí tiene sitio.</p>
  <p><a class="tc-button" href="archivo-enviar.html">Compartir una foto antigua</a></p>
  {cuerpo}
  <p class="tc-item-meta" style="margin-top:18px;">¿Reconoces a alguien en una foto, o sabes de qué año es?
  <a href="https://wa.me/34695645395" target="_blank" rel="noopener">Cuéntanoslo por WhatsApp</a> y lo añadimos.</p>
  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>"""
    return shell("El archivo: fotos de antes — El Terracampino", body, depth=0,
                 desc="Archivo de fotos antiguas de los pueblos de Tierra de Campos, aportadas por los vecinos.")


def render_archivo_form(built: list[dict]) -> str:
    """Formulario para aportar una foto antigua (web/api/archivo.js)."""
    opciones = "".join(f'<option value="{E(m["slug"])}">{E(m["name"])}</option>' for m in built)
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-tinta-tierra);">El archivo</span>
  <h1>Compartir una foto antigua</h1>
  <p class="tc-articulo-entradilla">Escanéala o hazle una foto con el móvil y súbela. La revisamos antes de
  publicarla y aparecerá en el archivo de tu pueblo, con el año y tu nombre como quien la aporta. Solo sube
  fotos que sean tuyas o que puedas compartir.</p>
  <div class="tc-card">
    <form id="tc-archivo-form">
      <p style="margin:0 0 6px;"><label style="font-weight:700; font-size:.9rem;">Pueblo *</label></p>
      <select id="ar-pueblo" name="pueblo" class="tc-muni-select" required><option value="">Elige el pueblo…</option>{opciones}<option value="_otro">Otro pueblo de la comarca…</option></select>
      <input id="ar-pueblo-otro" class="tc-input" placeholder="Escribe el nombre del pueblo" maxlength="80" hidden style="width:100%; box-sizing:border-box; margin-top:8px;" aria-label="Nombre del pueblo">
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Año aproximado</label></p>
      <input id="ar-anio" name="anio" class="tc-input" maxlength="30" placeholder="p. ej. 1965, o 'años 70'" style="width:260px;">
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">¿Qué es o quién sale?</label></p>
      <textarea id="ar-desc" name="descripcion" class="tc-input" rows="3" maxlength="600" style="width:100%; box-sizing:border-box; font-family:inherit; resize:vertical;"></textarea>
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Tu nombre (para el crédito)</label></p>
      <input id="ar-autor" name="autor" class="tc-input" maxlength="120" placeholder="Cómo quieres que figure: 'Aportada por…'" style="width:100%; box-sizing:border-box;">
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">La foto *</label></p>
      <input id="ar-foto" type="file" accept="image/*" required>
      <p style="margin:12px 0 6px;"><label style="font-weight:700; font-size:.9rem;">Tu contacto (opcional, no se publica)</label></p>
      <input id="ar-contacto" name="contacto" class="tc-input" maxlength="200" style="width:100%; box-sizing:border-box;">
      <input type="text" name="web" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px;" aria-hidden="true">
      <p style="margin:16px 0 0;"><button class="tc-button" type="submit">Enviar la foto</button></p>
      <p class="tc-item-meta" style="margin:10px 0 0;">Al enviarlo aceptas que tratemos estos datos para revisar y publicar la foto con tu nombre como autor. Cómo lo hacemos y cómo pedir que se borren, en el <a href="aviso-legal.html#privacidad">aviso legal</a>.</p>
      <p id="ar-resultado" class="tc-item-meta" style="margin-top:10px;"></p>
    </form>
  </div>
  <p class="tc-item-meta"><a href="archivo.html">← Ver el archivo</a></p>
</div></article>
<script>
(function() {{
  var form = document.getElementById("tc-archivo-form");
  var fileInput = document.getElementById("ar-foto");
  // Reduce la foto en el navegador (máx 1600px: es archivo, se quiere resolución
  // pero sin mandar 8 MB desde el móvil del pueblo).
  function leerFoto() {{
    return new Promise(function(resolve, reject) {{
      var f = fileInput.files && fileInput.files[0];
      if (!f) return reject();
      var img = new Image();
      img.onload = function() {{
        var max = 1600, w = img.width, h = img.height;
        if (w > max || h > max) {{ var r = Math.min(max/w, max/h); w = Math.round(w*r); h = Math.round(h*r); }}
        var c = document.createElement("canvas"); c.width = w; c.height = h;
        c.getContext("2d").drawImage(img, 0, 0, w, h);
        resolve(c.toDataURL("image/jpeg", 0.85));
      }};
      img.onerror = reject;
      var fr = new FileReader();
      fr.onload = function(e) {{ img.src = e.target.result; }};
      fr.readAsDataURL(f);
    }});
  }}
  form.addEventListener("submit", function(e) {{
    e.preventDefault();
    var res = document.getElementById("ar-resultado");
    var btn = form.querySelector("button");
    btn.disabled = true; btn.textContent = "Enviando…";
    leerFoto().then(function(fotoB64) {{
      return fetch("api/archivo", {{
        method: "POST", headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          pueblo: puebloElegido("ar-pueblo", "ar-pueblo-otro"),
          anio: document.getElementById("ar-anio").value,
          descripcion: document.getElementById("ar-desc").value,
          autor: document.getElementById("ar-autor").value,
          contacto: document.getElementById("ar-contacto").value,
          foto_base64: fotoB64,
          web: form.querySelector('input[name="web"]').value
        }})
      }});
    }}).then(function(r) {{ return r.json().then(function(d) {{ return {{ ok: r.ok, body: d }}; }}); }})
      .then(function(out) {{
        if (out.ok) {{ form.style.display = "none"; res.textContent = "Recibida. Gracias — la revisamos y la añadimos al archivo del pueblo."; }}
        else {{ res.textContent = out.body.error || "No se pudo enviar."; btn.disabled = false; btn.textContent = "Enviar la foto"; }}
      }})
      .catch(function() {{ res.textContent = "Elige una foto y vuelve a intentarlo."; btn.disabled = false; btn.textContent = "Enviar la foto"; }});
  }});
}})();
</script>"""
    return shell("Compartir una foto antigua — El Terracampino", body, depth=0,
                 desc="Comparte fotos antiguas de tu pueblo con el archivo fotográfico de El Terracampino.")


def render_gente(built: list[dict], blog_articulos: list[dict]) -> str:
    """Serie 'Gente de Campos': perfiles de personas reales de la comarca.

    Los perfiles NO se generan solos: son de personas reales, con sus palabras
    reales, y se escriben a partir de una entrevista o unas notas de verdad
    (ver docs/ideas-mundo.md). Esta página presenta la serie, lista los perfiles
    ya publicados (artículos de blog con tema 'gente') e invita a proponer
    candidatos. Mientras no haya perfiles reales, no se inventa ninguno."""
    perfiles = [a for a in blog_articulos if a.get("tema") == "gente"]
    if perfiles:
        tarjetas = "".join(f'''<a class="tc-blog-tarjeta" href="blog/{E(a["slug"])}.html">
      {f'<img src="assets/blog/{E(a["slug"])}.jpg" alt="" loading="lazy">' if a.get("tiene_imagen") else ""}
      <span class="tc-news-titular">{E(a["titular"])}</span>
      <span class="tc-news-entradilla">{E(a["entradilla"])}</span>
    </a>''' for a in perfiles)
        lista = f'<div class="tc-blog-grid">{tarjetas}</div>'
    else:
        lista = ('<p class="tc-pieza-cuerpo">Todavía no hay perfiles publicados. El primero está por llegar: '
                 'si conoces a alguien de la comarca cuya historia merezca contarse, dínoslo.</p>')
    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-tinta-tierra);">La comarca</span>
  <h1>Gente de Campos</h1>
  <p class="tc-articulo-entradilla">El último pastor, la panadera de toda la vida, el que se fue a la ciudad y
  volvió, la maestra que conoció a varias generaciones. Retratos de personas de carne y hueso de Tierra de
  Campos, contados con sus propias palabras.</p>
  {lista}
  <div class="tc-card" style="margin-top:var(--tc-space-3);">
    <h3 style="margin-top:0;">¿Conoces a alguien que merezca un reportaje?</h3>
    <p class="tc-pieza-cuerpo">Un oficio que se pierde, una vida que da para una historia, alguien a quien el
    pueblo entero conoce. Propónnoslo y vamos a conocerlo.</p>
    <p><a class="tc-button" href="https://wa.me/34695645395" target="_blank" rel="noopener">Proponer por WhatsApp</a></p>
  </div>
  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>"""
    return shell("Gente de Campos — El Terracampino", body, depth=0,
                 desc="Retratos de personas de los pueblos de Tierra de Campos, contados con sus propias palabras.")


def escribir_resumen_dia(built: list[dict], feed: list[dict], blog_articulos: list[dict],
                          avisos: list[dict], hoy: date) -> None:
    """Deja en data/boletin_hoy.json lo publicable del día, para que
    scripts/boletin_telegram.py componga el boletín sin repetir el trabajo del
    build (scrapers + IA). Solo escribe datos: no envía nada.

    Se guardan los titulares y entradillas YA redactados y revisados por la
    cadena de redactor.py — el boletín no vuelve a pasar nada por la IA, así que
    no puede introducir texto nuevo ni inventar."""
    base = "https://elterracampino.es"
    r = resumen_tiempo(built)

    # Una misma resolución del BOCyL puede afectar a varios municipios y aparece
    # UNA VEZ POR CADA UNO en el feed. Sin agrupar, el boletín repetía cinco
    # veces seguidas el anuncio de la línea de 132 kV: de 8 "noticias", 3
    # distintas.
    por_hash: dict[str, dict] = {}
    for d in feed:
        e = por_hash.get(d["hash"])
        if e:
            if d.get("municipality_name") and d["municipality_name"] not in e["municipios"]:
                e["municipios"].append(d["municipality_name"])
        else:
            por_hash[d["hash"]] = {"doc": d,
                                   "municipios": [d["municipality_name"]] if d.get("municipality_name") else []}

    # Lo NUEVO primero. Antes esto se ordenaba por relevancia, que puntúa por
    # palabras clave y NO mira la fecha: un anuncio jugoso de hace semanas ganaba
    # siempre, así que el boletín mandaba día tras día las mismas noticias en vez
    # de las últimas. La relevancia queda solo para desempatar dentro del día.
    ordenadas = sorted(por_hash.values(),
                       key=lambda e: (e["doc"].get("published_at") or "", relevancia(e["doc"])),
                       reverse=True)
    noticias = []
    for e in ordenadas[:8]:
        d = e["doc"]
        red = redactar(d)
        munis = e["municipios"]
        if len(munis) > 2:
            donde = f"{len(munis)} pueblos de la comarca"
        else:
            donde = " y ".join(munis)
        noticias.append({
            "hash": d["hash"],
            "titular": red["titular"],
            "municipio": donde,
            "fecha": d.get("published_at", ""),
            "fuente": fuente_label(d),
            "url": f"{base}/{articulo_path(d)}" if red.get("cuerpo") else url_segura(d.get("url_original", "")),
        })
    datos = {
        "fecha": hoy.isoformat(),
        "tiempo": r,
        "avisos": [{"nivel": a.get("nivel"), "zona": a.get("zona"),
                    "fenomeno": a.get("fenomeno", "")} for a in avisos],
        "noticias": noticias,
        "investigaciones": [
            {"titular": a["titular"], "url": f"{base}/blog/{a['slug']}.html", "fecha": a.get("fecha", "")}
            for a in blog_articulos[:3]
        ],
    }
    ruta = ROOT / "data" / "boletin_hoy.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  resumen del día para el boletín: {len(noticias)} noticias, "
          f"{len(datos['avisos'])} avisos")


def render_acompanar() -> str:
    """Sección "Acompañar" (Fase 1) — servicio público contra la soledad no
    deseada de los mayores. Ver docs/acompanar.md.

    LÍNEA ROJA: esta sección NUNCA publica que una persona concreta vive sola
    ni datos personales de nadie. Solo recursos verificados a los que llamar,
    dónde encontrarse, y cómo puede ayudar quien tiene cerca a alguien solo.
    Todos los teléfonos están verificados (Cruz Roja, Teléfono de la Esperanza,
    112) — antes de tocar un número, re-verificar."""
    # Tarjetas de "a quién llamar": teléfonos verificados. tel: para que en el
    # móvil se pueda llamar con un toque.
    recursos = [
        {
            "nombre": "Emergencias",
            "tel": "112", "tel_href": "112",
            "coste": "24 horas · todos los días",
            "desc": "Si hay peligro para la vida o la salud, o una urgencia de cualquier tipo. No lo dudes.",
        },
        {
            "nombre": "Te Acompaña — Cruz Roja",
            "tel": "900 444 111", "tel_href": "900444111",
            "coste": "Gratuito · de lunes a viernes, de 10 a 18 h",
            "desc": "Para quien se siente solo. Escuchan, orientan y acompañan, sin prisa y sin que cueste nada.",
        },
        {
            "nombre": "Teléfono de la Esperanza",
            "tel": "717 003 717", "tel_href": "717003717",
            "coste": "Gratuito y anónimo · 24 horas, todos los días",
            "desc": "Cuando uno necesita hablar y que le escuchen, a cualquier hora del día o de la noche.",
        },
    ]
    tarjetas = "".join(f"""<div class="tc-card tc-acompanar-tarjeta">
    <h3 style="margin-top:0;">{E(r['nombre'])}</h3>
    <p class="tc-acompanar-tel"><a href="tel:{r['tel_href']}">{E(r['tel'])}</a></p>
    <p class="tc-acompanar-coste">{E(r['coste'])}</p>
    <p class="tc-pieza-cuerpo">{E(r['desc'])}</p>
  </div>""" for r in recursos)

    body = f"""<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-verde-regadio);">Acompañar</span>
  <h1>No estás solo. No estás sola.</h1>
  <p class="tc-articulo-entradilla">En nuestros pueblos hay mucha gente mayor que vive sola. La soledad no
  se cuenta en el periódico, pero sí podemos poner a mano los teléfonos donde escuchan, recordar dónde
  encontrarse con otros, y pedirte —si tienes cerca a alguien solo— que le eches una mano. Se hace entre todos.</p>

  <h2 class="tc-blog-subtitulo">¿A quién llamar?</h2>
  <p class="tc-pieza-cuerpo">Teléfonos de verdad, gratuitos, donde hay alguien al otro lado. Llamar no es molestar.</p>
  <div class="tc-acompanar-grid">{tarjetas}</div>

  <h2 class="tc-blog-subtitulo">La ayuda pública, tu ayuntamiento</h2>
  <p class="tc-pieza-cuerpo">La puerta de entrada a la teleasistencia, la ayuda a domicilio y los programas
  contra la soledad (como <strong>«Siempre Acompañados»</strong> de la Junta de Castilla y León) son los
  <strong>Servicios Sociales</strong> de tu zona. Pregunta en tu ayuntamiento por el <strong>CEAS</strong> que
  te corresponde: te explican qué hay y cómo pedirlo. Es un derecho, no un favor.</p>

  <h2 class="tc-blog-subtitulo">¿Tienes cerca a alguien que pasa mucho tiempo solo?</h2>
  <p class="tc-pieza-cuerpo">Casi siempre, lo que más ayuda no es un servicio: es un vecino. Si conoces a
  alguien mayor que vive solo —un padre, una madre que se quedó, el vecino del final de la calle—:</p>
  <ul class="tc-links-list">
    <li>Llámale hoy, aunque sea un momento. Una llamada corta también acompaña.</li>
    <li>Pásate a verle, o dile a quién puede llamar si un día se encuentra mal.</li>
    <li>Si hay actividades en el pueblo (el hogar, una merienda, misa, el mercado), anímale a ir y, si puedes, llévale.</li>
    <li>Si ves que algo va mal —no come, está muy decaído, no sale—, avisa a los Servicios Sociales del ayuntamiento.</li>
  </ul>

  <h2 class="tc-blog-subtitulo">Dónde encontrarse</h2>
  <p class="tc-pieza-cuerpo">Queremos ir armando, pueblo a pueblo, la agenda de dónde y cuándo se junta la
  gente: el hogar del jubilado, las actividades de la Diputación, las meriendas, el mercado. Si en tu pueblo
  hay algo así y quieres que lo publiquemos para que nadie se quede sin enterarse,
  <a href="chivatazo.html">cuéntanoslo aquí</a>.</p>

  <div class="tc-card" style="margin-top:var(--tc-space-3);">
    <h3 style="margin-top:0;">Una hoja para colgar en el pueblo</h3>
    <p class="tc-pieza-cuerpo">No todo el mundo está en el móvil. Hemos preparado una hoja con estos teléfonos,
    en letra grande, para imprimir y colgar donde pueda verla quien lo necesite: la farmacia, el consultorio,
    el hogar del jubilado, la iglesia, el ayuntamiento.</p>
    <p><a class="tc-button" href="acompanar-hoja.html">Ver e imprimir la hoja</a></p>
  </div>

  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>"""
    return shell("Acompañar — El Terracampino", body, depth=0,
                 desc="Teléfonos y recursos contra la soledad de los mayores en Tierra de Campos: a quién llamar y cómo ayudar a quien tienes cerca.")


def render_acompanar_hoja() -> str:
    """Hoja A4 imprimible con los teléfonos, en letra grande, para colgar en
    farmacias, consultorios, hogares del jubilado, iglesias. Página autónoma
    (no usa shell): pensada para imprimirse limpia, no para navegar. Ver
    docs/acompanar.md. Los teléfonos son los mismos verificados de render_acompanar()."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Si te sientes solo, llama — El Terracampino</title>
<link rel="icon" href="/assets/favicon-32.png" type="image/png" sizes="32x32">
<style>
  :root { --verde:#5F7C52; --tinta:#131313; --terr:#A65F2A; }
  * { box-sizing:border-box; }
  body { font-family: Georgia,'PT Serif',serif; color:var(--tinta); background:#fff; margin:0; padding:2.5rem; line-height:1.35; }
  .hoja { max-width: 800px; margin:0 auto; }
  h1 { font-size: 2.6rem; line-height:1.15; margin:0 0 .3em; }
  .sub { font-size:1.35rem; margin:0 0 1.6rem; }
  .tel-bloque { border:3px solid var(--verde); border-radius:14px; padding:1.1rem 1.4rem; margin:0 0 1.1rem; }
  .tel-nombre { font-size:1.3rem; font-weight:bold; margin:0 0 .1em; }
  .tel-num { font-size:2.7rem; font-weight:bold; letter-spacing:.02em; margin:.1em 0; font-family:Arial,Helvetica,sans-serif; }
  .tel-cost { font-size:1.1rem; color:#444; margin:0; }
  .emerg { border-color:var(--terr); }
  .pie { margin-top:1.8rem; font-size:1.05rem; color:#333; border-top:1px solid #ccc; padding-top:1rem; }
  .pie strong { color:var(--verde); }
  .volver { font-family:Arial,sans-serif; font-size:.95rem; }
  @media print {
    body { padding:1.2cm; }
    .no-print { display:none; }
    .tel-bloque { break-inside:avoid; }
  }
</style>
</head>
<body>
<div class="hoja">
  <p class="no-print volver"><a href="acompanar.html">← Volver</a> ·
  <button type="button" onclick="window.print()" style="font:inherit; padding:6px 12px; min-height:44px; cursor:pointer;">Imprimir esta hoja</button>
  y cuélgala donde pueda verla quien la necesite.</p>
  <h1>¿Te sientes solo?<br>No estás solo.</h1>
  <p class="sub">Llamar es gratis. Al otro lado hay alguien que escucha.</p>

  <div class="tel-bloque">
    <p class="tel-nombre">Para hablar, cuando lo necesites — Teléfono de la Esperanza</p>
    <p class="tel-num">717 003 717</p>
    <p class="tel-cost">Gratuito y anónimo · Las 24 horas, todos los días</p>
  </div>

  <div class="tel-bloque">
    <p class="tel-nombre">Si te sientes solo — Te Acompaña, de Cruz Roja</p>
    <p class="tel-num">900 444 111</p>
    <p class="tel-cost">Gratuito · De lunes a viernes, de 10 a 18 horas</p>
  </div>

  <div class="tel-bloque emerg">
    <p class="tel-nombre">Emergencias (peligro o urgencia)</p>
    <p class="tel-num">112</p>
    <p class="tel-cost">Las 24 horas, todos los días</p>
  </div>

  <p class="pie">Y para la teleasistencia o la ayuda a domicilio, pregunta en tu <strong>ayuntamiento</strong>
  por los Servicios Sociales (CEAS) de tu zona.</p>
  <p class="pie" style="border:0;padding-top:.3rem;"><strong>El Terracampino</strong> · el periódico de los pueblos de Tierra de Campos · elterracampino.es</p>
</div>
</body>
</html>
"""


def render_aviso_legal() -> str:
    """Aviso legal / titularidad del medio (LSSI-CE art. 10). Deja constancia de
    quién es la propietaria del periódico y quién lo desarrolla y mantiene. No se
    publica ningún DNI personal: la propietaria figura por nombre (es lo que exige
    la ley para el titular) y la empresa de desarrollo con su CIF, que sí es un
    identificador público de sociedad."""
    body = """<article class="tc-wrap tc-articulo tc-blog-articulo"><div class="tc-articulo-ancho">
  <span class="tc-section-label" style="color:var(--tc-azul-bop);">Información legal</span>
  <h1>Aviso legal</h1>
  <p class="tc-articulo-entradilla">Quién es responsable de El Terracampino y quién lo ha construido, en cumplimiento del artículo 10 de la Ley 34/2002 de Servicios de la Sociedad de la Información (LSSI-CE).</p>

  <h2 class="tc-blog-subtitulo">Titularidad del medio</h2>
  <p class="tc-articulo-parrafo">El Terracampino (elterracampino.es) es un medio de comunicación digital propiedad de <strong>María Vega Blanco</strong>, responsable de su línea editorial y de los contenidos publicados.</p>

  <h2 class="tc-blog-subtitulo">Desarrollo y mantenimiento técnico</h2>
  <p class="tc-articulo-parrafo">El diseño, desarrollo y mantenimiento técnico del sitio corre a cargo de <strong>Naraya Services Cloud Consulting, S.L.</strong>, con los siguientes datos identificativos:</p>
  <ul class="tc-links-list">
    <li>Denominación social: Naraya Services Cloud Consulting, S.L.</li>
    <li>NIF: B-42792101</li>
    <li>Domicilio: Calle Real 212 B, Villaobispo de las Regueras, 24193 Villaquilambre (León), España.</li>
    <li>Actividad (CNAE 7020): otras actividades de consultoría de gestión empresarial.</li>
  </ul>

  <h2 class="tc-blog-subtitulo">Contacto</h2>
  <p class="tc-articulo-parrafo">Para cualquier consulta, corrección o solicitud relacionada con los contenidos puedes escribirnos por WhatsApp al <a href="https://wa.me/34695645395" target="_blank" rel="noopener">695 645 395</a> o a través del <a href="chivatazo.html">formulario de contacto</a>.</p>

  <h2 class="tc-blog-subtitulo" id="privacidad">Privacidad: qué datos recogemos y para qué</h2>
  <p class="tc-articulo-parrafo">Responsable del tratamiento: <strong>María Vega Blanco</strong> (ver arriba).
  Solo pedimos datos cuando tú decides enviarlos, y siempre para lo mínimo:</p>
  <ul class="tc-links-list">
    <li><strong>Newsletter</strong>: tu correo, para mandarte el boletín. Base legal: tu consentimiento, que
    confirmas pinchando el enlace del primer correo. Se gestiona con MailerLite. Puedes darte de baja desde
    cualquier envío, y con eso se borra.</li>
    <li><strong>Esquelas</strong>: el nombre de la persona fallecida y los datos del aviso, más un teléfono o
    correo de contacto que usamos <em>solo</em> para verificar contigo que el aviso es real. El contacto no se
    publica nunca. Base legal: tu consentimiento al enviarlo.</li>
    <li><strong>Archivo de fotos</strong>: la foto, su descripción y el nombre de quien la aporta, que sí se
    publica como crédito de autoría (por eso te lo pedimos).</li>
    <li><strong>Chivatazos</strong>: solo el texto y el pueblo. No pedimos identidad.</li>
    <li><strong>Visitas</strong>: una medición agregada de páginas vistas (Vercel Analytics), sin perfiles ni
    seguimiento entre webs.</li>
  </ul>
  <p class="tc-articulo-parrafo">Lo que nos envías se guarda en almacenamiento privado (Supabase) y no se
  cede a terceros ni se usa con fines comerciales. Puedes pedirnos acceder, corregir o borrar tus datos —o
  retirar tu consentimiento— escribiendo por
  <a href="https://wa.me/34695645395" target="_blank" rel="noopener">WhatsApp al 695 645 395</a>;
  atendemos la petición sin más trámite. Si no quedas conforme, puedes reclamar ante la Agencia Española de
  Protección de Datos (aepd.es).</p>

  <h2 class="tc-blog-subtitulo">Sobre los contenidos</h2>
  <p class="tc-articulo-parrafo">Este medio resume y enlaza información pública procedente de fuentes oficiales y abiertas (boletines oficiales, portales de transparencia, organismos públicos). Los resúmenes no sustituyen al documento original: ante cualquier trámite, plazo, ayuda o acuerdo municipal, consulta siempre la fuente oficial enlazada. Si detectas un error, dínoslo y lo corregimos.</p>

  <p class="tc-item-meta"><a href="index.html">← Volver a portada</a></p>
</div></article>"""
    return shell("Aviso legal — El Terracampino", body, depth=0,
                 desc="Titularidad de El Terracampino: propiedad de María Vega Blanco, desarrollado por Naraya Services Cloud Consulting S.L.")


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
  <!-- Sin el menú de siempre, esta página dejaba al visitante en un callejón con
       dos salidas en vez de diez. Rutas absolutas porque Vercel sirve este mismo
       fichero para cualquier ruta rota, a cualquier profundidad. -->
  <p style="margin-top:22px; font-size:.95rem;">O ve directamente a:
    <a href="/esquelas.html">Esquelas</a> ·
    <a href="/acompanar.html">Acompañar</a> ·
    <a href="/huerta.html">Huerta</a> ·
    <a href="/campo.html">El campo</a> ·
    <a href="/leyendas.html">Leyendas</a> ·
    <a href="/archivo.html">Archivo</a> ·
    <a href="/gente.html">Gente de Campos</a>
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
    esquelas_por_slug = cargar_esquelas()
    archivo_por_slug = cargar_archivo_fotografico()

    # Foto de cabecera con licencia libre (scripts/buscar_fotos_libres.py):
    # solo relleno honesto mientras no hay fotos de vecinos, con su autor y
    # licencia siempre visibles (obligatorio en CC-BY/CC-BY-SA). Nunca se
    # mezcla con la galería de vecinos, que sigue siendo la sección principal.
    fotos_libres_path = ROOT / "data" / "fotos_libres.json"
    fotos_libres = (json.loads(fotos_libres_path.read_text(encoding="utf-8"))
                     if fotos_libres_path.exists() else {})

    # Avisos meteorológicos y precios del cereal: ninguno de los dos es crítico
    # para el sitio, así que si fallan se sigue sin ellos (mismo criterio que
    # el resto de fuentes).
    print("· Avisos de AEMET…", flush=True)
    try:
        avisos_meteo = aemet_avisos()
    except Exception as exc:  # noqa: BLE001 — una alerta caída no tumba el build
        print(f"  aviso: sin avisos de AEMET ({exc})", file=sys.stderr)
        avisos_meteo = []
    print(f"  {len(avisos_meteo)} aviso(s) vigentes en la comarca")

    print("· Lonja de Valladolid y Palencia…", flush=True)
    try:
        cots_lonja = lonja_cotizaciones(hoy)
    except Exception as exc:  # noqa: BLE001
        print(f"  aviso: sin precios de lonja ({exc})", file=sys.stderr)
        cots_lonja = []
    print(f"  {len(cots_lonja)} productos con cotización")

    print("· Embalses del Duero…", flush=True)
    try:
        emb_datos = situacion_embalses()
    except Exception as exc:  # noqa: BLE001
        print(f"  aviso: sin datos de embalses ({exc})", file=sys.stderr)
        emb_datos = None
    if emb_datos:
        print(f"  {len(emb_datos['sistemas'])} sistemas de riego de la comarca")

    print("· Paro registrado (SEPE)…", flush=True)
    try:
        paro_datos = paro_comarca_cacheado(hoy)
    except Exception as exc:  # noqa: BLE001
        print(f"  aviso: sin datos de paro ({exc})", file=sys.stderr)
        paro_datos = None
    if paro_datos:
        print(f"  {paro_datos['mes_nombre']} {paro_datos['anio']}: {paro_datos['total']} personas")

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
    # Un pueblo que YA tuvo ficha se sigue regenerando aunque hoy no tenga
    # noticias. Si no, pasaba esto: un pueblo pequeño sale una vez en el BOP, se
    # le genera la ficha, y al día siguiente cae de la lista y su página queda
    # CONGELADA en producción — con la plantilla de aquel día, sin el tiempo y
    # sin los avisos de privacidad. Había 8 así, algunas del 12 de julio.
    # La cobertura solo crece, que es justo lo que dice el comentario de arriba.
    ya_publicados = sorted(p.stem for p in (WEB / "municipio").glob("*.html")) \
        if (WEB / "municipio").exists() else []
    slugs = list(dict.fromkeys(PILOTS + list(por_muni.keys()) + list(propias_por_slug.keys())
                               + list(esquelas_por_slug.keys()) + list(archivo_por_slug.keys())
                               + ya_publicados))

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
                m["lat"], m["lon"] = float(lat), float(lon)
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
        m["_esquelas"] = esquelas_por_slug.get(slug, [])
        m["_archivo"] = archivo_por_slug.get(slug, [])
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
    (WEB / "index.html").write_text(
        render_home(built, feed, hoy, avisos_meteo, cots_lonja, paro_datos), encoding="utf-8")
    blog_articulos = cargar_blog_articulos()
    (WEB / "feed.xml").write_text(render_feed_rss(blog_articulos), encoding="utf-8")

    # Páginas para sitemap.xml: se van acumulando según se escribe cada
    # fichero, así el sitemap nunca puede desincronizarse de lo que hay
    # realmente en disco (nada de reconstruir la lista aparte a mano).
    (WEB / "huerta.html").write_text(render_huerta(), encoding="utf-8")
    (WEB / "chivatazo.html").write_text(render_chivatazo(built), encoding="utf-8")
    (WEB / "leyendas.html").write_text(render_leyendas(built), encoding="utf-8")
    (WEB / "campo.html").write_text(render_lonja(cots_lonja, emb_datos), encoding="utf-8")
    nombre_por_slug_built = {m["slug"]: m["name"] for m in built}
    (WEB / "esquelas.html").write_text(
        render_esquelas_pagina(esquelas_por_slug, nombre_por_slug_built, hoy), encoding="utf-8")
    (WEB / "esquela.html").write_text(render_esquela_form(built), encoding="utf-8")
    (WEB / "archivo.html").write_text(
        render_archivo_pagina(archivo_por_slug, nombre_por_slug_built), encoding="utf-8")
    (WEB / "archivo-enviar.html").write_text(render_archivo_form(built), encoding="utf-8")
    (WEB / "gente.html").write_text(render_gente(built, blog_articulos), encoding="utf-8")
    (WEB / "aviso-legal.html").write_text(render_aviso_legal(), encoding="utf-8")
    (WEB / "acompanar.html").write_text(render_acompanar(), encoding="utf-8")
    (WEB / "acompanar-hoja.html").write_text(render_acompanar_hoja(), encoding="utf-8")
    paginas_sitemap: list[tuple[str, str]] = [
        ("", hoy.isoformat()), ("huerta.html", hoy.isoformat()), ("chivatazo.html", hoy.isoformat()),
        ("leyendas.html", hoy.isoformat()), ("campo.html", hoy.isoformat()),
        ("esquelas.html", hoy.isoformat()), ("archivo.html", hoy.isoformat()),
        ("gente.html", hoy.isoformat()), ("aviso-legal.html", hoy.isoformat()),
        ("acompanar.html", hoy.isoformat()),
    ]
    paginas_sitemap += [(f"blog/{a['slug']}.html", a.get("fecha", hoy.isoformat())) for a in blog_articulos]

    for m in built:
        (WEB / "municipio" / f"{m['slug']}.html").write_text(
            render_municipio(m, m["_anuncios"], hoy, avisos_meteo), encoding="utf-8")
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

    # Resumen del día para el boletín de Telegram (scripts/boletin_telegram.py).
    # Se escribe aquí porque el build ya tiene todo esto en memoria: hacerlo
    # aparte obligaría a repetir scrapers y llamadas a la IA. No publica nada —
    # solo deja los datos; enviar es decisión de otro paso.
    escribir_resumen_dia(built, feed, blog_articulos, avisos_meteo, hoy)

    cache.flush()
    modo = "IA (Claude)" if ia.disponible() else "reglas (sin ANTHROPIC_API_KEY)"
    print(f"\nGenerado: web/index.html + {len(built)} fichas de municipio + "
          f"{n_articulos} artículos (plenos + ayudas) + sitemap.xml ({len(paginas_sitemap)} páginas). "
          f"Redacción: {modo}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
