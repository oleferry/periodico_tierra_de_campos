"""Desarrolla una pista del radar (scrapers/radar_noticias.py) en una pieza
NUESTRA, que se publica en la ficha de su pueblo — nunca en la portada.

Por qué existe: el radar solo da pistas (titular ajeno + enlace). Publicar eso
sería republicar el trabajo de otro medio. Este script cierra el circuito:
lee la noticia de origen, extrae los HECHOS y encarga a la IA una pieza propia
que cita a quien lo publicó primero (ver sitegen/ia.py:_SISTEMA_PISTA, que
prohíbe copiar y parafrasear).

Reparto (lo que pidió el usuario el 2026-07-17): cada noticia vive en la ficha
de su pueblo, no en la portada — a un vecino de Villada no le interesa mucho lo
que pasa en Sahagún, y la portada no debe convertirse en un cajón de sastre.

Publicación (decisión del usuario, 2026-08-18): --indice publica directamente,
sin paso manual de revisión. --publicar se conserva por compatibilidad con
piezas antiguas que hayan quedado en estado 'borrador'.

Modo automático (decisión del usuario, 2026-09-17): --auto N lo corre el build
diario y desarrolla hasta N pistas al día sin que nadie las elija. Como nadie
las revisa, pasan dos puertas antes de desarrollarse, las dos conservadoras:
  1. palabras de suceso en titular y resumen (gratis, determinista);
  2. clasificación con IA (sitegen/ia.py:clasificar_pista) que descarta
     sucesos, fallecimientos, menores, personas vulnerables, noticias ya
     publicadas, anuncios caducados y piezas sin hechos. Si la clasificación
     falla, la pista no se publica.
La política editorial prohíbe publicar sucesos automáticamente, y buena parte
del radar son sucesos: por eso la primera puerta existe aunque haya segunda.

A diferencia de la cola de pistas (data/radar/, en .gitignore por ser texto
ajeno), este fichero SÍ se versiona: es contenido nuestro.

Uso:
    python -m scripts.desarrollar_pista --listar
    python -m scripts.desarrollar_pista --indice 3
    python -m scripts.desarrollar_pista --auto 2          # lo que corre el build diario
    python -m scripts.desarrollar_pista --auto 2 --dry-run  # qué haría, sin gastar en redacción
    python -m scripts.desarrollar_pista --listar-borradores
    python -m scripts.desarrollar_pista --publicar <hash>
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

# La consola de Windows viene en cp1252 y revienta al imprimir el borrador
# (tildes, guiones largos). El texto ya estaba guardado cuando petaba, pero el
# script salía con error: se fuerza UTF-8 en la salida.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

from scrapers.common import ROOT, ScraperError, fetch, sha256  # noqa: E402
from scrapers.radar_noticias import PISTAS_PATH  # noqa: E402
from sitegen import ia  # noqa: E402

PROPIAS_PATH = ROOT / "data" / "noticias" / "propias.json"

# Mínimo de texto para que una noticia dé para una pieza propia. Por debajo de
# esto el original es un teletipo de tres líneas: no hay hechos suficientes y
# lo único "desarrollable" sería su redacción — justo lo que no queremos.
MIN_CARACTERES = 400


def _cargar(path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _guardar(path, datos: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _pistas_pendientes(pueblo: str | None = None) -> list[dict]:
    """Pistas pendientes de cualquier pueblo de la comarca, no solo de los 12
    pilotos: al publicar una pieza de un pueblo vecino, este gana ficha propia
    automáticamente (ver sitegen/build.py, construcción de `slugs`)."""
    pistas = [p for p in _cargar(PISTAS_PATH) if p.get("estado") == "pendiente"]
    if pueblo:
        pistas = [p for p in pistas if p["municipality_slug"] == pueblo]
    return pistas


def extraer_texto(url: str) -> str:
    """Texto del artículo de origen, como materia prima de hechos para la IA.
    No se guarda ni se publica: solo alimenta la redacción propia."""
    soup = BeautifulSoup(fetch(url), "html.parser")
    for basura in soup.select("script, style, nav, header, footer, aside, form"):
        basura.decompose()
    nodo = soup.select_one("article") or soup.select_one("main") or soup.body
    if not nodo:
        raise ScraperError("unexpected_structure", f"Sin cuerpo legible en {url}")
    # Con <p> (WordPress: La Mar de Campos, Palencia en la Red) se filtra por
    # párrafo. Folioepress (Sahagún Digital, Leonsur, InterBenavente) no usa <p>
    # en el cuerpo — sus únicos <p> son el aviso legal de los comentarios — así
    # que ahí se cae al texto del propio <article>, línea a línea.
    parrafos = [p.get_text(" ", strip=True) for p in nodo.select("p")]
    texto = "\n".join(p for p in parrafos if len(p) > 40)
    if len(texto) < MIN_CARACTERES:
        texto = "\n".join(l for l in nodo.get_text("\n", strip=True).splitlines() if len(l) > 40)
    return texto.strip()


def _hash_pieza(pista: dict) -> str:
    return sha256(f"propia-{pista['url_original']}")


def desarrollar(pista: dict, texto: str | None = None) -> dict:
    """Pista -> doc con nuestra redacción dentro. Lanza si no hay material o IA.
    `texto` permite reutilizar el que ya se leyó para clasificarla (modo --auto)."""
    if not ia.disponible():
        raise SystemExit("Falta OPENAI_API_KEY/ANTHROPIC_API_KEY real en .env: sin IA no hay pieza propia.")

    if texto is None:
        print(f"· Leyendo la fuente ({pista['fuente']})…")
        texto = extraer_texto(pista["url_original"])
    print(f"  {len(texto)} caracteres de material")
    if len(texto) < MIN_CARACTERES:
        raise SystemExit(
            f"El original solo tiene {len(texto)} caracteres (mínimo {MIN_CARACTERES}). "
            "No hay hechos suficientes para una pieza propia: lo único que podríamos "
            "'desarrollar' sería su redacción. Descártala o busca otra fuente."
        )

    doc = {
        "municipality_slug": pista["municipality_slug"],
        "municipality_name": pista["municipality_name"],
        "title": pista["titulo"],          # solo referencia interna, NO se publica
        "source_type": "radar_local",
        "url_original": pista["url_original"],
        "published_at": (pista.get("publicado") or datetime.now(timezone.utc).isoformat())[:10],
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "pista_texto": texto,
        "hash": _hash_pieza(pista),
        "confidence": "medium",            # material de terceros, sin revisión humana
        "requires_review": False,
        "estado": "publicado",
        "metadata": {"fuente": pista["fuente"], "fuente_slug": pista["fuente_slug"],
                     "scraper": "SCR-016"},
    }

    print("· Redactando pieza propia con IA…")
    doc["redaccion"] = ia.redactar_pista(doc)
    # El material ajeno ya cumplió su función (alimentar la redacción). No se
    # conserva: el fichero se versiona en un repo público.
    doc.pop("pista_texto")
    return doc


def _guardar_pieza(doc: dict) -> None:
    propias = [d for d in _cargar(PROPIAS_PATH) if d["hash"] != doc["hash"]]
    propias.insert(0, doc)
    _guardar(PROPIAS_PATH, propias)


def _marcar_pista(pista: dict, estado: str, motivo: str = "") -> None:
    """Deja la pista fuera de la cola para no volver a evaluarla. El motivo del
    descarte es una etiqueta corta, no texto ajeno: data/radar/ no se versiona,
    pero en CI se conserva entre builds con actions/cache."""
    cola = _cargar(PISTAS_PATH)
    for p in cola:
        if p["hash"] == pista["hash"]:
            p["estado"] = estado
            if motivo:
                p["motivo_descarte"] = motivo
    _guardar(PISTAS_PATH, cola)


# ---------------------------------------------------------------- modo --auto

# Cuántas pistas se leen y clasifican como mucho por ejecución, para acotar
# peticiones a medios ajenos y llamadas a la IA aunque la cola sea grande.
MAX_EVALUADAS = 15

# Antigüedad máxima de una pista con fecha para desarrollarse sola: una noticia
# de hace un mes publicada hoy como nueva engaña al lector.
DIAS_MAX_ANTIGUEDAD = 7

# Primera puerta: palabras que delatan un suceso (sobre el texto sin tildes).
# Deliberadamente amplia — perder alguna noticia buena por un falso positivo
# ("Kiko Rivera dispara el mercurio festivo") es mucho mejor que publicar sola
# un accidente con heridos. Calibrada contra la cola real del 2026-09-17: 19 de
# 19 sucesos evidentes fuera. Lo que se le escapa lo para la segunda puerta.
_PATRON_SUCESO = re.compile("|".join([
    r"accident", r"herid[oa]s?\b", r"fallec", r"muert[eoa]", r"\bmurio\b", r"cadaver",
    r"\bmat(o|aron)\b", r"incendi", r"\barden?\b", r"\bllamas\b", r"calcin", r"detenid",
    r"detencion", r"guardia civil", r"policia", r"atropell", r"choque", r"colision",
    r"vuelc[ao]", r"volcar", r"salirse de la via", r"sal(e|ida) de (la )?via",
    r"\brob(o|an|aron|ar)\b", r"hurto", r"asalt", r"agresi", r"agred", r"apunal",
    # «dispar» y «rescat» en forma nominal o de participio: «dispara el mercurio
    # festivo» o «rescata en escena a fray Bernardino» no son sucesos.
    r"\bdispar(o|os|aron|ado)\b", r"tiroteo", r"estaf", r"investig(an|ado|ada|ados|adas)\b",
    r"desaparecid", r"ahogad", r"suicid", r"siniestro", r"\brescate\b", r"rescatad[oa]s?\b",
    r"evacuad", r"helicoptero", r"\b112\b",
    r"suceso", r"violencia", r"maltrat", r"\babus[oa]", r"\bmenores\b",
]))


def _sin_tildes(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _palabra_de_suceso(pista: dict) -> str | None:
    m = _PATRON_SUCESO.search(_sin_tildes(f"{pista['titulo']} {pista.get('resumen', '')}"))
    return m.group(0) if m else None


def _fecha_pista(pista: dict) -> datetime | None:
    """Fecha de publicación si la fuente la da; si no (Sahagún Digital no la
    trae en el listado), la de la primera vez que el radar la vio."""
    for campo in ("publicado", "detected_at"):
        valor = pista.get(campo)
        if not valor:
            continue
        try:
            fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            continue
        return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)
    return None


def _titulares_recientes(slug: str, dias: int = 45) -> list[str]:
    limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    return [
        d["redaccion"]["titular"] for d in _cargar(PROPIAS_PATH)
        if d.get("municipality_slug") == slug and (d.get("detected_at") or "") >= limite
        and d.get("redaccion")
    ]


def auto(maximo: int, dry_run: bool = False) -> int:
    """Desarrolla y publica hasta `maximo` pistas sin intervención humana.
    Nunca lanza: lo corre el build diario y un fallo aquí no puede impedir que
    el sitio se publique. Devuelve cuántas se publicaron."""
    if not ia.disponible():
        print("aviso: sin ANTHROPIC_API_KEY no se desarrollan pistas", file=sys.stderr)
        return 0

    ahora = datetime.now(timezone.utc)
    hechas = {d["hash"] for d in _cargar(PROPIAS_PATH)}
    candidatas = []
    for p in _pistas_pendientes():
        fecha = _fecha_pista(p)
        if _hash_pieza(p) in hechas or fecha is None:
            continue
        if ahora - fecha > timedelta(days=DIAS_MAX_ANTIGUEDAD):
            continue
        candidatas.append((fecha, p))
    # Primero las más nuevas.
    candidatas.sort(key=lambda par: par[0], reverse=True)
    print(f"· {len(candidatas)} pistas recientes sin desarrollar")

    publicadas, evaluadas, pueblos = 0, 0, set()
    for _, pista in candidatas:
        if publicadas >= maximo or evaluadas >= MAX_EVALUADAS:
            break
        # Una por pueblo al día: que no salgan tres piezas de la misma feria.
        if pista["municipality_slug"] in pueblos:
            continue
        etiqueta = f"{pista['municipality_name']} — {pista['titulo'][:70]}"

        palabra = _palabra_de_suceso(pista)
        if palabra:
            print(f"  fuera (suceso, «{palabra}»): {etiqueta}")
            if not dry_run:
                _marcar_pista(pista, "descartada", "suceso")
            continue

        evaluadas += 1
        try:
            texto = extraer_texto(pista["url_original"])
        except ScraperError as exc:
            print(f"  aviso: no se pudo leer {pista['url_original']} ({exc}); otro día", file=sys.stderr)
            continue
        if len(texto) < MIN_CARACTERES:
            print(f"  fuera (sin material, {len(texto)} car.): {etiqueta}")
            if not dry_run:
                _marcar_pista(pista, "descartada", "sin_material")
            continue

        try:
            veredicto = ia.clasificar_pista(
                pueblo=pista["municipality_name"], titulo=pista["titulo"], texto=texto,
                hoy=ahora.date().isoformat(),
                titulares_recientes=_titulares_recientes(pista["municipality_slug"]),
            )
        except Exception as exc:  # noqa: BLE001 — sin clasificar, no se publica
            print(f"  aviso: no se pudo clasificar ({exc}); no se publica hoy: {etiqueta}", file=sys.stderr)
            continue
        if veredicto["categoria"] != "publicable":
            print(f"  fuera ({veredicto['categoria']}: {veredicto['motivo']}): {etiqueta}")
            if not dry_run:
                _marcar_pista(pista, "descartada", veredicto["categoria"])
            continue

        if dry_run:
            print(f"  PUBLICARÍA: {etiqueta}")
            publicadas += 1
            pueblos.add(pista["municipality_slug"])
            continue

        try:
            doc = desarrollar(pista, texto=texto)
        except (Exception, SystemExit) as exc:  # noqa: BLE001
            print(f"  aviso: fallo redactando ({exc}); se reintentará: {etiqueta}", file=sys.stderr)
            continue
        _guardar_pieza(doc)
        _marcar_pista(pista, "desarrollada")
        publicadas += 1
        pueblos.add(pista["municipality_slug"])
        print(f"  publicada: {doc['redaccion']['titular']} ({pista['municipality_name']})")

    print(f"· Pistas desarrolladas{' (simulación)' if dry_run else ''}: {publicadas} de {maximo}")
    return publicadas


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-016 — Desarrolla una pista en pieza propia")
    ap.add_argument("--listar", action="store_true", help="pistas pendientes (todas o las de --pueblo)")
    ap.add_argument("--pueblo", metavar="SLUG", help="limita --listar/--indice a un pueblo")
    ap.add_argument("--listar-borradores", action="store_true", help="piezas propias sin publicar")
    ap.add_argument("--indice", type=int, help="desarrolla la pista N de --listar")
    ap.add_argument("--publicar", metavar="HASH", help="marca una pieza como publicada")
    ap.add_argument("--auto", type=int, metavar="N",
                    help="elige, filtra y publica solo hasta N pistas (build diario)")
    ap.add_argument("--dry-run", action="store_true",
                    help="con --auto: clasifica y dice qué publicaría, sin redactar ni guardar")
    args = ap.parse_args()

    if args.auto is not None:
        auto(args.auto, dry_run=args.dry_run)
        return 0

    if args.listar:
        pistas = _pistas_pendientes(args.pueblo)
        for i, p in enumerate(pistas):
            print(f"[{i:2}] {p['municipality_name']:22} [{p['fuente']}] {p['titulo'][:70]}")
        print(f"\n{len(pistas)} pistas pendientes.")
        return 0

    if args.listar_borradores:
        for d in _cargar(PROPIAS_PATH):
            print(f"[{d['estado']:9}] {d['municipality_name']:22} {d['redaccion']['titular'][:65]}")
            print(f"            {d['hash']}")
        return 0

    if args.publicar:
        propias = _cargar(PROPIAS_PATH)
        for d in propias:
            if d["hash"].startswith(args.publicar):
                d["estado"] = "publicado"
                _guardar(PROPIAS_PATH, propias)
                print(f"Publicada: {d['redaccion']['titular']}")
                print("Aparecerá en la ficha de", d["municipality_name"],
                      "en el próximo `python -m sitegen.build`.")
                return 0
        print(f"No hay ninguna pieza con hash {args.publicar}", file=sys.stderr)
        return 1

    if args.indice is None:
        ap.error("indica --listar, --indice N, --listar-borradores o --publicar HASH")

    pistas = _pistas_pendientes(args.pueblo)
    if not 0 <= args.indice < len(pistas):
        print(f"Índice fuera de rango (hay {len(pistas)} pistas)", file=sys.stderr)
        return 1
    pista = pistas[args.indice]

    doc = desarrollar(pista)
    _guardar_pieza(doc)
    # La pista queda marcada para no volver a ofrecerla.
    _marcar_pista(pista, "desarrollada")

    r = doc["redaccion"]
    print(f"\n== Borrador para {doc['municipality_name']} ==")
    print(f"{r['titular']}\n")
    print(f"{r['entradilla']}\n")
    for parrafo in r["cuerpo"]:
        print(f"{parrafo}\n")
    print(f"Fuente citada: {doc['metadata']['fuente']} — {doc['url_original']}")
    print(f"\nPublicada. Aparecerá en la ficha de {doc['municipality_name']}",
          "en el próximo `python -m sitegen.build`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
