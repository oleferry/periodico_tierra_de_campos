"""Empaqueta una investigación ya publicada en web/blog/ como email listo para
importar a mano en MailerLite: HTML + carpeta images/ + banner rotativo de
proyectos hermanos, todo en un .zip.

Por qué a mano: meter contenido de campaña por API exige el plan Advanced de
MailerLite; el gratuito no lo permite (ver docs/newsletter.md). El zip generado
se sube en MailerLite: Campaigns → Create campaign → Regular → editor HTML →
Import zip.

El banner de hermanos (brand/hermanos/hermanos.json) rota por POSICIÓN EN LA
SERIE de investigaciones empaquetadas, no por semana del calendario — si dos
investigaciones salen la misma semana o una semana no hay ninguna, el reparto
sigue siendo uno cada uno. El estado se guarda en
data/newsletter_banners_estado.json (versionado en git a propósito).

Uso:
    python -m scripts.empaquetar_newsletter                  # la última investigación
    python -m scripts.empaquetar_newsletter --slug <slug>
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = ROOT / "web" / "blog"
IMAGENES_BLOG = ROOT / "web" / "assets" / "blog"
HERMANOS_DIR = ROOT / "brand" / "hermanos"
HERMANOS_JSON = HERMANOS_DIR / "hermanos.json"
ESTADO_PATH = ROOT / "data" / "newsletter_banners_estado.json"
SALIDA_DIR = ROOT / "data" / "newsletter_salida"

SITE_URL = "https://elterracampino.es"


def elegir_slug(slug: str | None) -> str:
    if slug:
        if not (BLOG_DIR / f"{slug}.html").exists():
            raise SystemExit(f"No existe web/blog/{slug}.html")
        return slug
    piezas = sorted(BLOG_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not piezas:
        raise SystemExit("No hay ninguna investigación en web/blog/")
    return piezas[0].stem


def leer_articulo(slug: str) -> dict:
    html = (BLOG_DIR / f"{slug}.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("h1")
    entradilla = soup.select_one(".tc-articulo-entradilla")
    if not h1 or not entradilla:
        raise SystemExit(
            f"web/blog/{slug}.html no tiene <h1> o .tc-articulo-entradilla — "
            "¿es realmente una investigación generada por sitegen.build?"
        )
    return {
        "titulo": h1.get_text(strip=True),
        "entradilla": entradilla.get_text(" ", strip=True),
        "url": f"{SITE_URL}/blog/{slug}.html",
    }


def imagen_portada(slug: str) -> Path | None:
    ruta = IMAGENES_BLOG / f"{slug}.jpg"
    return ruta if ruta.exists() else None


ANCHO_EMAIL = 536  # ancho de columna del email; las portadas del sitio salen a 1024x1024


def guardar_para_email(origen: Path, destino: Path, ancho: int = ANCHO_EMAIL) -> None:
    """Reescala a la anchura del email — las portadas del sitio (1024x1024, ~2MB)
    son demasiado pesadas para un correo tal cual."""
    im = Image.open(origen).convert("RGB")
    if im.width > ancho:
        alto = round(im.height * ancho / im.width)
        im = im.resize((ancho, alto), Image.LANCZOS)
    for calidad in (85, 78, 70, 60):
        im.save(destino, "JPEG", quality=calidad, optimize=True)
        if destino.stat().st_size <= 150_000:
            break


def elegir_banner(slug: str) -> dict:
    hermanos = json.loads(HERMANOS_JSON.read_text(encoding="utf-8"))
    if not hermanos:
        raise SystemExit("brand/hermanos/hermanos.json está vacío.")

    estado = json.loads(ESTADO_PATH.read_text(encoding="utf-8")) if ESTADO_PATH.exists() else {
        "posicion": -1,
        "historial": {},
    }

    if slug in estado["historial"]:
        posicion = estado["historial"][slug]
    else:
        posicion = (estado["posicion"] + 1) % len(hermanos)
        estado["posicion"] = posicion
        estado["historial"][slug] = posicion
        ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
        ESTADO_PATH.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")

    return hermanos[posicion % len(hermanos)]


def componer_email(articulo: dict, banner: dict, tiene_portada: bool) -> str:
    portada_html = (
        f'<img src="images/portada.jpg" width="536" alt="" '
        f'style="display:block;width:100%;max-width:536px;height:auto;border:0;margin:0 0 24px;">'
        if tiene_portada else ""
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{articulo['titulo']}</title>
</head>
<body style="margin:0;padding:0;background:#FAF8F4;font-family:Georgia,'Times New Roman',serif;color:#131313;">
<div style="display:none;max-height:0;overflow:hidden;">{articulo['entradilla'][:140]}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FAF8F4;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="536" cellpadding="0" cellspacing="0" style="max-width:536px;width:100%;">

<tr><td style="padding-bottom:20px;border-bottom:2px solid #131313;">
<span style="font-family:'Courier New',monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#1F3F5C;">El Terracampino</span>
</td></tr>

<tr><td style="padding:28px 0 4px;">
<h1 style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:26px;line-height:1.25;color:#131313;">{articulo['titulo']}</h1>
</td></tr>

<tr><td style="padding:16px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.6;color:#131313;">
<p style="margin:0 0 22px;">{articulo['entradilla']}</p>
</td></tr>

<tr><td style="padding:0 0 28px;">
<a href="{articulo['url']}" style="display:inline-block;background:#131313;color:#FFFFFF;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-weight:bold;font-size:15px;padding:13px 22px;">Leer el reportaje completo &rarr;</a>
</td></tr>

<tr><td style="padding:0 0 28px;">
{portada_html}
</td></tr>

<tr><td style="padding:20px 0;border-top:1px solid rgba(19,19,19,.16);border-bottom:1px solid rgba(19,19,19,.16);">
<span style="display:block;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:rgba(19,19,19,.55);margin-bottom:10px;">De la casa</span>
<a href="{banner['url']}">
<img src="images/banner.jpg" width="536" alt="{banner['alt']}" style="display:block;width:100%;max-width:536px;height:auto;border:0;">
</a>
</td></tr>

<tr><td style="padding:28px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.6;color:rgba(19,19,19,.55);">
<p style="margin:0;">Recibes este correo porque te suscribiste en elterracampino.es.
<a href="{{$unsubscribe}}" style="color:rgba(19,19,19,.55);">Darse de baja</a>.</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""


def empaquetar(slug: str) -> Path:
    articulo = leer_articulo(slug)
    portada = imagen_portada(slug)
    banner = elegir_banner(slug)

    if not portada:
        print(f"aviso: sin imagen de portada para {slug} (web/assets/blog/{slug}.jpg no existe) — el email sale sin ella")

    html = componer_email(articulo, banner, tiene_portada=bool(portada))

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    carpeta = SALIDA_DIR / slug
    if carpeta.exists():
        shutil.rmtree(carpeta)
    (carpeta / "images").mkdir(parents=True)

    (carpeta / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(HERMANOS_DIR / banner["fichero"], carpeta / "images" / "banner.jpg")
    if portada:
        guardar_para_email(portada, carpeta / "images" / "portada.jpg")

    zip_path = SALIDA_DIR / f"{slug}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", carpeta)
    shutil.rmtree(carpeta)

    print(f"Investigación: {articulo['titulo']}")
    print(f"Banner de hermanos: {banner['nombre']} ({banner['url']})")
    print(f"Zip listo: {zip_path.relative_to(ROOT)}")
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Empaqueta una investigación como email para MailerLite")
    ap.add_argument("--slug", help="slug del artículo en web/blog/ (por defecto, el más reciente)")
    args = ap.parse_args()

    slug = elegir_slug(args.slug)
    empaquetar(slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
