"""«La semana terracampina»: el correo de los viernes.

La portada promete "un correo, una vez por semana" desde el lanzamiento, pero
hasta 2026-11 lo único que se mandaba era la secuencia de bienvenida. Este
script lo cumple: cada viernes arma el correo de la semana con lo publicado en
los últimos siete días y lo manda por Telegram al administrador en privado,
como zip para importar en MailerLite. Igual que la newsletter de cada
investigación (scripts/empaquetar_newsletter.py), es manual a propósito:
meter contenido de campaña por API exige el plan Advanced de MailerLite.

Qué lleva:
  - una entradilla de la semana, con la voz de la casa (IA, solo a partir de
    los titulares que se le dan: no puede añadir nada que no esté en ellos);
  - la investigación de la semana, si la hay;
  - lo más importante (los plenos primero);
  - los pueblos con novedades, dos piezas cada uno como mucho;
  - la agenda de fiestas que viene;
  - el banner rotativo de los proyectos hermanos.

Lee web/datos/ultimas.json, que escribe el build diario: corre DESPUÉS de él.

Uso:
    python -m scripts.semana_terracampina                # solo el zip, sin mandar
    python -m scripts.semana_terracampina --auto         # build diario: solo los viernes y una vez
    python -m scripts.semana_terracampina --auto --forzar
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from scripts.empaquetar_newsletter import (  # noqa: E402
    HERMANOS_DIR, IMAGENES_BLOG, ROOT, SALIDA_DIR,
    elegir_banner, guardar_para_email, marcar_enviado, ya_enviado,
)
from sitegen import ia  # noqa: E402
from sitegen.build import url_publica  # noqa: E402

ULTIMAS = ROOT / "web" / "datos" / "ultimas.json"
MANIFIESTO_BLOG = ROOT / "data" / "blog" / "articulos.json"
MAX_DESTACADAS = 5
MAX_PUEBLOS = 10
POR_PUEBLO = 2

E = html.escape
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _hoy_madrid() -> date:
    return datetime.now(ZoneInfo("Europe/Madrid")).date()


def _clave_semana(hoy: date) -> str:
    anio, semana, _ = hoy.isocalendar()
    return f"semana-{anio}-{semana:02d}"


def _fecha_corta(iso: str) -> str:
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return ""
    return f"{d.day} de {_MESES[d.month - 1]}"


def recopilar(hoy: date) -> dict:
    piezas = json.loads(ULTIMAS.read_text(encoding="utf-8")) if ULTIMAS.exists() else []
    desde = (hoy - timedelta(days=7)).isoformat()
    semana = [p for p in piezas if p.get("fecha", "") >= desde]

    investigacion = None
    if MANIFIESTO_BLOG.exists():
        for a in json.loads(MANIFIESTO_BLOG.read_text(encoding="utf-8")):
            if a.get("fecha", "") >= desde:
                investigacion = a
                break

    # Lo más importante: plenos y piezas con artículo propio, por fecha.
    destacadas = sorted(semana, key=lambda p: (p.get("pleno", False), p.get("propia", False), p.get("fecha", "")),
                        reverse=True)[:MAX_DESTACADAS]
    usadas = {id(p) for p in destacadas}

    por_pueblo: dict[str, list[dict]] = {}
    for p in semana:
        if id(p) in usadas or not p.get("pueblo"):
            continue
        lista = por_pueblo.setdefault(p["pueblo"], [])
        if len(lista) < POR_PUEBLO:
            lista.append(p)
    pueblos = sorted(por_pueblo.items(), key=lambda kv: -len(kv[1]))[:MAX_PUEBLOS]
    pueblos.sort(key=lambda kv: kv[0])

    from scrapers.common import load_municipios
    from sitegen.contenido import eventos_comarca
    nombres = {m.slug: m.name for m in load_municipios()}
    agenda = eventos_comarca(nombres, hoy, n=5)

    return {"semana": semana, "investigacion": investigacion, "destacadas": destacadas,
            "pueblos": pueblos, "agenda": agenda}


def entradilla_semana(datos: dict) -> str:
    """Dos o tres frases con la voz de la casa a partir de los titulares de la
    semana. Si la IA falla, una frase neutra: el correo sale igual."""
    titulares = [f"{p['pueblo']}: {p['titular']}" for p in datos["semana"][:40]]
    if datos["investigacion"]:
        titulares.insert(0, f"Investigación de la semana: {datos['investigacion']['titular']}")
    neutra = f"Esta semana han pasado {len(datos['semana'])} cosas en los pueblos de Tierra de Campos. Aquí van las que más importan."
    if not titulares or not ia.disponible():
        return neutra
    try:
        resp = ia._llamar(
            model=ia._model(),
            max_tokens=3000,
            system=(
                "Eres el vecino de Tierra de Campos que se entera de todo y abre el correo semanal de "
                "El Terracampino. Escribe dos o tres frases que cuenten cómo ha ido la semana en la "
                "comarca, cercano pero serio, a partir SOLO de los titulares que se te dan. No añadas "
                "ningún dato, nombre, cifra ni valoración que no esté en ellos. Nada de saludos, "
                "exclamaciones, 'en resumen' ni folclore. Devuelve solo el texto."
            ),
            messages=[{"role": "user", "content": "Titulares de la semana:\n" + "\n".join(f"- {t}" for t in titulares)}],
        )
        return ia._texto(resp).strip()
    except Exception as exc:  # noqa: BLE001
        print(f"aviso: sin entradilla de IA ({exc}); se usa la neutra", file=sys.stderr)
        return neutra


def _pieza_html(p: dict, *, con_pueblo: bool) -> str:
    kicker = " · ".join(x for x in [p.get("pueblo") if con_pueblo else "", p.get("fuente", ""),
                                    _fecha_corta(p.get("fecha", ""))] if x)
    entradilla = (f'<p style="margin:6px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;'
                  f'line-height:1.55;color:rgba(19,19,19,.78);">{E(p["entradilla"])}</p>'
                  if p.get("entradilla") else "")
    return f"""<tr><td style="padding:16px 0;border-bottom:1px solid rgba(19,19,19,.14);">
