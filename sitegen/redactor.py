"""Redactor: convierte el texto oficial (BOP/BOCyL) en titular + entradilla.

Primera versión POR REGLAS (determinista, sin IA): detecta el tema del anuncio y
genera un titular periodístico y una entradilla legible, conservando el dato real y
el enlace a la fuente. Cuando se conecte el pipeline con IA, basta sustituir
`redactar()` por la llamada al modelo (misma firma), guardando el resultado por hash.

Reglas de estilo (editorial/politica_editorial.md, docs/guia-estilo-gi.md):
  · factual, sin alarmismo, sin inventar nada que no esté en el texto oficial;
  · el titular es un gancho claro; la entradilla da el detalle y remite a la fuente.
"""

from __future__ import annotations

import hashlib
import re
import sys

from scrapers.common import strip_accents
from sitegen import cache, ia


def redactar(doc: dict) -> dict:
    """Titular + entradilla. Usa la IA si hay clave (con caché por hash); si no,
    o si la IA falla, cae al redactor por reglas (determinista)."""
    es_pleno_con_texto = doc.get("source_type") == "municipal_plenary" and doc.get("acta_texto")
    clave = hashlib.sha256(
        f"{ia.PROMPT_VERSION}|{doc.get('title','')}|{doc.get('municipality_name','')}|"
        f"{doc.get('acta_texto','')}".encode()
    ).hexdigest()
    guardado = cache.get("redactor", clave)
    if guardado:
        return _con_titular_capitalizado(guardado)
    if ia.disponible():
        try:
            r = ia.redactar_pleno(doc) if es_pleno_con_texto else ia.redactar(doc)
            cache.set("redactor", clave, r)
            return _con_titular_capitalizado(r)
        except Exception as exc:  # noqa: BLE001 (cualquier fallo → reglas)
            print(f"  aviso: IA no disponible para un titular ({exc}); uso reglas", file=sys.stderr)
    return redactar_reglas(doc)


def _con_titular_capitalizado(r: dict) -> dict:
    """La IA no siempre empieza el titular en mayúscula; se normaliza aquí
    (una sola vez, aplica también a lo que ya estaba en caché)."""
    t = r["titular"]
    if t and t[0].islower():
        r = {**r, "titular": t[0].upper() + t[1:]}
    return r


