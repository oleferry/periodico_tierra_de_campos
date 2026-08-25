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

El envío por Telegram va siempre al administrador en privado (ADMIN_TELEGRAM_ID),
nunca al canal público — es un borrador de trabajo, no contenido publicado.

Uso:
    python -m scripts.empaquetar_newsletter                  # la última investigación, solo el zip
    python -m scripts.empaquetar_newsletter --slug <slug>
    python -m scripts.empaquetar_newsletter --telegram        # zip + lo manda por Telegram
    python -m scripts.empaquetar_newsletter --auto            # modo build diario: solo si hay investigación nueva sin mandar
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

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
    """El artículo COMPLETO, no un teaser — así lo pidió Daniel: en Gafasvan el
    email lleva el reportaje entero, no solo un enlace a la web."""
    html = (BLOG_DIR / f"{slug}.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    articulo_el = soup.select_one("article")
    h1 = soup.select_one("h1")
    entradilla = soup.select_one(".tc-articulo-entradilla")
    if not articulo_el or not h1 or not entradilla:
        raise SystemExit(
            f"web/blog/{slug}.html no tiene <article>, <h1> o .tc-articulo-entradilla — "
            "¿es realmente una investigación generada por sitegen.build?"
        )

    cuerpo = []
    for el in articulo_el.find_all(["h2", "p"]):
        clases = el.get("class") or []
        if el.name == "h2" and "tc-blog-subtitulo" in clases:
            cuerpo.append(("h2", el.get_text(" ", strip=True)))
        elif el.name == "p" and "tc-articulo-parrafo" in clases:
            cuerpo.append(("p", el.get_text(" ", strip=True)))

    fuentes_box = articulo_el.select_one(".tc-source-box")
    fuentes = fuentes_box.get_text(" ", strip=True) if fuentes_box else ""

    return {
        "titulo": h1.get_text(strip=True),
        "entradilla": entradilla.get_text(" ", strip=True),
        "cuerpo": cuerpo,
        "fuentes": fuentes,
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


def _cargar_estado() -> dict:
    if not ESTADO_PATH.exists():
        return {"posicion": -1, "historial": {}, "enviados": []}
    estado = json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
    estado.setdefault("enviados", [])
    return estado


def _guardar_estado(estado: dict) -> None:
    ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
    ESTADO_PATH.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def elegir_banner(slug: str) -> dict:
    hermanos = json.loads(HERMANOS_JSON.read_text(encoding="utf-8"))
    if not hermanos:
        raise SystemExit("brand/hermanos/hermanos.json está vacío.")

    estado = _cargar_estado()

    if slug in estado["historial"]:
        posicion = estado["historial"][slug]
    else:
        posicion = (estado["posicion"] + 1) % len(hermanos)
        estado["posicion"] = posicion
        estado["historial"][slug] = posicion
        _guardar_estado(estado)

    return hermanos[posicion % len(hermanos)]


def ya_enviado(slug: str) -> bool:
    return slug in _cargar_estado()["enviados"]


def marcar_enviado(slug: str) -> None:
    estado = _cargar_estado()
    if slug not in estado["enviados"]:
        estado["enviados"].append(slug)
        _guardar_estado(estado)


def _cuerpo_html(cuerpo: list[tuple[str, str]]) -> str:
    bloques = []
    for tipo, texto in cuerpo:
        texto = html.escape(texto)
        if tipo == "h2":
            bloques.append(
                f'<h2 style="margin:26px 0 10px;font-family:Georgia,\'Times New Roman\',serif;'
                f'font-size:19px;line-height:1.3;color:#131313;">{texto}</h2>'
            )
        else:
            bloques.append(
                f'<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;'
                f'font-size:16px;line-height:1.6;color:#131313;">{texto}</p>'
            )
    return "\n".join(bloques)


def componer_email(articulo: dict, banner: dict, tiene_portada: bool) -> str:
    titulo = html.escape(articulo["titulo"])
    entradilla = html.escape(articulo["entradilla"])
    preheader = html.escape(articulo["entradilla"][:140])

    portada_html = (
        f'<tr><td style="padding:20px 0 0;">'
        f'<img src="images/portada.jpg" width="536" alt="" '
        f'style="display:block;width:100%;max-width:536px;height:auto;border:0;">'
        f"</td></tr>"
        if tiene_portada else ""
    )

    fuentes_html = ""
    if articulo["fuentes"]:
        fuentes_html = f"""
<tr><td style="padding:24px 0 0;border-left:3px solid #131313;padding-left:16px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.6;color:rgba(19,19,19,.72);">
{html.escape(articulo['fuentes'])}
</td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
</head>
<body style="margin:0;padding:0;background:#FAF8F4;font-family:Georgia,'Times New Roman',serif;color:#131313;">
<div style="display:none;max-height:0;overflow:hidden;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FAF8F4;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="536" cellpadding="0" cellspacing="0" style="max-width:536px;width:100%;">

<tr><td style="padding-bottom:20px;border-bottom:2px solid #131313;">
<span style="font-family:'Courier New',monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#1F3F5C;">El Terracampino</span>
</td></tr>

<tr><td style="padding:28px 0 4px;">
<h1 style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:26px;line-height:1.25;color:#131313;">{titulo}</h1>
</td></tr>
{portada_html}

<tr><td style="padding:20px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:17px;line-height:1.6;color:#131313;">
<p style="margin:0;font-weight:bold;">{entradilla}</p>
</td></tr>

<tr><td style="padding:20px 0;border-top:1px solid rgba(19,19,19,.16);border-bottom:1px solid rgba(19,19,19,.16);">
<span style="display:block;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:rgba(19,19,19,.55);margin-bottom:10px;">De la casa</span>
<a href="{banner['url']}">
<img src="images/banner.jpg" width="536" alt="{html.escape(banner['alt'])}" style="display:block;width:100%;max-width:536px;height:auto;border:0;">
</a>
</td></tr>

<tr><td style="padding:24px 0 0;">
{_cuerpo_html(articulo['cuerpo'])}
</td></tr>
{fuentes_html}

<tr><td style="padding:24px 0 0;">
<a href="{articulo['url']}" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1F3F5C;">Leer y compartir en elterracampino.es &rarr;</a>
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
    return zip_path, articulo, banner


def enviar_telegram(zip_path: Path, articulo: dict, banner: dict) -> bool:
    """Manda el zip al admin por privado (nunca al canal público). Requiere
    TELEGRAM_BOT_TOKEN + ADMIN_TELEGRAM_ID (tu id numérico, se saca con /id
    hablando con el bot en privado)."""
    import os
    import requests

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if not token or not admin_id:
        print("aviso: falta TELEGRAM_BOT_TOKEN o ADMIN_TELEGRAM_ID — no se manda por Telegram", file=sys.stderr)
        return False

    caption = (
        f"📩 Newsletter lista: {articulo['titulo']}\n\n"
        f"Banner de hermanos: {banner['nombre']}\n\n"
        f"Importar en MailerLite: Campaigns → Create campaign → Regular → "
        f"editor HTML → Import zip."
    )
    with open(zip_path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": admin_id, "caption": caption},
            files={"document": (zip_path.name, f, "application/zip")},
            timeout=30,
        )
    if r.status_code != 200:
        print(f"aviso: fallo al mandar el zip por Telegram: {r.text}", file=sys.stderr)
        return False
    print("Mandado por Telegram.")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Empaqueta una investigación como email para MailerLite")
    ap.add_argument("--slug", help="slug del artículo en web/blog/ (por defecto, el más reciente)")
    ap.add_argument("--telegram", action="store_true", help="manda el zip por Telegram al terminar")
    ap.add_argument(
        "--auto", action="store_true",
        help="modo build diario: la última investigación, solo si no se mandó ya; manda por Telegram sola",
    )
    ap.add_argument("--forzar", action="store_true", help="con --auto, manda aunque ya conste como enviada")
    args = ap.parse_args()

    if args.auto:
        slug = elegir_slug(None)
        if ya_enviado(slug) and not args.forzar:
            print(f"{slug}: ya se mandó antes, nada que hacer.")
            return 0
        zip_path, articulo, banner = empaquetar(slug)
        if enviar_telegram(zip_path, articulo, banner):
            marcar_enviado(slug)
        return 0

    slug = elegir_slug(args.slug)
    zip_path, articulo, banner = empaquetar(slug)
    if args.telegram:
        if enviar_telegram(zip_path, articulo, banner):
            marcar_enviado(slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