<span style="display:block;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#1F3F5C;">{E(kicker)}</span>
<a href="{E(p['url'])}" style="display:block;margin-top:4px;font-family:Georgia,'Times New Roman',serif;font-size:19px;line-height:1.3;font-weight:bold;color:#131313;text-decoration:none;">{E(p['titular'])}</a>
{entradilla}
</td></tr>"""


def _titulo_seccion(texto: str) -> str:
    return (f'<tr><td style="padding:30px 0 4px;border-bottom:2px solid #131313;">'
            f'<span style="font-family:Georgia,\'Times New Roman\',serif;font-size:18px;font-weight:bold;color:#131313;">'
            f'{E(texto)}</span></td></tr>')


def componer(datos: dict, hoy: date, entradilla: str, banner: dict, con_portada: bool) -> str:
    filas = []
    inv = datos["investigacion"]
    if inv:
        url_inv = url_publica(f"blog/{inv['slug']}")
        img = ('<img src="images/portada.jpg" width="536" alt="" style="display:block;width:100%;'
               'max-width:536px;height:auto;border:0;margin:0 0 14px;">') if con_portada else ""
        filas.append(_titulo_seccion("La investigación de la semana"))
        filas.append(f"""<tr><td style="padding:18px 0 4px;">
{img}<a href="{E(url_inv)}" style="font-family:Georgia,'Times New Roman',serif;font-size:23px;line-height:1.25;font-weight:bold;color:#131313;text-decoration:none;">{E(inv['titular'])}</a>
<p style="margin:8px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55;color:rgba(19,19,19,.78);">{E(inv['entradilla'])}</p>
<p style="margin:10px 0 0;"><a href="{E(url_inv)}" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1F3F5C;">Leer la investigación &rarr;</a></p>
</td></tr>""")

    if datos["destacadas"]:
        filas.append(_titulo_seccion("Lo más importante"))
        filas.extend(_pieza_html(p, con_pueblo=True) for p in datos["destacadas"])

    # Banner de la casa tras el primer bloque, como en el resto de correos.
    filas.append(f"""<tr><td style="padding:24px 0;">
