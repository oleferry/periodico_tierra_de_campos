"""Procesa fotos enviadas por vecinos: recorta a un formato fijo y añade el
marco de marca — decisión explícita del usuario: SOLO encuadre y marco, sin
retocar color ni luz. La foto es del vecino, no nuestra; no se toca el
contenido, solo el formato en el que se presenta.

El marco usa el mismo lenguaje visual que el resto del sitio (recorte de
periódico: blanco, regla fina negra, franja con la marca en IBM Plex Mono y
el pueblo en PT Serif — brand/web/brand-tokens.css), no un marco genérico de
red social. Las fuentes están bundled en brand/fonts/ (Google Fonts, OFL,
libres de usar) para no depender de qué tenga instalado el sistema donde
corra esto — importante porque el bot de Telegram puede acabar corriendo en
un servidor distinto a esta máquina.

El pie de foto lo escribe la IA a partir de lo que ve en la imagen (Claude
con visión) más el texto que mande el remitente si manda alguno — nunca
inventa datos que no se puedan ver en la foto (ver sitegen/ia.py:pie_de_foto).

Como el resto de contenido enviado por vecinos (tablón de negocios), esto
pasa por REVISIÓN antes de publicarse, no se publica automático — ver
data/fotos/pendientes.json.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
FUENTES = ROOT / "brand" / "fonts"

ANCHO_SALIDA = 1080
FORMATO = (4, 5)  # ancho:alto, retrato — encaja bien en una rejilla tipo Instagram
MARGEN = 36
FRANJA_PIE = 130

TINTA = (19, 19, 19)
PAPEL = (255, 255, 255)
AZUL_BOP = (31, 63, 92)

_cache_fuentes: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _fuente(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    clave = (nombre, tam)
    if clave not in _cache_fuentes:
        _cache_fuentes[clave] = ImageFont.truetype(str(FUENTES / nombre), tam)
    return _cache_fuentes[clave]


def _recortar_a_formato(im: Image.Image, formato: tuple[int, int]) -> Image.Image:
    """Recorta al centro para encajar en la proporción `formato`, sin deformar."""
    obj_w, obj_h = formato
    ratio_obj = obj_w / obj_h
    w, h = im.size
    ratio = w / h
    if ratio > ratio_obj:  # más ancha de lo necesario: recorta los lados
        nuevo_w = round(h * ratio_obj)
        x0 = (w - nuevo_w) // 2
        im = im.crop((x0, 0, x0 + nuevo_w, h))
    else:  # más alta de lo necesario: recorta arriba/abajo
        nuevo_h = round(w / ratio_obj)
        y0 = (h - nuevo_h) // 2
        im = im.crop((0, y0, w, y0 + nuevo_h))
    return im


def procesar(imagen_bytes: bytes, *, pueblo: str) -> bytes:
    """Recorta a formato fijo + marco de marca. No toca color/luz. Devuelve
    JPEG en bytes, listo para guardar y para pasarle a la IA del pie de foto."""
    im = Image.open(io.BytesIO(imagen_bytes))
    im = ImageOps.exif_transpose(im).convert("RGB")
    im = _recortar_a_formato(im, FORMATO)

    ancho_foto = ANCHO_SALIDA - 2 * MARGEN
    alto_foto = round(ancho_foto * FORMATO[1] / FORMATO[0])
    im = im.resize((ancho_foto, alto_foto), Image.LANCZOS)

    alto_total = MARGEN + alto_foto + MARGEN + FRANJA_PIE
    lienzo = Image.new("RGB", (ANCHO_SALIDA, alto_total), PAPEL)
    lienzo.paste(im, (MARGEN, MARGEN))

    draw = ImageDraw.Draw(lienzo)
    y_regla = MARGEN + alto_foto + MARGEN // 2
    draw.line([(MARGEN, y_regla), (ANCHO_SALIDA - MARGEN, y_regla)], fill=TINTA, width=2)

    y_franja = MARGEN + alto_foto + MARGEN
    draw.text((MARGEN, y_franja + 12), "EL TERRACAMPINO", font=_fuente("IBMPlexMono-Medium.ttf", 22), fill=AZUL_BOP)
    draw.text((MARGEN, y_franja + 46), pueblo, font=_fuente("PTSerif-Bold.ttf", 42), fill=TINTA)

    salida = io.BytesIO()
    lienzo.save(salida, format="JPEG", quality=90)
    return salida.getvalue()