def _limpiar(titulo: str) -> str:
    """Quita ruido burocrático para la entradilla, sin alterar el fondo."""
    t = titulo.strip()
    t = re.sub(r"\s*Expte\.?\s*:.*$", "", t)
    t = re.sub(r"\s*\((?:Valladolid|Palencia|Le[oó]n|Zamora)\)", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.rstrip(" .") + "."


def _quoted(titulo: str) -> str | None:
    m = re.search(r"[«\"]([^»\"]{2,60})[»\"]", titulo)
    return m.group(1) if m else None


def _para_objeto(titulo: str) -> str | None:
    """Extrae el 'para <algo>' de las solicitudes de suelo rústico."""
    m = re.search(r"\bpara (?:la |el |un |una |unos |unas )?(.+?)(?:,? en (?:la |el )?(?:parcela|pol[ií]gono|t[ée]rmino)|\.| promovid)", titulo, re.I)
    if m:
        obj = m.group(1).strip()
        return obj if 3 <= len(obj) <= 80 else None
    return None


def _licitacion_objeto(titulo: str) -> str | None:
    m = re.search(r"licitaci[oó]n (?:de |del |de la |para )?(.+)", titulo, re.I)
    if m:
        return m.group(1).strip().rstrip(".")
    return None


def _por_la_que(titulo: str) -> str | None:
    """Extrae la acción real de una resolución/orden: '...por la que se <acción>'.
    Es la cláusula que de verdad dice qué ha pasado; el resto es quién y cuándo firma."""
    m = re.search(r"por (?:la|el) que se (.+?)(?:\.\s|\. ?$|$)", titulo, re.I)
    if not m:
        return None
    accion = m.group(1).strip().rstrip(".")
    return accion if 8 <= len(accion) <= 140 else None


def redactar_reglas(doc: dict) -> dict:
    """Redactor determinista por reglas (respaldo cuando no hay IA)."""
    titulo = (doc.get("title") or "").strip()
    muni = doc.get("municipality_name", "").strip()
    t = strip_accents(titulo).lower()
    entradilla = _limpiar(titulo)
    empresa = _quoted(titulo)
    por = f", promovido por {empresa}," if empresa else ""

    def h(txt):  # helper: titular sin punto final
        return txt.rstrip(".")

    # --- detección de tema, de lo más específico a lo más genérico ---
    if "fotovoltaic" in t or "planta solar" in t or "energia electrica de origen fotovoltaico" in t:
        nombre = f" «{empresa}»" if empresa else ""
        titular = h(f"Un parque solar fotovoltaico{nombre} avanza en {muni}")
    elif "eolic" in t or "parque eolico" in t:
        if empresa and "eolic" in strip_accents(empresa).lower():
            titular = h(f"El «{empresa}» avanza cerca de {muni}")
        else:
            nombre = f" «{empresa}»" if empresa else ""
            titular = h(f"Un parque eólico{nombre} avanza cerca de {muni}")
    elif "planta de aceite" in t or "aceites de semillas" in t or "embotellado de aceite" in t:
        titular = h(f"Una planta de aceite proyecta instalarse en {muni}")
    elif "plan general de ordenacion urbana" in t:
        titular = h(f"{muni} da un paso en su nuevo Plan General de Ordenación Urbana")
    elif "plan economico financiero" in t:
        anio = re.search(r"\b(20\d{2})\b", titulo)
        titular = h(f"{muni} aprueba su plan económico" + (f" para {anio.group(1)}" if anio else ""))
    elif "modificacion presupuestaria" in t or "presupuest" in t or "credito extraordinario" in t or "suplemento de credito" in t:
        titular = h(f"{muni} modifica su presupuesto municipal")
    elif "licitaci" in t:
        obj = _licitacion_objeto(titulo)
        titular = h(f"{muni} saca a licitación {obj}" if obj else f"{muni} abre una nueva licitación")
    elif "declaracion de ruina" in t:
        titular = h(f"El Ayuntamiento de {muni} tramita la ruina de un inmueble")
    elif "via pecuaria" in t:
        via = _quoted(titulo)
        titular = h(f"Ocupación temporal de la vía pecuaria «{via}» en {muni}" if via else f"Ocupación temporal de una vía pecuaria en {muni}")
    elif "instalacion de distribucion electrica" in t or "linea electrica" in t or "instalacion electrica" in t:
        titular = h(f"Nueva instalación eléctrica en {muni}")
    elif "explotacion porcina" in t or "explotacion ganadera" in t or "explotacion avicola" in t:
        titular = h(f"Trámite ambiental de una explotación ganadera en {muni}")
    elif "uso excepcional de suelo rustico" in t:
        obj = _para_objeto(titulo)
        if obj:
            titular = h(f"Piden permiso para {obj} en {muni}{(' ('+empresa+')') if empresa else ''}")
        else:
            titular = h(f"Solicitan un uso excepcional de suelo rústico en {muni}")
    elif "impacto ambiental" in t or "autorizacion ambiental" in t:
        titular = h(f"Trámite ambiental de un proyecto en {muni}")
    elif "subvenci" in t or "ayuda" in t:
        titular = h(f"Nueva convocatoria de ayudas que afecta a {muni}")
    elif "acuerdo" in t and "pleno" in t:
        titular = h(f"Acuerdo del Pleno del Ayuntamiento de {muni}")
    else:
        # Genérico: primero intenta la cláusula real ("...por la que se concede/aprueba/...");
        # es lo que de verdad pasó. Solo si no la hay, se recorta el arranque burocrático
        # (y eso puede dejar un titular empezando por una fecha, así que es el último recurso).
        accion = _por_la_que(titulo)
        if accion:
            accion = accion[:1].upper() + accion[1:]
            titular = h(f"{muni}: {accion}" if muni and muni.lower() not in accion.lower() else accion)
        else:
            base = re.sub(r"^(INFORMACI[ÓO]N p[úu]blica relativa a la |INFORMACI[ÓO]N p[úu]blica relativa al |INFORMACI[ÓO]N p[úu]blica relativa a |ANUNCIO (?:de|del) |RESOLUCI[ÓO]N de \d{1,2} de \w+ de \d{4}, |RESOLUCI[ÓO]N de |ORDEN |ACUERDO de )", "", titulo, flags=re.I)
            base = _limpiar(base)
            base = base[:1].upper() + base[1:]
            titular = h(base if len(base) <= 90 else base[:88] + "…")
        titular = titular[:1].upper() + titular[1:]

    return {"titular": titular, "entradilla": entradilla}