<span style="display:block;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:rgba(19,19,19,.55);margin-bottom:10px;">De la casa</span>
<a href="{E(banner['url'])}"><img src="images/banner.jpg" width="536" alt="{E(banner['alt'])}" style="display:block;width:100%;max-width:536px;height:auto;border:0;"></a>
</td></tr>""")

    for pueblo, piezas in datos["pueblos"]:
        filas.append(_titulo_seccion(pueblo))
        filas.extend(_pieza_html(p, con_pueblo=False) for p in piezas)

    if datos["agenda"]:
        items = "".join(
            f'<li style="padding:6px 0;border-bottom:1px solid rgba(19,19,19,.12);">'
            f'<strong style="font-family:\'Courier New\',monospace;font-size:13px;color:#1F3F5C;">{E(e["cuando"])}</strong> · '
            f'{E(e["nombre"])} <span style="color:rgba(19,19,19,.6);">({E(e["pueblo"])})</span></li>'
            for e in datos["agenda"])
        filas.append(_titulo_seccion("Lo que viene"))
        filas.append(f'<tr><td style="padding:10px 0;font-family:Arial,Helvetica,sans-serif;font-size:15px;">'
                     f'<ul style="list-style:none;margin:0;padding:0;">{items}</ul></td></tr>')

    titulo = f"La semana terracampina · {hoy.day} de {_MESES[hoy.month - 1]}"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(titulo)}</title>
</head>
<body style="margin:0;padding:0;background:#FAF8F4;font-family:Georgia,'Times New Roman',serif;color:#131313;">
<div style="display:none;max-height:0;overflow:hidden;">{E(entradilla[:140])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FAF8F4;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="536" cellpadding="0" cellspacing="0" style="max-width:536px;width:100%;">

<tr><td style="padding-bottom:18px;border-bottom:2px solid #131313;">
<span style="font-family:'Courier New',monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#1F3F5C;">El Terracampino</span>
<h1 style="margin:8px 0 0;font-family:Georgia,'Times New Roman',serif;font-size:28px;line-height:1.2;color:#131313;">La semana terracampina</h1>
<span style="display:block;margin-top:4px;font-family:'Courier New',monospace;font-size:12px;color:rgba(19,19,19,.6);">{hoy.day} de {_MESES[hoy.month - 1]} de {hoy.year}</span>
</td></tr>

<tr><td style="padding:22px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:17px;line-height:1.6;color:#131313;">
<p style="margin:0;">{E(entradilla)}</p>
</td></tr>

{''.join(filas)}

<tr><td style="padding:28px 0 0;">
<a href="{url_publica("")}" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1F3F5C;">Todo lo de tu pueblo, cada día, en elterracampino.es &rarr;</a>
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


def empaquetar(hoy: date) -> tuple[Path, dict, int] | None:
    datos = recopilar(hoy)
    if not datos["semana"] and not datos["investigacion"]:
        print("Semana sin novedades: no hay correo.")
        return None
    clave = _clave_semana(hoy)
    banner = elegir_banner(clave)
    entradilla = entradilla_semana(datos)
    inv = datos["investigacion"]
    portada = IMAGENES_BLOG / f"{inv['slug']}.jpg" if inv and inv.get("tiene_imagen") else None
    if portada is not None and not portada.exists():
        portada = None

    carpeta = SALIDA_DIR / clave
    if carpeta.exists():
        shutil.rmtree(carpeta)
    (carpeta / "images").mkdir(parents=True)
    (carpeta / "index.html").write_text(componer(datos, hoy, entradilla, banner, bool(portada)), encoding="utf-8")
    shutil.copy(HERMANOS_DIR / banner["fichero"], carpeta / "images" / "banner.jpg")
    if portada:
        guardar_para_email(portada, carpeta / "images" / "portada.jpg")
    zip_path = SALIDA_DIR / f"{clave}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", carpeta)
    shutil.rmtree(carpeta)
    n = len(datos["destacadas"]) + sum(len(v) for _, v in datos["pueblos"])
    print(f"Correo de la {clave}: {n} piezas, {len(datos['pueblos'])} pueblos, banner {banner['nombre']}")
    print(f"Zip: {zip_path.relative_to(ROOT)}")
    return zip_path, banner, n


def enviar(zip_path: Path, banner: dict, n: int, hoy: date) -> bool:
    import os

    import requests

    token, admin = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("ADMIN_TELEGRAM_ID")
    if not token or not admin:
        print("aviso: falta TELEGRAM_BOT_TOKEN o ADMIN_TELEGRAM_ID — no se manda", file=sys.stderr)
        return False
    caption = (f"📬 La semana terracampina del {hoy.day} de {_MESES[hoy.month - 1]}: {n} piezas.\n\n"
               f"Banner de hermanos: {banner['nombre']}\n\n"
               "Importar en MailerLite: Campaigns → Create campaign → Regular → editor HTML → "
               "Import zip. Asunto sugerido: «La semana terracampina».")
    with open(zip_path, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                          data={"chat_id": admin, "caption": caption},
                          files={"document": (zip_path.name, f, "application/zip")}, timeout=30)
    if r.status_code != 200:
        print(f"aviso: Telegram respondió {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return False
    print("Mandado por Telegram.")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="La semana terracampina (correo de los viernes)")
    ap.add_argument("--auto", action="store_true", help="build diario: solo los viernes, una vez por semana")
    ap.add_argument("--forzar", action="store_true", help="con --auto: cualquier día y aunque ya se mandara")
    args = ap.parse_args()

    hoy = _hoy_madrid()
    clave = _clave_semana(hoy)
    if args.auto and not args.forzar:
        if hoy.weekday() != 4:
            print("Hoy no es viernes: no toca el correo de la semana.")
            return 0
        if ya_enviado(clave):
            print(f"{clave}: ya se mandó.")
            return 0
    hecho = empaquetar(hoy)
    if hecho and args.auto:
        zip_path, banner, n = hecho
        if enviar(zip_path, banner, n, hoy):
            marcar_enviado(clave)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
